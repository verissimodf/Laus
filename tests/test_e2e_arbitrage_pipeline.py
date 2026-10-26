#!/usr/bin/env python3
"""
test_e2e_arbitrage_pipeline.py - Comprehensive E2E Integration Suite for Laus
Verifies end-to-end flow between:
  - Pilar 1: core_jarvis (JarvisOrchestrator & Emergency Stop)
  - Pilar 2: agents_quant (AsyncSpreadDetector & ArbitrageProposal)
  - Pilar 3: gateway_vault (RiskGuardrail deterministic checks)
  - Pilar 4: console_ui (PostHog telemetry capture)
  - Pilar 8: accounting_ledger (Double-entry journal & IN 1888 tax provisions)
"""

import asyncio
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Setup module resolution
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "core_jarvis"))
sys.path.insert(0, str(project_root / "gateway_vault" / "guardrail"))
sys.path.insert(0, str(project_root / "accounting_ledger"))
sys.path.insert(0, str(project_root / "agents_quant" / "arbitrators"))
sys.path.insert(0, str(project_root / "agents_quant" / "mirofish_simulator"))
sys.path.insert(0, str(project_root / "cognition_skills" / "skills" / "posthog_telemetry" / "scripts"))

from core_jarvis.orchestrator import JarvisOrchestrator
from gateway_vault.guardrail.risk_validator import RiskGuardrail
from accounting_ledger.ledger_engine import AccountingLedger, DailyPaperDrawdownLimitError, DailyPaperNotionalLimitError
from agents_quant.arbitrators.spread_detector import ArbitrageProposal, AsyncSpreadDetector, SpreadOpportunity
from core_jarvis.pipeline_e2e import LausE2EPipeline
from agents_quant.mirofish_simulator.swarm_orchestrator import SwarmOrchestrator


class TestLausE2EArbitragePipeline(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Create an isolated temporary SQLite database for testing (no Drive pollution)
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name

        self.kill_switch_path = self.db_path + ".kill_switch.json"
        Path(self.kill_switch_path).write_text(json.dumps({"active": False, "reason": None}), encoding="utf-8")
        self.orchestrator = JarvisOrchestrator(kill_switch_path=self.kill_switch_path)
        self.ledger = AccountingLedger(self.db_path)
        self.guardrail = RiskGuardrail(max_order_usd=500.0, max_slippage_pct=0.50)
        self.pipeline = LausE2EPipeline(
            orchestrator=self.orchestrator,
            ledger=self.ledger,
            guardrail=self.guardrail,
            db_path=self.db_path,
            environment="automated_test_suite",
        )

    def tearDown(self):
        # Clean up temporary SQLite database
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
            if os.path.exists(self.kill_switch_path):
                os.remove(self.kill_switch_path)
        except Exception:
            pass

    async def test_kill_switch_persists_across_orchestrator_restart(self):
        self.orchestrator.trigger_kill_switch("test emergency")
        restarted = JarvisOrchestrator(kill_switch_path=self.kill_switch_path)

        self.assertTrue(restarted.emergency_stop)
        self.assertEqual(restarted.emergency_stop_reason, "test emergency")
        result = await restarted.dispatch_event("ARBITRAGE_TRADE_COMPLETED", {})
        self.assertEqual(result["status"], "aborted")

    def test_kill_switch_reads_configured_environment_path(self):
        from unittest.mock import patch

        configured_path = self.db_path + ".configured-kill-switch.json"
        Path(configured_path).write_text(
            json.dumps({"active": True, "reason": "configured path"}),
            encoding="utf-8",
        )
        try:
            with patch.dict(os.environ, {"LAUS_KILL_SWITCH_PATH": configured_path}):
                configured = JarvisOrchestrator()

            self.assertEqual(configured.kill_switch_path, Path(configured_path))
            self.assertTrue(configured.emergency_stop)
            self.assertEqual(configured.emergency_stop_reason, "configured path")
        finally:
            Path(configured_path).unlink(missing_ok=True)

    def test_kill_switch_reset_requires_confirmation_and_persists_reason(self):
        self.orchestrator.trigger_kill_switch("incident under review")

        with self.assertRaisesRegex(ValueError, "Confirmação inválida"):
            self.orchestrator.reset_kill_switch("reset", "cause reviewed")
        with self.assertRaisesRegex(ValueError, "motivo do reset"):
            self.orchestrator.reset_kill_switch("RESET KILL SWITCH", "  ")
        self.assertTrue(self.orchestrator.emergency_stop)

        self.assertTrue(
            self.orchestrator.reset_kill_switch(
                "RESET KILL SWITCH",
                "source issue fixed and manual checks completed",
            )
        )
        self.assertFalse(self.orchestrator.emergency_stop)
        self.assertIsNone(self.orchestrator.emergency_stop_reason)

        with open(self.kill_switch_path, encoding="utf-8") as state_file:
            state = json.load(state_file)
        self.assertFalse(state["active"])
        self.assertEqual(
            state["last_reset"]["reason"],
            "source issue fixed and manual checks completed",
        )
        self.assertTrue(state["last_reset"]["timestamp_utc"])

        restarted = JarvisOrchestrator(kill_switch_path=self.kill_switch_path)
        self.assertFalse(restarted.emergency_stop)

    def test_kill_switch_reset_refuses_stale_cross_process_incident_state(self):
        self.orchestrator.trigger_kill_switch("original incident")
        Path(self.kill_switch_path).write_text(
            json.dumps({"active": True, "reason": "new incident from another process"}),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "mudou em outro processo"):
            self.orchestrator.reset_kill_switch(
                "RESET KILL SWITCH",
                "reviewed original incident",
            )

        self.assertTrue(self.orchestrator.emergency_stop)
        with open(self.kill_switch_path, encoding="utf-8") as state_file:
            state = json.load(state_file)
        self.assertTrue(state["active"])
        self.assertEqual(state["reason"], "new incident from another process")

    def test_kill_switch_reset_persistence_failure_keeps_latch_active(self):
        from unittest.mock import patch

        self.orchestrator.trigger_kill_switch("incident under review")
        with patch.object(
            self.orchestrator,
            "_persist_kill_switch_reset",
            side_effect=OSError("storage unavailable"),
        ):
            with self.assertRaises(OSError):
                self.orchestrator.reset_kill_switch(
                    "RESET KILL SWITCH",
                    "attempted reset after review",
                )

        self.assertTrue(self.orchestrator.emergency_stop)
        self.assertEqual(
            self.orchestrator.emergency_stop_reason,
            "incident under review",
        )

    async def test_pipeline_rejects_missing_or_below_minimum_spread(self):
        for index, spread_bps in enumerate((None, 30.0)):
            with self.subTest(spread_bps=spread_bps):
                proposal = ArbitrageProposal(
                    proposal_id=f"PROP-PIPELINE-SPREAD-{index}",
                    timestamp=time.time(),
                    symbol="USDT/BRL",
                    side="buy",
                    amount_usd=100.0,
                    fiat_ask=5.0240,
                    target_price=5.0,
                    expected_net_profit_usd=1.0,
                    latency_ms=30.0,
                    guardrail_approved=True,
                    status="STAGED_FOR_MCP_EXECUTION",
                    net_spread_bps=spread_bps,
                    estimated_slippage=0.1,
                )
                result = await self.pipeline.execute_pipeline_turn(proposal)
                self.assertFalse(result["success"])
                self.assertEqual(
                    result["status"],
                    "INVALID_PROPOSAL_SPREAD" if spread_bps is None else "REJECTED_BELOW_MIN_SPREAD",
                )

        self.assertEqual(self.ledger.get_summary()["total_operacoes"], 0)

    async def test_stage_rejects_opportunity_below_minimum_spread(self):
        dispatched = []

        async def capture_proposal(proposal):
            dispatched.append(proposal)

        detector = AsyncSpreadDetector(
            min_spread_bps=65.0,
            on_proposal_created=capture_proposal,
        )
        opportunity = SpreadOpportunity(
            opportunity_id="OPP-BELOW-STAGING-THRESHOLD",
            timestamp=time.time(),
            symbol="USDT/BRL",
            p_fiat_ask=5.0,
            p_crypto_vwap=5.001,
            gross_spread_pct=0.02,
            total_costs_pct=0.01,
            net_spread_pct=0.01,
            net_spread_bps=1.0,
            estimated_slippage_pct=0.1,
            viable_volume_usd=100.0,
            is_actionable=False,
        )

        proposal = await detector.stage_mcp_proposal(opportunity, latency_ms=10.0)

        self.assertFalse(proposal.guardrail_approved)
        self.assertEqual(proposal.status, "REJECTED_BELOW_MIN_SPREAD")
        self.assertIn("abaixo do mínimo", proposal.guardrail_reason)
        self.assertEqual(dispatched, [proposal])
        self.assertEqual(detector.proposals_history, [proposal])

    async def test_01_paper_trade_is_recorded_without_claiming_execution(self):
        """Cenário 1: Proposta viável aprovada pelo Guardrail e registrada no Ledger com provisão IN 1888."""
        detector = AsyncSpreadDetector(
            symbol="USDT/BRL",
            min_spread_bps=20.0,
            max_order_usd=500.0,
            max_slippage_pct=0.50,
            max_latency_ms=500.0,
        )

        opportunity = SpreadOpportunity(
            opportunity_id="OPP-TEST-01",
            timestamp=time.time(),
            symbol="USDT/BRL",
            p_fiat_ask=5.0200,
            p_crypto_vwap=5.0600,
            gross_spread_pct=0.796,
            total_costs_pct=0.498,
            net_spread_pct=0.298,
            net_spread_bps=29.8,
            estimated_slippage_pct=0.12,
            viable_volume_usd=250.0,
            is_actionable=True,
        )

        proposal = await detector.stage_mcp_proposal(opportunity, latency_ms=42.5)
        self.pipeline.min_spread_bps = 20.0

        self.assertTrue(proposal.guardrail_approved)
        self.assertEqual(proposal.status, "STAGED_FOR_MCP_EXECUTION")

        result = await self.pipeline.execute_pipeline_turn(
            proposal=proposal,
            fiat_rate=5.0240,
            effective_spread_pct=0.75,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "PAPER_TRADE_RECORDED")
        self.assertIn("ledger_result", result)

        ledger_res = result["ledger_result"]
        self.assertGreater(ledger_res["net_profit_usd"], 0)
        self.assertGreater(ledger_res["tax_provision_brl"], 0)

        # Verify database persistence
        summary = self.ledger.get_summary()
        self.assertEqual(summary["total_operacoes"], 1)
        self.assertGreater(summary["lucro_liquido_usd"], 0)
        self.assertGreater(summary["provisao_ir_brl"], 0)

    def test_ledger_rejects_non_finite_accounting_values(self):
        invalid_values = [
            {"amount_usd": float("nan"), "rate": 5.0, "spread_pct": 0.5},
            {"amount_usd": 10.0, "rate": float("inf"), "spread_pct": 0.5},
            {"amount_usd": 10.0, "rate": 5.0, "spread_pct": float("nan")},
            {"amount_usd": 10.0, "rate": 0.0, "spread_pct": 0.5},
        ]
        for values in invalid_values:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    self.ledger.record_arbitrage_trade(
                        symbol="USDT/BRL",
                        source="test",
                        **values,
                    )
        self.assertEqual(self.ledger.get_summary()["total_operacoes"], 0)

    async def test_pipeline_rejects_non_json_market_evidence_without_ledger_write(self):
        proposal = ArbitrageProposal(
            proposal_id="PROP-INVALID-EVIDENCE",
            timestamp=time.time(),
            symbol="USDT/BRL",
            side="buy",
            amount_usd=100.0,
            fiat_ask=5.0240,
            target_price=5.0,
            expected_net_profit_usd=1.0,
            latency_ms=30.0,
            guardrail_approved=True,
            status="STAGED_FOR_MCP_EXECUTION",
            net_spread_bps=100.0,
            estimated_slippage=0.1,
            market_evidence={"invalid": {1, 2, 3}},
        )

        result = await self.pipeline.execute_pipeline_turn(proposal)

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "PAPER_LEDGER_INPUT_REJECTED")
        self.assertIn("serializável", result["reason"])
        self.assertEqual(self.ledger.get_summary()["total_operacoes"], 0)

    async def test_invalid_paper_accounting_inputs_are_rejected_before_ledger_write(self):
        invalid_cases = [
            (float("nan"), 0.75),
            (5.024, float("inf")),
            (0.0, 0.75),
        ]

        for index, (fiat_rate, spread_pct) in enumerate(invalid_cases):
            with self.subTest(fiat_rate=fiat_rate, spread_pct=spread_pct):
                proposal = ArbitrageProposal(
                    proposal_id=f"PROP-INVALID-ACCOUNTING-{index}",
                    timestamp=time.time(),
                    symbol="USDT/BRL",
                    side="buy",
                    amount_usd=100.0,
                    fiat_ask=5.0240,
                    target_price=5.0,
                    expected_net_profit_usd=1.0,
                    latency_ms=30.0,
                    guardrail_approved=True,
                    status="STAGED_FOR_MCP_EXECUTION",
                    estimated_slippage=0.1,
                    net_spread_bps=100,
                )
                result = await self.pipeline.execute_pipeline_turn(
                    proposal,
                    fiat_rate=fiat_rate,
                    effective_spread_pct=spread_pct,
                )
                self.assertFalse(result["success"])
                self.assertEqual(result["status"], "PAPER_ACCOUNTING_INPUT_REJECTED")

        self.assertEqual(self.ledger.get_summary()["total_operacoes"], 0)

    async def test_pipeline_refreshes_external_kill_switch_activation(self):
        Path(self.kill_switch_path).write_text(
            json.dumps({"active": True, "reason": "activated by another process"}),
            encoding="utf-8",
        )
        proposal = ArbitrageProposal(
            proposal_id="PROP-EXTERNAL-KILL-SWITCH",
            timestamp=time.time(),
            symbol="USDT/BRL",
            side="buy",
            amount_usd=100.0,
            fiat_ask=5.0240,
            target_price=5.0,
            expected_net_profit_usd=1.0,
            latency_ms=30.0,
            guardrail_approved=True,
            status="STAGED_FOR_MCP_EXECUTION",
            estimated_slippage=0.1,
        )

        result = await self.pipeline.execute_pipeline_turn(proposal)

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "ABORTED_BY_KILL_SWITCH")
        self.assertTrue(self.orchestrator.emergency_stop)
        self.assertEqual(self.orchestrator.emergency_stop_reason, "activated by another process")
        self.assertEqual(self.ledger.get_summary()["total_operacoes"], 0)

        Path(self.kill_switch_path).write_text(
            json.dumps({"active": False, "reason": None}),
            encoding="utf-8",
        )
        self.assertTrue(self.orchestrator.refresh_kill_switch())

    async def test_kill_switch_activated_during_final_validation_blocks_ledger_write(self):
        from unittest.mock import patch

        proposal = ArbitrageProposal(
            proposal_id="PROP-KILL-SWITCH-RACE",
            timestamp=time.time(),
            symbol="USDT/BRL",
            side="buy",
            amount_usd=100.0,
            fiat_ask=5.0240,
            target_price=5.0,
            expected_net_profit_usd=1.0,
            latency_ms=30.0,
            guardrail_approved=True,
            status="STAGED_FOR_MCP_EXECUTION",
            estimated_slippage=0.1,
        )
        original_validate = self.guardrail.validate_order

        def validate_then_activate_kill_switch(*args, **kwargs):
            result = original_validate(*args, **kwargs)
            self.orchestrator.trigger_kill_switch("activated during final validation")
            return result

        with patch.object(
            self.guardrail,
            "validate_order",
            side_effect=validate_then_activate_kill_switch,
        ):
            result = await self.pipeline.execute_pipeline_turn(proposal)

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "ABORTED_BY_KILL_SWITCH")
        self.assertEqual(self.ledger.get_summary()["total_operacoes"], 0)
        self.assertEqual(self.pipeline.executed_trades, [])

    async def test_duplicate_proposal_is_recorded_only_once(self):
        proposal = ArbitrageProposal(
            proposal_id="PROP-IDEMPOTENCY-TEST",
            timestamp=time.time(),
            symbol="USDT/BRL",
            side="buy",
            amount_usd=100.0,
            fiat_ask=5.0240,
            target_price=5.0,
            expected_net_profit_usd=1.0,
            latency_ms=30.0,
            guardrail_approved=True,
            status="STAGED_FOR_MCP_EXECUTION",
            net_spread_bps=100.0,
            estimated_slippage=0.1,
        )

        first = await self.pipeline.execute_pipeline_turn(proposal)
        second = await self.pipeline.execute_pipeline_turn(proposal)

        self.assertTrue(first["success"])
        self.assertEqual(second["status"], "DUPLICATE_PROPOSAL")
        self.assertEqual(self.ledger.get_summary()["total_operacoes"], 1)
        self.assertEqual(self.ledger.get_daily_summary()["paper_trade_count"], 1)

    async def test_02_guardrail_rejects_excessive_order_amount(self):
        """Cenário 2: Ordem acima do limite máximo ($800 > $500) é barrada pelo RiskGuardrail."""
        detector = AsyncSpreadDetector(
            symbol="USDT/BRL",
            max_order_usd=500.0,
            max_slippage_pct=0.50,
            max_latency_ms=500.0,
        )

        opportunity = SpreadOpportunity(
            opportunity_id="OPP-TEST-OVERLIMIT",
            timestamp=time.time(),
            symbol="USDT/BRL",
            p_fiat_ask=5.0200,
            p_crypto_vwap=5.0600,
            gross_spread_pct=0.80,
            total_costs_pct=0.50,
            net_spread_pct=0.30,
            net_spread_bps=30.0,
            estimated_slippage_pct=0.10,
            viable_volume_usd=800.0,  # Excede $500
            is_actionable=True,
        )

        proposal = await detector.stage_mcp_proposal(opportunity, latency_ms=50.0)

        self.assertFalse(proposal.guardrail_approved)
        self.assertEqual(proposal.status, "REJECTED_GUARDRAIL")
        self.assertIn("excede o limite", proposal.guardrail_reason)

        result = await self.pipeline.execute_pipeline_turn(proposal)
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "REJECTED_GUARDRAIL")

        # Ledger must remain completely unpolluted
        summary = self.ledger.get_summary()
        self.assertEqual(summary["total_operacoes"], 0)

    async def test_03_guardrail_rejects_excessive_slippage(self):
        """Cenário 3: Slippage de 0.85% (tolerância 0.50%) é vetado pelo Guardrail."""
        detector = AsyncSpreadDetector(
            symbol="USDT/BRL",
            max_order_usd=500.0,
            max_slippage_pct=0.50,
        )

        opportunity = SpreadOpportunity(
            opportunity_id="OPP-TEST-SLIPPAGE",
            timestamp=time.time(),
            symbol="USDT/BRL",
            p_fiat_ask=5.0200,
            p_crypto_vwap=5.0600,
            gross_spread_pct=0.80,
            total_costs_pct=0.50,
            net_spread_pct=0.30,
            net_spread_bps=30.0,
            estimated_slippage_pct=0.85,  # Excede 0.50%
            viable_volume_usd=200.0,
            is_actionable=True,
        )

        proposal = await detector.stage_mcp_proposal(opportunity, latency_ms=40.0)
        self.assertFalse(proposal.guardrail_approved)
        self.assertIn("Slippage", proposal.guardrail_reason)

        result = await self.pipeline.execute_pipeline_turn(proposal)
        self.assertFalse(result["success"])
        self.assertEqual(self.ledger.get_summary()["total_operacoes"], 0)

    async def test_04_circuit_breaker_blocks_high_latency(self):
        """Cenário 4: Latência RTT de 650ms (limite 500ms) aciona o Circuit Breaker do Pilar 6."""
        detector = AsyncSpreadDetector(
            symbol="USDT/BRL",
            max_latency_ms=500.0,
        )

        opportunity = SpreadOpportunity(
            opportunity_id="OPP-TEST-LATENCY",
            timestamp=time.time(),
            symbol="USDT/BRL",
            p_fiat_ask=5.0200,
            p_crypto_vwap=5.0600,
            gross_spread_pct=0.80,
            total_costs_pct=0.50,
            net_spread_pct=0.30,
            net_spread_bps=30.0,
            estimated_slippage_pct=0.10,
            viable_volume_usd=200.0,
            is_actionable=True,
        )

        proposal = await detector.stage_mcp_proposal(opportunity, latency_ms=650.0)  # > 500ms
        self.assertFalse(proposal.guardrail_approved)
        self.assertEqual(proposal.status, "CIRCUIT_BREAKER_BLOCKED")

        result = await self.pipeline.execute_pipeline_turn(proposal)
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "CIRCUIT_BREAKER_BLOCKED")
        self.assertEqual(self.ledger.get_summary()["total_operacoes"], 0)

    async def test_05_kill_switch_aborts_all_operations(self):
        """Cenário 5: Ativação do Kill Switch do Jarvis aborta execuções instantaneamente."""
        self.orchestrator.trigger_kill_switch(reason="Panic button triggered from Console UI")
        self.assertTrue(self.orchestrator.emergency_stop)

        valid_proposal = ArbitrageProposal(
            proposal_id="PROP-VALID-BUT-HALTED",
            timestamp=time.time(),
            symbol="USDT/BRL",
            side="buy",
            amount_usd=200.0,
            fiat_ask=5.0240,
            target_price=5.0500,
            expected_net_profit_usd=1.50,
            latency_ms=35.0,
            guardrail_approved=True,
            status="STAGED_FOR_MCP_EXECUTION",
        )

        result = await self.pipeline.execute_pipeline_turn(valid_proposal)
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "ABORTED_BY_KILL_SWITCH")
        self.assertEqual(self.ledger.get_summary()["total_operacoes"], 0)

    async def test_06_live_callback_dispatch_integration(self):
        """Cenário 6: Conexão direta do callback do AsyncSpreadDetector ao pipeline E2E."""
        self.pipeline.min_spread_bps = 10.0
        captured_results = []

        async def pipeline_callback(proposal: ArbitrageProposal):
            res = await self.pipeline.handle_proposal_callback(proposal)
            captured_results.append(res)

        detector = AsyncSpreadDetector(
            symbol="USDT/BRL",
            min_spread_bps=10.0,  # Gatilho baixo para teste
            poll_interval_sec=0.1,
            max_order_usd=500.0,
            max_slippage_pct=0.50,
            on_proposal_created=pipeline_callback,
        )

        # Injeta uma proposta diretamente simulando o gatilho de mercado
        simulated_opp = detector.evaluate_spread(
            p_fiat=5.0200,
            p_crypto=5.0600,
            slippage_pct=0.15,
            volume_usd=250.0,
        )
        await detector.stage_mcp_proposal(simulated_opp, latency_ms=45.0)

        self.assertEqual(len(captured_results), 1)
        self.assertTrue(captured_results[0]["success"])
        self.assertEqual(self.ledger.get_summary()["total_operacoes"], 1)

    async def test_07_swarm_approval_leads_to_guardrail_and_ledger_execution(self):
        """Cenário 7: MiroFish Swarm aprova com consenso >= 3 e zero vetos, procedendo ao Guardrail e Ledger."""
        swarm_orch = SwarmOrchestrator(scenario="normal")
        detector = AsyncSpreadDetector(
            symbol="USDT/BRL",
            max_order_usd=500.0,
            max_slippage_pct=0.50,
            max_latency_ms=500.0,
            swarm_orchestrator=swarm_orch,
            enable_swarm=True,
        )

        pipeline = LausE2EPipeline(
            orchestrator=self.orchestrator,
            ledger=self.ledger,
            guardrail=self.guardrail,
            swarm_orchestrator=swarm_orch,
            enable_swarm=True,
            environment="automated_test_suite",
        )

        opportunity = SpreadOpportunity(
            opportunity_id="OPP-SWARM-APPROVED",
            timestamp=time.time(),
            symbol="USDT/BRL",
            p_fiat_ask=5.0200,
            p_crypto_vwap=5.0600,
            gross_spread_pct=0.85,
            total_costs_pct=0.45,
            net_spread_pct=0.40,
            net_spread_bps=80.0,  # > 50 bps (BullAnalyst aprova)
            estimated_slippage_pct=0.15,  # <= 0.40% (BearAnalyst aprova)
            viable_volume_usd=250.0,  # <= 500 (RiskManager aprova)
            is_actionable=True,
        )

        proposal = await detector.stage_mcp_proposal(opportunity, latency_ms=35.0)

        # Swarm validation assertions
        self.assertIsNotNone(proposal.swarm_result)
        self.assertEqual(proposal.swarm_result["final_decision"], "APPROVED")
        self.assertEqual(proposal.swarm_result["votes_summary"]["vetos"], 0)
        self.assertGreaterEqual(proposal.swarm_result["votes_summary"]["approves"], 3)
        self.assertTrue(proposal.guardrail_approved)
        self.assertEqual(proposal.status, "STAGED_FOR_MCP_EXECUTION")

        # Execute in Pipeline
        result = await pipeline.execute_pipeline_turn(proposal)
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "PAPER_TRADE_RECORDED")
        self.assertIsNotNone(result["swarm_result"])

        # Verify ledger has recorded trade
        summary = self.ledger.get_summary()
        self.assertEqual(summary["total_operacoes"], 1)

    async def test_08_swarm_vetoes_flash_crash_before_guardrail(self):
        """Cenário 8: Em flash crash, MiroFish Swarm emite veto imediato, impedindo envio ao Guardrail."""
        swarm_orch = SwarmOrchestrator(scenario="flash_crash")
        detector = AsyncSpreadDetector(
            symbol="USDT/BRL",
            max_order_usd=500.0,
            max_slippage_pct=0.50,
            swarm_orchestrator=swarm_orch,
            enable_swarm=True,
        )

        pipeline = LausE2EPipeline(
            orchestrator=self.orchestrator,
            ledger=self.ledger,
            guardrail=self.guardrail,
            swarm_orchestrator=swarm_orch,
            enable_swarm=True,
            environment="automated_test_suite",
        )

        opportunity = SpreadOpportunity(
            opportunity_id="OPP-SWARM-FLASH-CRASH",
            timestamp=time.time(),
            symbol="USDT/BRL",
            p_fiat_ask=5.0200,
            p_crypto_vwap=5.0600,
            gross_spread_pct=0.80,
            total_costs_pct=0.50,
            net_spread_pct=0.30,
            net_spread_bps=70.0,
            estimated_slippage_pct=0.20,
            viable_volume_usd=250.0,
            is_actionable=True,
        )

        proposal = await detector.stage_mcp_proposal(opportunity, latency_ms=40.0)

        # Must be rejected at Swarm stage, never marked as guardrail approved
        self.assertFalse(proposal.guardrail_approved)
        self.assertEqual(proposal.status, "REJECTED_BY_SWARM")
        self.assertIn("MiroFish Swarm Veto", proposal.guardrail_reason)
        self.assertGreater(proposal.swarm_result["votes_summary"]["vetos"], 0)

        # Pipeline execution should be blocked
        result = await pipeline.execute_pipeline_turn(proposal)
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "REJECTED_BY_SWARM")
        self.assertEqual(self.ledger.get_summary()["total_operacoes"], 0)

    async def test_09_swarm_vetoes_excessive_slippage(self):
        """Cenário 9: Slippage de 0.45% é vetado preventivamente pelo BearAnalyst antes do limite do Guardrail (0.50%)."""
        swarm_orch = SwarmOrchestrator(scenario="normal")
        detector = AsyncSpreadDetector(
            symbol="USDT/BRL",
            max_order_usd=500.0,
            max_slippage_pct=0.50,  # Guardrail aceitaria até 0.50%
            swarm_orchestrator=swarm_orch,
            enable_swarm=True,
        )

        pipeline = LausE2EPipeline(
            orchestrator=self.orchestrator,
            ledger=self.ledger,
            guardrail=self.guardrail,
            swarm_orchestrator=swarm_orch,
            enable_swarm=True,
            environment="automated_test_suite",
        )

        opportunity = SpreadOpportunity(
            opportunity_id="OPP-BEAR-SLIPPAGE-VETO",
            timestamp=time.time(),
            symbol="USDT/BRL",
            p_fiat_ask=5.0200,
            p_crypto_vwap=5.0600,
            gross_spread_pct=0.80,
            total_costs_pct=0.50,
            net_spread_pct=0.30,
            net_spread_bps=60.0,
            estimated_slippage_pct=0.45,  # > 0.40% -> BearAnalyst veta
            viable_volume_usd=200.0,
            is_actionable=True,
        )

        proposal = await detector.stage_mcp_proposal(opportunity, latency_ms=45.0)

        self.assertFalse(proposal.guardrail_approved)
        self.assertEqual(proposal.status, "REJECTED_BY_SWARM")
        self.assertIn("BearAnalyst", proposal.guardrail_reason)

        result = await pipeline.execute_pipeline_turn(proposal)
        self.assertFalse(result["success"])
        self.assertEqual(self.ledger.get_summary()["total_operacoes"], 0)

    async def test_pipeline_uses_environment_risk_limits_by_default(self):
        from unittest.mock import patch

        with patch.dict(
            os.environ,
            {"MAX_ORDER_USD": "125.0", "MAX_SLIPPAGE_PCT": "0.2"},
        ):
            pipeline = LausE2EPipeline(
                orchestrator=self.orchestrator,
                ledger=self.ledger,
                db_path=self.db_path,
            )

        self.assertEqual(pipeline.guardrail.max_order_usd, 125.0)
        self.assertEqual(pipeline.guardrail.max_slippage_pct, 0.2)

    def test_daily_notional_limit_is_atomic_across_ledger_connections(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        barrier = Barrier(2)

        def record_from_separate_connection(index):
            ledger = AccountingLedger(self.db_path)
            barrier.wait(timeout=5)
            try:
                return ledger.record_arbitrage_trade(
                    symbol="USDT/BRL",
                    amount_usd=60.0,
                    rate=5.0,
                    spread_pct=0.5,
                    source="PAPER_SIMULATION_CONCURRENCY_TEST",
                    proposal_id=f"PROP-CONCURRENT-{index}",
                    max_daily_notional_usd=100.0,
                )
            finally:
                ledger.conn.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(record_from_separate_connection, i) for i in range(2)]
            outcomes = []
            for future in futures:
                try:
                    future.result(timeout=10)
                    outcomes.append("recorded")
                except DailyPaperNotionalLimitError:
                    outcomes.append("limit_rejected")

        self.assertCountEqual(outcomes, ["recorded", "limit_rejected"])
        self.assertEqual(self.ledger.get_daily_summary()["paper_daily_notional_usd"], 60.0)

    def test_daily_drawdown_limit_is_atomic_across_ledger_connections(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        barrier = Barrier(2)

        def record_from_separate_connection(index):
            ledger = AccountingLedger(self.db_path)
            barrier.wait(timeout=5)
            try:
                return ledger.record_arbitrage_trade(
                    symbol="USDT/BRL",
                    amount_usd=100.0,
                    rate=5.0,
                    spread_pct=-5.0,
                    source="PAPER_SIMULATION_CONCURRENCY_TEST",
                    proposal_id=f"PROP-CONCURRENT-LOSS-{index}",
                    max_daily_notional_usd=1000.0,
                    max_daily_drawdown_usd=5.0,
                )
            finally:
                ledger.conn.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(record_from_separate_connection, i) for i in range(2)]
            outcomes = []
            for future in futures:
                try:
                    future.result(timeout=10)
                    outcomes.append("recorded")
                except DailyPaperDrawdownLimitError:
                    outcomes.append("drawdown_rejected")

        self.assertCountEqual(outcomes, ["recorded", "drawdown_rejected"])
        self.assertLessEqual(
            self.ledger.get_daily_summary()["paper_realized_pnl_usd"], -5.0
        )

    async def test_daily_paper_notional_limit_blocks_next_trade(self):
        self.ledger.record_arbitrage_trade(
            symbol="USDT-BRL",
            amount_usd=250.0,
            rate=5.0,
            spread_pct=0.0,
            source="PAPER_SIMULATION_TEST",
        )
        limited_pipeline = LausE2EPipeline(
            orchestrator=self.orchestrator,
            ledger=self.ledger,
            guardrail=RiskGuardrail(
                max_order_usd=500.0,
                max_slippage_pct=0.5,
                max_daily_paper_notional_usd=300.0,
            ),
            db_path=self.db_path,
            environment="automated_test_suite",
        )
        proposal = ArbitrageProposal(
            proposal_id="PROP-DAILY-NOTIONAL-STOP",
            timestamp=time.time(),
            symbol="USDT/BRL",
            side="buy",
            amount_usd=100.0,
            fiat_ask=5.0240,
            target_price=5.0,
            expected_net_profit_usd=1.0,
            latency_ms=30.0,
            guardrail_approved=True,
            status="STAGED_FOR_MCP_EXECUTION",
            net_spread_bps=100.0,
            estimated_slippage=0.1,
        )

        result = await limited_pipeline.execute_pipeline_turn(proposal)

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "DAILY_PAPER_NOTIONAL_LIMIT")
        self.assertEqual(result["daily_paper_notional_usd"], 250.0)
        self.assertEqual(self.ledger.get_summary()["total_operacoes"], 1)

    async def test_daily_paper_drawdown_blocks_next_trade(self):
        self.ledger.record_arbitrage_trade(
            symbol="USDT-BRL",
            amount_usd=500.0,
            rate=5.0,
            spread_pct=-60.0,
            source="PAPER_SIMULATION_TEST",
        )
        proposal = ArbitrageProposal(
            proposal_id="PROP-DAILY-LOSS-STOP",
            timestamp=time.time(),
            symbol="USDT/BRL",
            side="buy",
            amount_usd=100.0,
            fiat_ask=5.0240,
            target_price=5.0,
            expected_net_profit_usd=1.0,
            latency_ms=30.0,
            guardrail_approved=True,
            status="STAGED_FOR_MCP_EXECUTION",
            net_spread_bps=100.0,
            estimated_slippage=0.1,
        )

        result = await self.pipeline.execute_pipeline_turn(proposal)

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "DAILY_DRAWDOWN_LIMIT")
        self.assertEqual(self.ledger.get_summary()["total_operacoes"], 1)

    async def test_10_swarm_vetoes_macro_instability_custom_state(self):
        """Cenário 10: Instabilidade bancária ou oscilação cambial severa causa veto imediato pelo MacroMarketMaker."""
        swarm_orch = SwarmOrchestrator(scenario="normal")
        pipeline = LausE2EPipeline(
            orchestrator=self.orchestrator,
            ledger=self.ledger,
            guardrail=self.guardrail,
            swarm_orchestrator=swarm_orch,
            enable_swarm=True,
            environment="automated_test_suite",
        )

        # Proposta candidata não avaliada previamente
        candidate_proposal = ArbitrageProposal(
            proposal_id="PROP-MACRO-UNSTABLE",
            timestamp=time.time(),
            symbol="USDT/BRL",
            side="buy",
            amount_usd=250.0,
            fiat_ask=5.0240,
            target_price=5.0500,
            expected_net_profit_usd=2.00,
            latency_ms=40.0,
            guardrail_approved=True,
            status="STAGED_FOR_MCP_EXECUTION",
            net_spread_bps=70.0,
            estimated_slippage=0.15,
        )

        # Simula instabilidade macro injetada no ambiente do Swarm
        swarm_orch.env.scenario = "macro_stress"
        swarm_orch.env.get_current_state = lambda: {
            "trend": "neutral",
            "volatility": "high",
            "usd_brl_pct_change": 3.2,  # > 2.0% -> MacroMarketMaker veta
            "bank_network_status": "degraded",
        }

        result = await pipeline.execute_pipeline_turn(candidate_proposal)
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "REJECTED_BY_SWARM")
        self.assertIn("MacroMarketMaker", result["reason"])
        self.assertEqual(self.ledger.get_summary()["total_operacoes"], 0)



class TestRiskGuardrailInputValidation(unittest.TestCase):
    def setUp(self):
        from gateway_vault.guardrail.risk_validator import RiskGuardrail, RiskGuardrailException
        self.guardrail = RiskGuardrail()
        self.exception = RiskGuardrailException

    def test_rejects_non_positive_amount(self):
        for amount in (0, -1):
            with self.subTest(amount=amount), self.assertRaises(self.exception):
                self.guardrail.validate_order("USDT/BRL", amount, 0.1)

    def test_rejects_non_finite_values(self):
        for amount, slippage in ((float("nan"), 0.1), (250, float("inf"))):
            with self.subTest(amount=amount, slippage=slippage), self.assertRaises(self.exception):
                self.guardrail.validate_order("USDT/BRL", amount, slippage)

    def test_daily_limit_reads_environment_configuration(self):
        import os
        from unittest.mock import patch

        with patch.dict(
            os.environ,
            {
                "MAX_ORDER_USD": "400.0",
                "MAX_SLIPPAGE_PCT": "0.25",
                "MAX_DAILY_DRAWDOWN_USD": "125.5",
                "MAX_DAILY_PAPER_NOTIONAL_USD": "900.0",
            },
        ):
            configured = RiskGuardrail()

        self.assertEqual(configured.max_order_usd, 400.0)
        self.assertEqual(configured.max_slippage_pct, 0.25)
        self.assertEqual(configured.max_daily_drawdown_usd, 125.5)
        self.assertEqual(configured.max_daily_paper_notional_usd, 900.0)

    def test_daily_notional_limit_allows_cap_and_rejects_overflow(self):
        self.assertTrue(
            self.guardrail.validate_order(
                "USDT/BRL", 100.0, 0.1, daily_paper_notional_usd=2400.0
            )
        )
        with self.assertRaisesRegex(self.exception, "volume paper"):
            self.guardrail.validate_order(
                "USDT/BRL", 100.01, 0.1, daily_paper_notional_usd=2400.0
            )

    def test_rejects_invalid_daily_paper_notional(self):
        for value in (-1, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(self.exception):
                self.guardrail.validate_order(
                    "USDT/BRL", 100.0, 0.1, daily_paper_notional_usd=value
                )

    def test_rejects_proposal_after_daily_paper_loss_limit(self):
        with self.assertRaisesRegex(self.exception, "perda diária paper"):
            self.guardrail.validate_order(
                "USDT/BRL",
                100.0,
                0.1,
                daily_realized_pnl_usd=-250.0,
            )

    def test_rejects_negative_slippage_and_empty_symbol(self):
        with self.assertRaises(self.exception):
            self.guardrail.validate_order("USDT/BRL", 250, -0.1)
        with self.assertRaises(self.exception):
            self.guardrail.validate_order(" ", 250, 0.1)

class TestLedgerProposalIdempotencyMigration(unittest.TestCase):
    def test_existing_ledger_is_migrated_without_losing_rows(self):
        temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_db.close()
        try:
            conn = sqlite3.connect(temp_db.name)
            conn.execute(
                "CREATE TABLE journal_entries ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp INTEGER, "
                "symbol TEXT, side TEXT, amount_usd REAL, rate REAL, "
                "gross_profit_usd REAL, fee_usd REAL, net_profit_usd REAL, "
                "tax_provision_brl REAL, source TEXT)"
            )
            conn.execute(
                "INSERT INTO journal_entries (timestamp, symbol, side, amount_usd, "
                "rate, gross_profit_usd, fee_usd, net_profit_usd, tax_provision_brl, source) "
                "VALUES (1, 'USDT/BRL', 'ARBITRAGE', 100, 5, 1, 0.1, 0.9, 0, 'LEGACY')"
            )
            conn.commit()
            conn.close()

            ledger = AccountingLedger(temp_db.name)
            columns = {
                row[1] for row in ledger.conn.execute("PRAGMA table_info(journal_entries)")
            }
            self.assertIn("proposal_id", columns)
            self.assertEqual(ledger.get_summary()["total_operacoes"], 1)
            ledger.conn.close()
        finally:
            if os.path.exists(temp_db.name):
                os.remove(temp_db.name)


if __name__ == "__main__":
    unittest.main()
