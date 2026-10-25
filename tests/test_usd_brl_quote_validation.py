import time
import unittest
from unittest.mock import patch

from cognition_skills.skills.macro_brazil.scripts import usd_brl_monitor


class TestUsdBrlQuoteValidation(unittest.TestCase):
    @staticmethod
    def payload(**overrides):
        quote = {
            "bid": "5.00",
            "ask": "5.01",
            "high": "5.10",
            "low": "4.90",
            "pctChange": "0.2",
            "timestamp": str(int(time.time())),
            "create_date": "2026-10-25 12:00:00",
        }
        quote.update(overrides)
        return {"USDBRL": quote}

    def test_accepts_fresh_finite_usd_brl_quote(self):
        with patch.object(usd_brl_monitor, "_http_get_json", return_value=self.payload()):
            quote = usd_brl_monitor.fetch_usd_brl_quote()

        self.assertEqual(quote["pair"], "USD-BRL")
        self.assertGreater(quote["ask"], quote["bid"])

    def test_rejects_missing_stale_future_and_non_finite_timestamps(self):
        invalid_timestamps = (
            None,
            str(int(time.time()) - 121),
            str(int(time.time()) + 3),
            "nan",
        )
        for timestamp in invalid_timestamps:
            with self.subTest(timestamp=timestamp):
                with patch.object(
                    usd_brl_monitor,
                    "_http_get_json",
                    return_value=self.payload(timestamp=timestamp),
                ), self.assertRaises(ValueError):
                    usd_brl_monitor.fetch_usd_brl_quote()

    def test_rejects_non_finite_or_crossed_prices(self):
        for overrides in (
            {"ask": "inf"},
            {"bid": "0"},
            {"bid": "5.02", "ask": "5.01"},
            {"high": "4.8", "low": "4.9"},
        ):
            with self.subTest(overrides=overrides):
                with patch.object(
                    usd_brl_monitor,
                    "_http_get_json",
                    return_value=self.payload(**overrides),
                ), self.assertRaises(ValueError):
                    usd_brl_monitor.fetch_usd_brl_quote()


if __name__ == "__main__":
    unittest.main()
