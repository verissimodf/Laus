"""
Gêmeo Digital & Sandboxing (Pilar 7 - Laus)
Paper trading contínuo, motor de shadow exchange e validação estatística de alpha.
"""

from .shadow_exchange import ShadowExchangeEngine, ShadowTradeRecord

__all__ = [
    "ShadowExchangeEngine",
    "ShadowTradeRecord",
]
