import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from accounting_ledger.ledger_engine import AccountingLedger
from agents_quant.arbitrators.spread_detector import AsyncSpreadDetector, ArbitrageProposal
from cognition_skills.runtime import SkillRuntime
from console_ui import server
from core_jarvis.durable_bus import DurableEventBus
from core_jarvis.orchestrator import JarvisOrchestrator
from core_jarvis.pipeline_e2e import LausE2EPipeline
from digital_twin.shadow_exchange import performance_metrics, replay, walk_forward
from gateway_vault.credential_vault import CredentialVault
from scripts.paper_backup import backup


class PaperAcceptance(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / "kill.json"
        self.state.write_text('{"active": false, "reason": null}', encoding="utf-8")
        self.ledger = AccountingLedger(str(self.root / "paper.db"))
        self.orchestrator = JarvisOrchestrator(kill_switch_path=str(self.state))
        self.pipeline = LausE2EPipeline(orchestrator=self.orchestrator, ledger=self.ledger)

    def tearDown(self):
        self.ledger.conn.close()
        self.temp.cleanup()

    async def test_callback_uses_observed_quote_and_net_costs_once(self):
        detector = AsyncSpreadDetector(min_spread_bps=0)
        opp = detector.evaluate_spread(4.0, 4.2, 0.10, 100)
        proposal = await detector.stage_mcp_proposal(opp, 20)
        result = await self.pipeline.handle_proposal_callback(proposal)
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["ledger_result"]["net_profit_usd"], proposal.expected_net_profit_usd, places=4)
        row = self.ledger.conn.execute("SELECT rate,evidence_json FROM journal_entries").fetchone()
        self.assertEqual(row[0], 4.0)
        fill = json.loads(row[1])["paper_execution"]
        self.assertEqual(fill["principal_brl"], 400)
        self.assertGreater(fill["modeled_costs_usd"], 0)
        self.assertTrue(self.ledger.reconcile()["balanced"])

    async def test_restart_after_commit_before_ack_does_not_duplicate_money(self):
        proposal = ArbitrageProposal("recover-1", 1, "USDT/BRL", "buy", 100, 5.1, 1, 20,
                                     True, "STAGED_FOR_MCP_EXECUTION", net_spread_bps=100,
                                     estimated_slippage=0.1, fiat_ask=5.0)
        path = self.root / "events.db"
        first = DurableEventBus(path)

        async def interrupted(_, payload):
            await self.pipeline.execute_pipeline_turn(ArbitrageProposal(**payload))
            raise RuntimeError("crash before acknowledgement")

        first.subscribe("agent.proposals", interrupted, consumer="accounting")
        with self.assertRaises(RuntimeError):
            await first.publish("agent.proposals", asdict(proposal))
        first.conn.close()
        second = DurableEventBus(path)

        async def recovered(_, payload):
            result = await self.pipeline.execute_pipeline_turn(ArbitrageProposal(**payload))
            self.assertEqual(result["status"], "DUPLICATE_PROPOSAL")

        second.subscribe("agent.proposals", recovered, consumer="accounting")
        await second.recover()
        await second.recover()
        self.assertEqual(self.ledger.get_summary()["total_operacoes"], 1)
        self.assertEqual(second.conn.execute("SELECT COUNT(*) FROM acknowledgements").fetchone()[0], 1)
        second.conn.close()

    async def test_persisted_bus_keeps_independent_consumer_acknowledgements(self):
        bus = DurableEventBus(self.root / "events.db")
        calls = []

        async def good(topic, payload):
            calls.append(payload)

        async def bad(topic, payload):
            raise RuntimeError("unavailable")

        bus.subscribe("x", good, "good")
        bus.subscribe("x", bad, "bad")
        with self.assertRaises(RuntimeError):
            await bus.publish("x", {"value": 1})
        with self.assertRaises(RuntimeError):
            await bus.recover()
        self.assertEqual(len(calls), 1)
        bus.conn.close()

    async def test_rejection_is_persistent(self):
        self.orchestrator.trigger_kill_switch("test")
        proposal = ArbitrageProposal("reject-1", 1, "USDT/BRL", "buy", 100, 5, 1, 20, True, "ready")
        result = await self.pipeline.execute_pipeline_turn(proposal)
        self.assertEqual(result["status"], "ABORTED_BY_KILL_SWITCH")
        self.assertEqual(self.ledger.conn.execute("SELECT COUNT(*) FROM paper_decisions").fetchone()[0], 1)
        self.assertEqual(self.ledger.get_summary()["total_operacoes"], 0)

    async def test_nonfinite_spread_rejection_is_serializable_and_persistent(self):
        proposal = ArbitrageProposal("invalid-nan", 1, "USDT/BRL", "buy", 100, 5, 1, 20,
                                     True, "ready", net_spread_bps=float("nan"), estimated_slippage=0.1)
        result = await self.pipeline.execute_pipeline_turn(proposal)
        self.assertEqual(result["status"], "INVALID_PROPOSAL_SPREAD")
        self.assertIsNone(result["spread_bps"])
        self.assertEqual(self.ledger.conn.execute("SELECT COUNT(*) FROM paper_decisions").fetchone()[0], 1)

    async def test_outbox_survives_delivery_failure_after_commit(self):
        self.ledger.record_arbitrage_trade("USDT/BRL", 100, 5, 1, "PAPER", proposal_id="outbox-1")
        with patch.object(self.orchestrator.bus, "publish", side_effect=RuntimeError("offline")):
            with self.assertRaises(RuntimeError):
                await self.pipeline.flush_outbox()
        self.assertEqual(self.ledger.conn.execute("SELECT published FROM paper_outbox").fetchone()[0], 0)
        await self.pipeline.flush_outbox()
        self.assertEqual(self.ledger.conn.execute("SELECT published FROM paper_outbox").fetchone()[0], 1)
        self.assertEqual(self.ledger.get_summary()["total_operacoes"], 1)

    def test_console_and_worker_agree_for_absent_corrupt_and_valid_state(self):
        for contents, active in [(None, True), ('{"active":"no"}', True), ('{', True), ('{"active":false}', False)]:
            if contents is None:
                self.state.unlink(missing_ok=True)
            else:
                self.state.write_text(contents, encoding="utf-8")
            with patch.object(server, "STATE_PATH", str(self.state)):
                self.assertEqual(server.get_system_state()["kill_switch"], active)
            self.assertEqual(JarvisOrchestrator(kill_switch_path=str(self.state)).emergency_stop, active)

    def test_backup_restore_preserves_balances_and_detects_legacy_gaps(self):
        self.ledger.record_arbitrage_trade("USDT/BRL", 100, 5, -1, "PAPER", proposal_id="loss")
        self.assertTrue(self.ledger.reconcile()["balanced"])
        target = backup(self.root / "paper.db", self.root / "snapshot.db")
        restored = AccountingLedger(str(target))
        self.assertEqual(restored.get_summary(), self.ledger.get_summary())
        self.assertTrue(restored.reconcile()["balanced"])
        restored.conn.close()
        with self.ledger.conn:
            self.ledger.conn.execute("DELETE FROM paper_postings")
        self.assertFalse(self.ledger.reconcile()["balanced"])

    def test_drawdown_retains_historical_loss_after_recovery(self):
        report = performance_metrics([10, -20, 30], initial_equity=100)
        self.assertAlmostEqual(report["max_drawdown_pct"], 20 / 110 * 100, places=5)
        self.assertFalse(report["eligible_for_production"])

    def test_zero_variance_and_five_trades_never_promote(self):
        report = performance_metrics([1] * 5)
        self.assertFalse(report["paper_statistical_gate"])
        self.assertFalse(report["eligible_for_production"])
        self.assertIsNone(performance_metrics([0] * 100)["sharpe_per_trade"])

    def test_replay_and_walk_forward_are_reproducible(self):
        orders = [dict(symbol="USDT/BRL", side="buy", amount_usd=100,
                       nominal_price=5, projected_spread_pct=s) for s in (1, -2, 3, 1, 2, 1)]
        self.assertEqual(replay(orders, seed=42), replay(orders, seed=42))
        result = walk_forward(orders, train_size=2, test_size=2)
        self.assertEqual([(w["test_start"], w["test_end"]) for w in result["windows"]], [(2, 4), (4, 6)])

    def test_vault_has_no_plaintext_and_detects_wrong_key_and_tampering(self):
        from cryptography.exceptions import InvalidTag
        path = self.root / "vault.db"
        vault = CredentialVault(path, b"k" * 32)
        vault.put("provider", "sensitive-value")
        self.assertEqual(vault.get("provider"), "sensitive-value")
        self.assertNotIn(b"sensitive-value", path.read_bytes())
        wrong = CredentialVault(path, b"z" * 32)
        with self.assertRaises(InvalidTag):
            wrong.get("provider")
        wrong.conn.close()
        with vault.conn:
            vault.conn.execute("UPDATE credentials SET ciphertext=?", (b"tampered",))
        with self.assertRaises(InvalidTag):
            vault.get("provider")
        vault.conn.close()

    def test_skill_permissions_are_denied_by_default_and_memory_survives_restart(self):
        path = self.root / "episodes.db"
        runtime = SkillRuntime(path)
        runtime.register("reconcile", self.ledger.reconcile, {"ledger:read"})
        with self.assertRaises(PermissionError):
            runtime.invoke("reconcile", {})
        self.assertTrue(runtime.invoke("reconcile", {}, {"ledger:read"})["balanced"])
        runtime.conn.close()
        restarted = SkillRuntime(path)
        self.assertEqual([r[1] for r in restarted.recent("reconcile")], ["COMPLETED", "DENIED"])
        restarted.conn.close()
