import os
import unittest
from unittest.mock import patch

from gateway_vault.mcp_servers.laus_mcp import LausMCPServer
from gateway_vault.mcp_servers.official_server import (
    market_scan_depth,
    mcp,
    simulate_swarm,
    validate_order_proposal,
    verify_bank,
)


class TestOfficialMCPServer(unittest.TestCase):
    def test_official_server_registers_safe_tool_handlers(self):
        self.assertTrue(callable(mcp.run))
        self.assertTrue(callable(market_scan_depth))
        self.assertTrue(callable(simulate_swarm))
        self.assertTrue(callable(validate_order_proposal))
        self.assertTrue(callable(verify_bank))

    def test_mcp_guardrail_uses_environment_risk_limits(self):
        with patch.dict(
            os.environ,
            {"MAX_ORDER_USD": "80.0", "MAX_SLIPPAGE_PCT": "0.15"},
        ):
            backend = LausMCPServer(db_path=":memory:")

        self.assertEqual(backend.guardrail.max_order_usd, 80.0)
        self.assertEqual(backend.guardrail.max_slippage_pct, 0.15)

    def test_legacy_trade_settlement_tool_is_disabled(self):
        backend = LausMCPServer(db_path=":memory:")
        advertised_names = {tool["name"] for tool in backend.list_tools()}

        self.assertNotIn("mcp_execute_hedged_trade", advertised_names)
        with self.assertRaisesRegex(RuntimeError, "não estão implementadas"):
            backend.handle_call_tool(
                "mcp_execute_hedged_trade",
                {
                    "symbol": "USDT-BRL",
                    "amount_usd": 10.0,
                    "rate": 5.0,
                    "spread_pct": 0.5,
                    "source": "test",
                },
            )

    def test_mcp_proposal_validation_rejects_json_booleans_and_strings(self):
        backend = LausMCPServer(db_path=":memory:")

        for invalid_amount in (True, "100"):
            with self.subTest(amount=invalid_amount):
                result = backend.handle_call_tool(
                    "mcp_stage_order",
                    {
                        "symbol": "USDT-BRL",
                        "amount_usd": invalid_amount,
                        "estimated_slippage": 0.1,
                    },
                )
                self.assertEqual(result["status"], "REJECTED_BY_GUARDRAIL")
                self.assertFalse(result["guardrail_authorized"])

    def test_mcp_numeric_tools_reject_non_finite_and_boolean_values(self):
        backend = LausMCPServer(db_path=":memory:")

        for invalid in (True, float("nan"), float("inf"), "1.0"):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                backend.handle_call_tool(
                    "mcp_market_scan_depth",
                    {"symbol": "USDT-BRL", "volume_usd": invalid},
                )
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                backend.handle_call_tool(
                    "mcp_swarm_evaluate",
                    {"spread_pct": invalid, "slippage_pct": 0.1},
                )

    def test_market_scan_exposes_source_freshness_provenance(self):
        class Scanner:
            @staticmethod
            def fetch_live_orderbook(symbol):
                return {
                    "source": "Mercado Bitcoin (Live Book)",
                    "symbol": symbol,
                    "bids": [[5.0, 1000.0]],
                    "asks": [[5.1, 1000.0]],
                    "timestamp": 100,
                    "source_timestamp": 99,
                    "received_at": 100.0,
                    "freshness_verified": True,
                }

            @staticmethod
            def calculate_vwap_slippage(levels, amount):
                return levels[0][0], levels[0][0], 0.0

        backend = LausMCPServer(scanner=Scanner(), db_path=":memory:")
        result = backend.handle_call_tool(
            "mcp_market_scan_depth",
            {"symbol": "USDT-BRL", "volume_usd": 250.0},
        )

        self.assertEqual(result["source_timestamp"], 99)
        self.assertEqual(result["received_at"], 100.0)
        self.assertTrue(result["freshness_verified"])

    def test_proposal_validation_does_not_submit_order(self):
        approved = validate_order_proposal("USDT-BRL", 100.0, 0.1)
        rejected = validate_order_proposal("USDT-BRL", -1.0, 0.1)

        self.assertEqual(approved["status"], "PROPOSAL_VALIDATED")
        self.assertTrue(approved["guardrail_authorized"])
        self.assertFalse(approved["order_submitted"])
        self.assertEqual(approved["validation_scope"], "PER_ORDER_LIMITS_ONLY")
        self.assertFalse(approved["daily_paper_limits_checked"])
        self.assertEqual(rejected["status"], "REJECTED_BY_GUARDRAIL")
        self.assertFalse(rejected["guardrail_authorized"])
        self.assertEqual(rejected["validation_scope"], "PER_ORDER_LIMITS_ONLY")
        self.assertFalse(rejected["daily_paper_limits_checked"])


if __name__ == "__main__":
    unittest.main()
