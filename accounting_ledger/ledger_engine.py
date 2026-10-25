"""
SQLite paper ledger.

Entries may include a JSON evidence envelope. Profit and tax figures are
simulation estimates; this module does not implement statutory accounting.
"""
import json
import math
from datetime import datetime, timezone
import sqlite3
import time
from typing import Any, Dict, Optional


class DuplicateProposalError(ValueError):
    """Raised when a paper proposal has already been recorded."""


class AccountingLedger:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER,
                    symbol TEXT,
                    side TEXT,
                    amount_usd REAL,
                    rate REAL,
                    gross_profit_usd REAL,
                    fee_usd REAL,
                    net_profit_usd REAL,
                    tax_provision_brl REAL,
                    source TEXT,
                    evidence_json TEXT,
                    proposal_id TEXT
                )
            """)
            columns = {
                row[1] for row in self.conn.execute("PRAGMA table_info(journal_entries)")
            }
            if "evidence_json" not in columns:
                self.conn.execute("ALTER TABLE journal_entries ADD COLUMN evidence_json TEXT")
            if "proposal_id" not in columns:
                self.conn.execute("ALTER TABLE journal_entries ADD COLUMN proposal_id TEXT")
            self.conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_journal_entries_proposal_id "
                "ON journal_entries(proposal_id) "
                "WHERE proposal_id IS NOT NULL AND proposal_id <> ''"
            )

    def record_arbitrage_trade(
        self,
        symbol: str,
        amount_usd: float,
        rate: float,
        spread_pct: float,
        source: str,
        evidence: Optional[Dict[str, Any]] = None,
        proposal_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a paper estimate once per proposal ID and its source evidence."""
        for name, value in (
            ("amount_usd", amount_usd),
            ("rate", rate),
            ("spread_pct", spread_pct),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} deve ser um número finito")
        if amount_usd <= 0:
            raise ValueError("amount_usd deve ser positivo")
        if rate <= 0:
            raise ValueError("rate deve ser positivo")
        if proposal_id is not None:
            if not isinstance(proposal_id, str) or not proposal_id.strip():
                raise ValueError("proposal_id deve ser uma string não vazia")
            proposal_id = proposal_id.strip()
        gross_profit = amount_usd * (spread_pct / 100.0)
        fee = amount_usd * 0.001
        net = gross_profit - fee
        tax_brl = (net * rate) * 0.15 if net > 0 else 0.0
        evidence_json = json.dumps(evidence, sort_keys=True, allow_nan=False) if evidence is not None else None
        try:
            with self.conn:
                cur = self.conn.execute(
                    """
                    INSERT INTO journal_entries (
                        timestamp, symbol, side, amount_usd, rate, gross_profit_usd,
                        fee_usd, net_profit_usd, tax_provision_brl, source, evidence_json,
                        proposal_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(time.time()), symbol, "ARBITRAGE", amount_usd, rate,
                        gross_profit, fee, net, tax_brl, source, evidence_json, proposal_id,
                    ),
                )
        except sqlite3.IntegrityError:
            if proposal_id is not None and self.conn.execute(
                "SELECT 1 FROM journal_entries WHERE proposal_id = ?", (proposal_id,)
            ).fetchone():
                raise DuplicateProposalError("proposal_id já registrado") from None
            raise
        return {
            "entry_id": cur.lastrowid,
            "net_profit_usd": round(net, 4),
            "fee_usd": round(fee, 4),
            "tax_provision_brl": round(tax_brl, 2),
            "evidence": evidence,
            "proposal_id": proposal_id,
        }

    def get_daily_summary(self) -> Dict[str, Any]:
        """Return UTC-day paper results; this is not a broker/account balance."""
        now = datetime.now(timezone.utc)
        day_start = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        cur = self.conn.cursor()
        cur.execute(
            "SELECT COUNT(*), COALESCE(SUM(net_profit_usd), 0), "
            "COALESCE(SUM(amount_usd), 0) "
            "FROM journal_entries WHERE timestamp >= ?",
            (day_start,),
        )
        trade_count, daily_pnl, daily_notional = cur.fetchone()
        return {
            "date_utc": now.date().isoformat(),
            "paper_trade_count": trade_count,
            "paper_realized_pnl_usd": round(daily_pnl, 4),
            "paper_daily_notional_usd": round(daily_notional, 4),
        }

    def get_summary(self) -> Dict[str, Any]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT COUNT(*), COALESCE(SUM(net_profit_usd), 0), "
            "COALESCE(SUM(tax_provision_brl), 0) FROM journal_entries"
        )
        total_ops, total_net, total_tax = cur.fetchone()
        return {
            "total_operacoes": total_ops,
            "lucro_liquido_usd": round(total_net, 4),
            "provisao_ir_brl": round(total_tax, 2),
        }
