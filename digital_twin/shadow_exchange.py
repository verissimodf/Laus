"""
Gêmeo Digital & Motor de Execução Shadow / Paper Trading (Pilar 7 - Laus)

Simula a execução de ordens com order books em tempo real, aplicando ruído
estocástico de book e derrapagem realista (Slippage) sem expor capital real.
"""

import math
import random
import time
import statistics
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
        seed: Optional[int] = None,
    ):
        self.initial_usd_balance = initial_usd_balance
        self.initial_brl_balance = initial_brl_balance
        self.usd_balance = initial_usd_balance
        self.brl_balance = initial_brl_balance
        self.slippage_noise_range = slippage_noise_range
        if not math.isfinite(initial_usd_balance) or initial_usd_balance <= 0:
            raise ValueError("initial_usd_balance must be positive and finite")
        self._rng = random.Random(seed)

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
        if side.lower() not in ("buy", "sell"):
            raise ValueError("side must be buy or sell")
        for value in (amount_usd, nominal_price, projected_spread_pct):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("Order inputs must be finite numbers")
        if amount_usd <= 0 or nominal_price <= 0 or amount_usd > self.usd_balance:
            raise ValueError("Invalid amount, price or insufficient paper liquidity")
        trade_id = f"TWIN-{len(self.trade_history) + 1}"
        timestamp = time.time()

        # Injeta ruído estocástico no slippage
        synthetic_slippage = self._rng.uniform(*self.slippage_noise_range)
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
        self.usd_balance += record.pnl_usd
        if self.usd_balance > self._peak_equity_usd:
            self._peak_equity_usd = self.usd_balance

        return record

    def get_performance_report(self) -> Dict[str, Any]:
        """Calcula métricas agregadas da carteira Shadow (Taxa de acerto, Drawdown, PnL)."""
        report = performance_metrics([t.pnl_usd for t in self.trade_history], self.initial_usd_balance)
        report["current_usd_balance"] = round(self.usd_balance, 4)
        return report


def performance_metrics(pnls, initial_equity=10000.0):
    """Sample Sharpe per trade (not annualized); historical peak-to-trough drawdown."""
    equity = peak = float(initial_equity)
    if not math.isfinite(equity) or equity <= 0:
        raise ValueError("initial_equity must be positive")
    returns, max_dd = [], 0.0
    for pnl in pnls:
        if isinstance(pnl, bool) or not isinstance(pnl, (int, float)) or not math.isfinite(pnl):
            raise ValueError("PnL must be finite")
        if equity <= 0:
            raise ValueError("Insolvent paper trajectory")
        returns.append(pnl / equity)
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak * 100)
    deviation = statistics.stdev(returns) if len(returns) > 1 else 0
    sharpe = statistics.mean(returns) / deviation if deviation > 0 else None
    return {"total_trades": len(pnls), "cumulative_pnl_usd": round(sum(pnls), 4),
            "win_rate_pct": sum(p > 0 for p in pnls) / len(pnls) * 100 if pnls else 0,
            "max_drawdown_pct": round(max_dd, 6), "sharpe_per_trade": sharpe,
            "sharpe_basis": "sample returns per trade, risk-free=0, not annualized",
            "paper_statistical_gate": len(pnls) >= 100 and sharpe is not None and sharpe > 1.5 and max_dd < 5,
            "eligible_for_production": False,
            "promotion_blockers": ["LIVE_EXECUTION_DISABLED", "SUPERVISED_ACCEPTANCE_REQUIRED"]}


def replay(orders, seed=0, initial_equity=10000.0):
    engine = ShadowExchangeEngine(initial_usd_balance=initial_equity, seed=seed)
    for order in orders:
        engine.simulate_order_execution(**order)
    return engine.get_performance_report()


def walk_forward(orders, train_size=100, test_size=50, seed=0):
    """Disjoint chronological test windows; no tuning on future observations.

    Runs a fixed strategy, not an optimizer. Each window starts with equal capital.
    """
    if train_size < 2 or test_size < 2:
        raise ValueError("Windows require at least two observations")
    windows = []
    for start in range(train_size, len(orders) - test_size + 1, test_size):
        windows.append({"train_start": start - train_size, "train_end": start,
                        "test_start": start, "test_end": start + test_size,
                        "report": replay(orders[start:start + test_size], seed)})
    return {"windows": windows, "eligible_for_production": False}
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
