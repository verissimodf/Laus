"""
Laus Execution Gateway - Risk Guardrail (Pilar 3)
Middleware determinístico que bloqueia ordens fora dos limites de segurança.
"""
import math


class RiskGuardrailException(Exception):
    pass


class RiskGuardrail:
    def __init__(self, max_order_usd: float = 500.0, max_slippage_pct: float = 0.5):
        self.max_order_usd = self._finite_number("max_order_usd", max_order_usd)
        self.max_slippage_pct = self._finite_number("max_slippage_pct", max_slippage_pct)
        if self.max_order_usd <= 0:
            raise ValueError("max_order_usd deve ser positivo")
        if self.max_slippage_pct < 0:
            raise ValueError("max_slippage_pct não pode ser negativo")

    @staticmethod
    def _finite_number(name: str, value: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RiskGuardrailException(f"{name} deve ser um número")
        if not math.isfinite(value):
            raise RiskGuardrailException(f"{name} deve ser finito")
        return float(value)

    def validate_order(self, symbol: str, amount_usd: float, estimated_slippage: float) -> bool:
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
        return True
