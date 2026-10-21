"""
Módulo de Arbitradores Quantitativos do Laus (Pilar 2)
Implementa detectores de spread cambial, triangular e espacial integrados
ao Risk Guardrail (Pilar 3) e conectores macro (Pilar 5).
"""

from .spread_detector import AsyncSpreadDetector, SpreadOpportunity, ArbitrageProposal

__all__ = [
    "AsyncSpreadDetector",
    "SpreadOpportunity",
    "ArbitrageProposal",
]
