import unittest

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

    def test_proposal_validation_does_not_submit_order(self):
        approved = validate_order_proposal("USDT-BRL", 100.0, 0.1)
        rejected = validate_order_proposal("USDT-BRL", -1.0, 0.1)

        self.assertEqual(approved["status"], "PROPOSAL_VALIDATED")
        self.assertTrue(approved["guardrail_authorized"])
        self.assertFalse(approved["order_submitted"])
        self.assertEqual(rejected["status"], "REJECTED_BY_GUARDRAIL")
        self.assertFalse(rejected["guardrail_authorized"])


if __name__ == "__main__":
    unittest.main()
