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
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any, Dict, Optional


class DuplicateProposalError(ValueError):
    """Raised when a paper proposal has already been recorded."""


class DailyPaperNotionalLimitError(ValueError):
    """Raised when an atomic paper-ledger write would exceed the UTC daily notional cap."""


class DailyPaperDrawdownLimitError(ValueError):
    """Raised when the UTC daily paper drawdown has already reached its configured cap."""


class AccountingLedger:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA busy_timeout=10000")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS paper_postings (
                    entry_id INTEGER NOT NULL, account TEXT NOT NULL,
                    amount_microusd INTEGER NOT NULL,
                    PRIMARY KEY(entry_id, account),
                    FOREIGN KEY(entry_id) REFERENCES journal_entries(id)
                );
                CREATE TABLE IF NOT EXISTS paper_decisions (
                    id INTEGER PRIMARY KEY, proposal_id TEXT NOT NULL,
                    timestamp INTEGER NOT NULL, result_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS paper_outbox (
                    entry_id INTEGER PRIMARY KEY, payload TEXT NOT NULL,
                    published INTEGER NOT NULL DEFAULT 0
                );
            """)
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
        max_daily_notional_usd: Optional[float] = None,
        max_daily_drawdown_usd: Optional[float] = None,
        fee_usd: Optional[float] = None,
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
        for name, value in (
            ("max_daily_notional_usd", max_daily_notional_usd),
            ("max_daily_drawdown_usd", max_daily_drawdown_usd),
        ):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} deve ser positivo e finito")
        if proposal_id is not None:
            if not isinstance(proposal_id, str) or not proposal_id.strip():
                raise ValueError("proposal_id deve ser uma string não vazia")
            proposal_id = proposal_id.strip()
        gross_profit = amount_usd * (spread_pct / 100.0)
        fee = amount_usd * 0.001 if fee_usd is None else fee_usd
        if isinstance(fee, bool) or not isinstance(fee, (int, float)) or not math.isfinite(fee) or fee < 0:
            raise ValueError("fee_usd deve ser finito e não negativo")
        net = gross_profit - fee
        tax_brl = (net * rate) * 0.15 if net > 0 else 0.0
        if not all(math.isfinite(v) for v in (gross_profit, net, tax_brl)):
            raise ValueError("Derived paper amounts must be finite")
        try:
            evidence_json = (
                json.dumps(evidence, sort_keys=True, allow_nan=False)
                if evidence is not None
                else None
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("evidence deve ser serializável em JSON estrito") from exc
        timestamp = int(time.time())
        try:
            with self.conn:
                if max_daily_notional_usd is not None or max_daily_drawdown_usd is not None:
                    # Lock the SQLite writer before reading limits and keep the read + insert atomic.
                    self.conn.execute("BEGIN IMMEDIATE")
                    now_utc = datetime.fromtimestamp(timestamp, timezone.utc)
                    day_start = int(
                        now_utc.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                    )
                    daily_row = self.conn.execute(
                        "SELECT COALESCE(SUM(amount_usd), 0), "
                        "COALESCE(SUM(net_profit_usd), 0) FROM journal_entries "
                        "WHERE timestamp >= ?",
                        (day_start,),
                    ).fetchone()
                    current_notional, daily_pnl = daily_row
                    if max_daily_notional_usd is not None:
                        projected_notional = current_notional + amount_usd
                        if projected_notional > max_daily_notional_usd:
                            raise DailyPaperNotionalLimitError(
                                "Limite diário de volume paper atingido: "
                                f"volume projetado={projected_notional} USD | "
                                f"limite={max_daily_notional_usd} USD"
                            )
                    if max_daily_drawdown_usd is not None and daily_pnl <= -max_daily_drawdown_usd:
                        raise DailyPaperDrawdownLimitError(
                            "Limite de perda diária paper atingido: "
                            f"PnL={daily_pnl} USD | limite=-{max_daily_drawdown_usd} USD"
                        )
                cur = self.conn.execute(
                    """
                    INSERT INTO journal_entries (
                        timestamp, symbol, side, amount_usd, rate, gross_profit_usd,
                        fee_usd, net_profit_usd, tax_provision_brl, source, evidence_json,
                        proposal_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        timestamp, symbol, "ARBITRAGE", amount_usd, rate,
                        gross_profit, fee, net, tax_brl, source, evidence_json, proposal_id,
                    ),
                )
                def micro(value):
                    return int((Decimal(str(value)) * 1_000_000).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
                gross_micro, fee_micro = micro(gross_profit), micro(fee)
                # Signed debit amounts: assets + expenses - income = 0.
                self.conn.executemany(
                    "INSERT INTO paper_postings VALUES (?, ?, ?)",
                    [(cur.lastrowid, "Asset:PaperCash:USD", gross_micro - fee_micro),
                     (cur.lastrowid, "Expense:PaperFees:USD", fee_micro),
                     (cur.lastrowid, "Income:PaperArbitrage:USD", -gross_micro)],
                )
                self.conn.execute("INSERT INTO paper_outbox(entry_id,payload) VALUES (?,?)",
                                  (cur.lastrowid, json.dumps({"proposal_id": proposal_id,
                                   "ledger_entry_id": cur.lastrowid, "net_profit_usd": round(net, 4),
                                   "scope": "paper"}, allow_nan=False)))
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

    def record_decision(self, proposal_id, result):
        payload = json.dumps(result, sort_keys=True, allow_nan=False)
        with self.conn:
            self.conn.execute("INSERT INTO paper_decisions(proposal_id,timestamp,result_json) VALUES (?,?,?)",
                              (proposal_id, int(time.time()), payload))

    def reconcile(self):
        unbalanced = self.conn.execute(
            "SELECT entry_id FROM paper_postings GROUP BY entry_id HAVING SUM(amount_microusd) <> 0"
        ).fetchall()
        uncovered = self.conn.execute(
            "SELECT COUNT(*) FROM journal_entries j WHERE NOT EXISTS "
            "(SELECT 1 FROM paper_postings p WHERE p.entry_id=j.id)"
        ).fetchone()[0]
        return {"balanced": not unbalanced and uncovered == 0,
                "unbalanced_entries": [r[0] for r in unbalanced], "legacy_uncovered_entries": uncovered}

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
