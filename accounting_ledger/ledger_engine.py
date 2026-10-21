"""
Ledger Engine SQLite (Pilar 8)
"""
import sqlite3
import time
from typing import Dict, Any

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
                    source TEXT
                )
            """)

    def record_arbitrage_trade(self, symbol: str, amount_usd: float, rate: float, spread_pct: float, source: str) -> Dict[str, Any]:
        gross_profit = amount_usd * (spread_pct / 100.0)
        fee = amount_usd * 0.001
        net = gross_profit - fee
        tax_brl = (net * rate) * 0.15 if net > 0 else 0.0
        with self.conn:
            cur = self.conn.execute("""
                INSERT INTO journal_entries (timestamp, symbol, side, amount_usd, rate, gross_profit_usd, fee_usd, net_profit_usd, tax_provision_brl, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (int(time.time()), symbol, "ARBITRAGE", amount_usd, rate, gross_profit, fee, net, tax_brl, source))
        return {
            "entry_id": cur.lastrowid, 
            "net_profit_usd": round(net, 4), 
            "fee_usd": round(fee, 4),
            "tax_provision_brl": round(tax_brl, 2)
        }

    def get_summary(self) -> Dict[str, Any]:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*), COALESCE(SUM(net_profit_usd), 0), COALESCE(SUM(tax_provision_brl), 0) FROM journal_entries")
        total_ops, total_net, total_tax = cur.fetchone()
        return {
            "total_operacoes": total_ops,
            "lucro_liquido_usd": round(total_net, 4),
            "provisao_ir_brl": round(total_tax, 2)
        }
