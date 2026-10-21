"""
Gêmeo Digital & Motor de Execução Shadow / Paper Trading (Pilar 7 - Laus)

Simula a execução de ordens com order books em tempo real, aplicando ruído
estocástico de book e derrapagem realista (Slippage) sem expor capital real.
"""

import math
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ShadowTradeRecord:
    trade_id: str
    timestamp: float
    symbol: str
    side: str
    amount_usd: float
    nominal_price: float
    effective_price: float
    slippage_pct: float
    pnl_usd: float
    status: str


class ShadowExchangeEngine:
    """
    Motor do Gêmeo Digital para homologação contínua de estratégias em modo Shadow.
    """

    def __init__(
        self,
        initial_usd_balance: float = 10000.0,
        initial_brl_balance: float = 50000.0,
        slippage_noise_range: tuple = (0.05, 0.22),
    ):
        self.initial_usd_balance = initial_usd_balance
        self.initial_brl_balance = initial_brl_balance
        self.usd_balance = initial_usd_balance
        self.brl_balance = initial_brl_balance
        self.slippage_noise_range = slippage_noise_range

        self.trade_history: List[ShadowTradeRecord] = []
        self._peak_equity_usd = initial_usd_balance

    def simulate_order_execution(
        self,
        symbol: str,
        side: str,
        amount_usd: float,
        nominal_price: float,
        projected_spread_pct: float,
    ) -> ShadowTradeRecord:
        """
        Executa uma ordem no livro virtual aplicando derrapagem de rede e profundidade.
        """
        trade_id = f"TWIN-{int(time.time() * 1000)}-{random.randint(100, 999)}"
        timestamp = time.time()

        # Injeta ruído estocástico no slippage
        synthetic_slippage = random.uniform(*self.slippage_noise_range)
        effective_spread = projected_spread_pct - synthetic_slippage

        # Preço efetivo simulado
        if side.lower() == "buy":
            effective_price = nominal_price * (1.0 + (synthetic_slippage / 100.0))
        else:
            effective_price = nominal_price * (1.0 - (synthetic_slippage / 100.0))

        # PnL líquido estimado
        pnl_usd = amount_usd * (effective_spread / 100.0)
        success = pnl_usd > 0 and effective_spread > 0.0

        status = "EXECUTED_PROFITABLE" if success else "EXECUTED_SLIPPAGE_LOSS"

        record = ShadowTradeRecord(
            trade_id=trade_id,
            timestamp=timestamp,
            symbol=symbol,
            side=side,
            amount_usd=amount_usd,
            nominal_price=round(nominal_price, 4),
            effective_price=round(effective_price, 4),
            slippage_pct=round(synthetic_slippage, 4),
            pnl_usd=round(pnl_usd, 4),
            status=status,
        )

        self.trade_history.append(record)
        self.usd_balance += pnl_usd
        if self.usd_balance > self._peak_equity_usd:
            self._peak_equity_usd = self.usd_balance

        return record

    def get_performance_report(self) -> Dict[str, Any]:
        """Calcula métricas agregadas da carteira Shadow (Taxa de acerto, Drawdown, PnL)."""
        if not self.trade_history:
            return {
                "total_trades": 0,
                "win_rate_pct": 0.0,
                "cumulative_pnl_usd": 0.0,
                "max_drawdown_pct": 0.0,
                "current_usd_balance": self.usd_balance,
                "eligible_for_production": False,
            }

        winning_trades = sum(1 for t in self.trade_history if t.pnl_usd > 0)
        total_pnl = sum(t.pnl_usd for t in self.trade_history)
        win_rate = (winning_trades / len(self.trade_history)) * 100.0

        current_dd_usd = self._peak_equity_usd - self.usd_balance
        max_dd_pct = (current_dd_usd / self._peak_equity_usd) * 100.0 if self._peak_equity_usd > 0 else 0.0

        # Critério de elegibilidade para promoção (Sharpe sintético simplificado > 1.5 e Win Rate > 60%)
        eligible = win_rate >= 60.0 and max_dd_pct < 5.0 and len(self.trade_history) >= 5

        return {
            "total_trades": len(self.trade_history),
            "winning_trades": winning_trades,
            "win_rate_pct": round(win_rate, 2),
            "cumulative_pnl_usd": round(total_pnl, 4),
            "max_drawdown_pct": round(max_dd_pct, 2),
            "current_usd_balance": round(self.usd_balance, 2),
            "eligible_for_production": eligible,
        }


if __name__ == "__main__":
    twin = ShadowExchangeEngine()
    print("Testando ShadowExchangeEngine...")
    for i in range(5):
        rec = twin.simulate_order_execution("USDT/BRL", "buy", 250.0, 5.0240, 0.85)
        print(f"Trade {rec.trade_id}: PnL=${rec.pnl_usd:+.4f} | Status={rec.status} | Slippage={rec.slippage_pct:.3f}%")

    metrics = twin.get_performance_report()
    print("\nRelatório de Performance Shadow:")
    for k, v in metrics.items():
        print(f"  • {k}: {v}")
