"""
Resilience Edge & Zero-Trust Infrastructure (Pilar 6 - Laus)
Monitoramento de saúde de rede, Circuit Breakers de latência e políticas de autocura.
"""

from .circuit_breaker import LatencyCircuitBreaker, CircuitState, CircuitBreakerStatus

__all__ = [
    "LatencyCircuitBreaker",
    "CircuitState",
    "CircuitBreakerStatus",
]
