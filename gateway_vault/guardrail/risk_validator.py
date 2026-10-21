"""
Laus Execution Gateway - Risk Guardrail (Pilar 3)
Middleware determinístico que bloqueia ordens fora dos limites de segurança.
"""
class RiskGuardrailException(Exception):
    pass

class RiskGuardrail:
    def __init__(self, max_order_usd: float = 500.0, max_slippage_pct: float = 0.5):
        self.max_order_usd = max_order_usd
        self.max_slippage_pct = max_slippage_pct

    def validate_order(self, symbol: str, amount_usd: float, estimated_slippage: float) -> bool:
        if amount_usd > self.max_order_usd:
            raise RiskGuardrailException(
                f"Ordem de ${amount_usd} excede o limite máximo permitido de ${self.max_order_usd}"
            )
        if estimated_slippage > self.max_slippage_pct:
            raise RiskGuardrailException(
                f"Slippage estimado de {estimated_slippage}% excede a tolerância de {self.max_slippage_pct}%"
            )
        return True
