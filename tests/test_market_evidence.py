import json
import unittest

from agents_quant.arbitrators.spread_detector import AsyncSpreadDetector
from accounting_ledger.ledger_engine import AccountingLedger


class TestMarketEvidence(unittest.IsolatedAsyncioTestCase):
    async def test_evidence_fingerprint_is_stable(self):
        detector = AsyncSpreadDetector()
        evidence = {
            "source": "Mercado Bitcoin (Live Book)",
            "symbol": "USDT-BRL",
            "bids": [[5.0, 100.0]],
            "asks": [[5.01, 100.0]],
        }

        first = detector._evidence_hash(evidence)
        second = detector._evidence_hash(dict(reversed(list(evidence.items()))))

        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)

    async def test_poll_cycle_records_source_and_freshness_verification(self):
        detector = AsyncSpreadDetector(min_spread_bps=1e9)

        async def fake_fiat():
            return {
                "source": "AwesomeAPI",
                "ask": 5.0,
                "timestamp": "1761390000",
                "received_at": 1761390001.0,
                "content_sha256": "a" * 64,
                "freshness_verified": True,
            }

        async def fake_book(fiat_ask, target_volume_usd):
            detector._last_book_evidence = {
                "source": "Mercado Bitcoin (Live Book)",
                "source_timestamp": None,
                "received_at": 1761390002.0,
                "source_timestamp_present": False,
                "freshness_verified": False,
                "content_sha256": "b" * 64,
            }
            return 5.2, 0.1, 40.0

        detector.fetch_fiat_quote_async = fake_fiat
        detector.fetch_crypto_book_depth_async = fake_book
        await detector.poll_cycle()

        evidence = detector.detected_history[0].market_evidence
        self.assertEqual(evidence["fiat_quote"]["source"], "AwesomeAPI")
        self.assertTrue(evidence["fiat_quote"]["freshness_verified"])
        self.assertEqual(
            evidence["orderbook"]["source"],
            "Mercado Bitcoin (Live Book)",
        )
        self.assertFalse(evidence["orderbook"]["freshness_verified"])
        self.assertEqual(len(evidence["orderbook"]["content_sha256"]), 64)

    async def test_market_evidence_flows_into_proposal(self):
        evidence = {
            "fiat_quote": {
                "source": "AwesomeAPI",
                "source_timestamp": "1761390000",
                "content_sha256": "a" * 64,
            },
            "orderbook": {
                "source": "Mercado Bitcoin (Live Book)",
                "source_timestamp": "1761390001",
                "content_sha256": "b" * 64,
            },
        }
        detector = AsyncSpreadDetector()
        opportunity = detector.evaluate_spread(
            p_fiat=5.0,
            p_crypto=5.1,
            slippage_pct=0.1,
            volume_usd=100.0,
            market_evidence=evidence,
        )

        proposal = await detector.stage_mcp_proposal(opportunity, latency_ms=50.0)

        self.assertEqual(proposal.market_evidence, evidence)

    async def test_existing_ledger_schema_migrates_without_losing_entries(self):
        import os
        import sqlite3
        import tempfile

        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        ledger = None
        try:
            conn = sqlite3.connect(handle.name)
            conn.execute("""
                CREATE TABLE journal_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER, symbol TEXT, side TEXT, amount_usd REAL,
                    rate REAL, gross_profit_usd REAL, fee_usd REAL,
                    net_profit_usd REAL, tax_provision_brl REAL, source TEXT
                )
            """)
            conn.execute(
                "INSERT INTO journal_entries (timestamp, symbol, source) VALUES (1, 'USDT-BRL', 'legacy')"
            )
            conn.commit()
            conn.close()

            ledger = AccountingLedger(handle.name)
            columns = {
                row[1] for row in ledger.conn.execute("PRAGMA table_info(journal_entries)")
            }
            row = ledger.conn.execute(
                "SELECT source, evidence_json FROM journal_entries WHERE id = 1"
            ).fetchone()

            self.assertIn("evidence_json", columns)
            self.assertEqual(row, ("legacy", None))
        finally:
            if ledger is not None:
                ledger.conn.close()
            os.remove(handle.name)

    async def test_daily_summary_reads_only_current_utc_day_entries(self):
        ledger = AccountingLedger(":memory:")
        ledger.record_arbitrage_trade(
            symbol="USDT-BRL",
            amount_usd=100.0,
            rate=5.0,
            spread_pct=0.5,
            source="PAPER_SIMULATION_TEST",
        )

        summary = ledger.get_daily_summary()

        self.assertEqual(summary["paper_trade_count"], 1)
        self.assertAlmostEqual(summary["paper_realized_pnl_usd"], 0.4)
        self.assertTrue(summary["date_utc"])

    async def test_ledger_persists_evidence_json(self):
        ledger = AccountingLedger(":memory:")
        evidence = {"orderbook": {"source": "Mercado Bitcoin", "content_sha256": "c" * 64}}

        entry = ledger.record_arbitrage_trade(
            symbol="USDT-BRL",
            amount_usd=100.0,
            rate=5.0,
            spread_pct=0.5,
            source="PAPER_SIMULATION_TEST",
            evidence=evidence,
        )
        row = ledger.conn.execute(
            "SELECT evidence_json FROM journal_entries WHERE id = ?",
            (entry["entry_id"],),
        ).fetchone()

        self.assertEqual(json.loads(row[0]), evidence)
        self.assertEqual(entry["evidence"], evidence)


if __name__ == "__main__":
    unittest.main()
