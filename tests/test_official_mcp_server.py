import unittest

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

    def test_proposal_validation_does_not_submit_order(self):
        approved = validate_order_proposal("USDT-BRL", 100.0, 0.1)
        rejected = validate_order_proposal("USDT-BRL", -1.0, 0.1)

        self.assertEqual(approved["status"], "APPROVED")
        self.assertTrue(approved["guardrail_authorized"])
        self.assertEqual(rejected["status"], "REJECTED_BY_GUARDRAIL")
        self.assertFalse(rejected["guardrail_authorized"])


if __name__ == "__main__":
    unittest.main()
