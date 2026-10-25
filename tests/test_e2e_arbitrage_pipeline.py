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

from orchestrator import JarvisOrchestrator
from risk_validator import RiskGuardrail
from ledger_engine import AccountingLedger
from spread_detector import ArbitrageProposal, AsyncSpreadDetector, SpreadOpportunity
from pipeline_e2e import LausE2EPipeline
from swarm_orchestrator import SwarmOrchestrator


class TestLausE2EArbitragePipeline(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Create an isolated temporary SQLite database for testing (no Drive pollution)
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name

        self.kill_switch_path = self.db_path + ".kill_switch.json"
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

    async def test_01_paper_trade_is_recorded_without_claiming_execution(self):
        """Cenário 1: Proposta viável aprovada pelo Guardrail e registrada no Ledger com provisão IN 1888."""
        detector = AsyncSpreadDetector(
            symbol="USDT/BRL",
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

    async def test_duplicate_proposal_is_recorded_only_once(self):
        proposal = ArbitrageProposal(
            proposal_id="PROP-IDEMPOTENCY-TEST",
            timestamp=time.time(),
            symbol="USDT/BRL",
            side="buy",
            amount_usd=100.0,
            target_price=5.0,
            expected_net_profit_usd=1.0,
            latency_ms=30.0,
            guardrail_approved=True,
            status="STAGED_FOR_MCP_EXECUTION",
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
            target_price=5.0,
            expected_net_profit_usd=1.0,
            latency_ms=30.0,
            guardrail_approved=True,
            status="STAGED_FOR_MCP_EXECUTION",
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
            target_price=5.0,
            expected_net_profit_usd=1.0,
            latency_ms=30.0,
            guardrail_approved=True,
            status="STAGED_FOR_MCP_EXECUTION",
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
        from risk_validator import RiskGuardrail, RiskGuardrailException
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
                "MAX_DAILY_DRAWDOWN_USD": "125.5",
                "MAX_DAILY_PAPER_NOTIONAL_USD": "900.0",
            },
        ):
            configured = RiskGuardrail(max_order_usd=500.0, max_slippage_pct=0.5)

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
