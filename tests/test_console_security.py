import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from console_ui import server


class TestConsoleSecurity(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server.app)

    def test_dashboard_requires_authentication(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers.get("www-authenticate"), "Basic")

    def test_missing_config_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.get("/", auth=("operator", "secret"))
        self.assertEqual(response.status_code, 503)

    def test_dashboard_escapes_state_and_labels_paper_values(self):
        with (
            patch.dict(
                os.environ,
                {
                    "LAUS_CONSOLE_USERNAME": "operator",
                    "LAUS_CONSOLE_PASSWORD": "test-secret",
                },
            ),
            patch.object(
                server,
                "get_system_state",
                return_value={
                    "kill_switch": False,
                    "status_reason": "<script>alert('x')</script>",
                },
            ),
            patch.object(
                server,
                "get_db_metrics",
                return_value={"total_trades": 9, "pnl_usd": -1.25, "tax_brl": 0.0},
            ),
        ):
            response = self.client.get("/", auth=("operator", "test-secret"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("<script>", response.text)
        self.assertIn("&lt;script&gt;", response.text)
        self.assertIn(">9</p>", response.text)
        self.assertIn("$-1.2500 USD", response.text)
        self.assertIn("PnL estimado (paper)", response.text)
        self.assertIn("Provisão simulada", response.text)


if __name__ == "__main__":
    unittest.main()
