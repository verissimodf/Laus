import unittest

from agents_quant.strategies.orderbook_scanner import OrderbookScanner


class TestOrderbookScannerValidation(unittest.TestCase):
    def test_rejects_invalid_market_symbols(self):
        for symbol in ("", " USDT-BRL", "USDT-BRL&symbol=BTC-BRL", "USDT/BRL", "A-B-C"):
            with self.subTest(symbol=symbol), self.assertRaises(ValueError):
                OrderbookScanner.fetch_live_orderbook(symbol)

    def test_rejects_non_positive_or_non_finite_levels(self):
        invalid_books = (
            [[float("nan"), 1.0]],
            [[5.0, float("inf")]],
            [[0.0, 1.0]],
            [[5.0, -1.0]],
            [[5.0]],
        )
        for book in invalid_books:
            with self.subTest(book=book), self.assertRaises(ValueError):
                OrderbookScanner.calculate_vwap_slippage(book, 10.0)

    def test_rejects_target_volume_exceeding_available_depth(self):
        with self.assertRaisesRegex(ValueError, "Liquidez insuficiente"):
            OrderbookScanner.calculate_vwap_slippage(
                [[5.0, 4.0], [5.1, 3.0]],
                10.0,
            )

    def test_accepts_target_fully_covered_by_multiple_levels(self):
        top, vwap, slippage = OrderbookScanner.calculate_vwap_slippage(
            [[5.0, 4.0], [5.1, 6.0]],
            10.0,
        )
        self.assertEqual(top, 5.0)
        self.assertEqual(vwap, 5.06)
        self.assertAlmostEqual(slippage, 1.2)

    def test_rejects_non_positive_and_non_finite_target_volume(self):
        for volume in (True, 0, -1.0, float("nan"), float("inf")):
            with self.subTest(volume=volume), self.assertRaises(ValueError):
                OrderbookScanner.calculate_vwap_slippage([[5.0, 10.0]], volume)

    def test_parses_numeric_exchange_levels_and_rejects_malformed_sides(self):
        levels = OrderbookScanner._parse_levels([["5.01", "100"]], "asks")
        self.assertEqual(levels, [[5.01, 100.0]])
        with self.assertRaises(ValueError):
            OrderbookScanner._parse_levels([], "asks")


if __name__ == "__main__":
    unittest.main()
