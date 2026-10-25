"""
Laus Execution Gateway - Risk Guardrail (Pilar 3)
Middleware determinístico que bloqueia ordens fora dos limites de segurança.
"""
import math
import os
from pathlib import Path

from dotenv import load_dotenv


class RiskGuardrailException(Exception):
    pass


class RiskGuardrail:
    def __init__(
        self,
        max_order_usd: float | None = None,
        max_slippage_pct: float | None = None,
        max_daily_drawdown_usd: float | None = None,
        max_daily_paper_notional_usd: float | None = None,
    ):
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
        if max_order_usd is None:
            max_order_usd = float(os.environ.get("MAX_ORDER_USD", "500.0"))
        if max_slippage_pct is None:
            max_slippage_pct = float(os.environ.get("MAX_SLIPPAGE_PCT", "0.5"))
        if max_daily_drawdown_usd is None:
            max_daily_drawdown_usd = float(os.environ.get("MAX_DAILY_DRAWDOWN_USD", "250.0"))
        if max_daily_paper_notional_usd is None:
            max_daily_paper_notional_usd = float(
                os.environ.get("MAX_DAILY_PAPER_NOTIONAL_USD", "2500.0")
            )
        self.max_order_usd = self._finite_number("max_order_usd", max_order_usd)
        self.max_slippage_pct = self._finite_number("max_slippage_pct", max_slippage_pct)
        self.max_daily_drawdown_usd = self._finite_number(
            "max_daily_drawdown_usd", max_daily_drawdown_usd
        )
        self.max_daily_paper_notional_usd = self._finite_number(
            "max_daily_paper_notional_usd", max_daily_paper_notional_usd
        )
        if self.max_order_usd <= 0:
            raise ValueError("max_order_usd deve ser positivo")
        if self.max_slippage_pct < 0:
            raise ValueError("max_slippage_pct não pode ser negativo")
        if self.max_daily_drawdown_usd <= 0:
            raise ValueError("max_daily_drawdown_usd deve ser positivo")
        if self.max_daily_paper_notional_usd <= 0:
            raise ValueError("max_daily_paper_notional_usd deve ser positivo")

    @staticmethod
    def _finite_number(name: str, value: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RiskGuardrailException(f"{name} deve ser um número")
        if not math.isfinite(value):
            raise RiskGuardrailException(f"{name} deve ser finito")
        return float(value)

    def validate_order(
        self,
        symbol: str,
        amount_usd: float,
        estimated_slippage: float,
        daily_realized_pnl_usd: float | None = None,
        daily_paper_notional_usd: float | None = None,
    ) -> bool:
        if not isinstance(symbol, str) or not symbol.strip():
            raise RiskGuardrailException("symbol deve ser uma string não vazia")

        amount_usd = self._finite_number("amount_usd", amount_usd)
        estimated_slippage = self._finite_number("estimated_slippage", estimated_slippage)

        if amount_usd <= 0:
            raise RiskGuardrailException("amount_usd deve ser positivo")
        if estimated_slippage < 0:
            raise RiskGuardrailException("estimated_slippage não pode ser negativo")
        if amount_usd > self.max_order_usd:
            raise RiskGuardrailException(
                f"Ordem de ${amount_usd} excede o limite máximo permitido de ${self.max_order_usd}"
            )
        if estimated_slippage > self.max_slippage_pct:
            raise RiskGuardrailException(
                f"Slippage estimado de {estimated_slippage}% excede a tolerância de {self.max_slippage_pct}%"
            )
        if daily_paper_notional_usd is not None:
            daily_paper_notional_usd = self._finite_number(
                "daily_paper_notional_usd", daily_paper_notional_usd
            )
            if daily_paper_notional_usd < 0:
                raise RiskGuardrailException("daily_paper_notional_usd não pode ser negativo")
            projected_daily_notional = daily_paper_notional_usd + amount_usd
            if projected_daily_notional > self.max_daily_paper_notional_usd:
                raise RiskGuardrailException(
                    "Limite diário de volume paper atingido: "
                    f"volume projetado=${projected_daily_notional} | "
                    f"limite=${self.max_daily_paper_notional_usd}"
                )
        if daily_realized_pnl_usd is not None:
            daily_realized_pnl_usd = self._finite_number(
                "daily_realized_pnl_usd", daily_realized_pnl_usd
            )
            if daily_realized_pnl_usd <= -self.max_daily_drawdown_usd:
                raise RiskGuardrailException(
                    "Limite de perda diária paper atingido: "
                    f"PnL=${daily_realized_pnl_usd} | limite=-${self.max_daily_drawdown_usd}"
                )
        return True
