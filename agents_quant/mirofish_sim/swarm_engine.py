"""
Swarm Engine — Simulação Multiagente Preditiva (Pilar 2 - Laus Quant)
Extraído cirurgicamente de notebook experimental via @graft-surgical-refactor.

Implementa personas analíticas com pesos heterogêneos para avaliação de viabilidade
de ordens em sandbox, calculando score de consenso e autorização antes da execução.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class SwarmPersona:
    """Representa uma persona do comitê com tolerância a risco e peso no quórum."""
    name: str
    risk_tolerance: float  # 0.0 (aversão estrita) a 1.0 (agressivo)
    bias_weight: float     # Peso no cálculo do consenso (0.0 a 1.0)

    def evaluate(self, spread_pct: float, slippage_pct: float) -> Dict[str, Any]:
        """
        Avalia a viabilidade preditiva da operação sob a ótica desta persona.

        Args:
            spread_pct: Spread bruto ou estimado em porcentagem.
            slippage_pct: Slippage real/projetado pelo scanner L2.

        Returns:
            Dict com 'persona', 'vote' ('BUY' ou 'HOLD') e 'confidence' (0.0 a 1.0).
        """
        liquidez_efetiva = spread_pct - slippage_pct
        aprovado = liquidez_efetiva > (0.5 * (1.0 - self.risk_tolerance))
        confianca = min(1.0, max(0.0, (liquidez_efetiva / 1.5) * self.risk_tolerance))

        return {
            "persona": self.name,
            "vote": "BUY" if aprovado else "HOLD",
            "confidence": round(confianca, 2),
            "effective_spread_pct": round(liquidez_efetiva, 4),
        }


class MiroFishSwarmSimulator:
    """
    Simulador de consenso de enxame preditivo para validação prévia de operações.
    """

    def __init__(self, personas: Optional[List[SwarmPersona]] = None):
        self.personas: List[SwarmPersona] = personas or [
            SwarmPersona(name="Conservative_Risk_Officer", risk_tolerance=0.2, bias_weight=0.4),
            SwarmPersona(name="Macro_Trend_Follower", risk_tolerance=0.6, bias_weight=0.3),
            SwarmPersona(name="HFT_Liquidity_Hunter", risk_tolerance=0.9, bias_weight=0.3),
        ]

    def simulate_consensus(self, spread_pct: float, slippage_pct: float) -> Dict[str, Any]:
        """
        Executa simulação de consenso entre as personas em ambiente isolado (Sandbox).

        Args:
            spread_pct: Spread estimado da janela operacional.
            slippage_pct: Slippage L2 medido pelo OrderbookScanner.

        Returns:
            Dict com 'authorized', 'consensus_score', 'votes_for', 'total_voters' e 'details'.
        """
        votos_favoraveis = 0
        soma_confianca_ponderada = 0.0
        detalhes: List[Dict[str, Any]] = []

        for persona in self.personas:
            resultado = persona.evaluate(spread_pct, slippage_pct)
            detalhes.append(resultado)
            if resultado["vote"] == "BUY":
                votos_favoraveis += 1
            soma_confianca_ponderada += resultado["confidence"] * persona.bias_weight

        consenso_atingido = votos_favoraveis >= 2 and soma_confianca_ponderada >= 0.45

        return {
            "authorized": consenso_atingido,
            "consensus_score": round(soma_confianca_ponderada, 3),
            "votes_for": votos_favoraveis,
            "total_voters": len(self.personas),
            "details": detalhes,
        }


if __name__ == "__main__":
    swarm = MiroFishSwarmSimulator()
    res = swarm.simulate_consensus(spread_pct=0.88, slippage_pct=0.12)
    print("Resultado da Simulação Preditiva Swarm:")
    print(f"Autorizado: {res['authorized']} | Score: {res['consensus_score']*100:.1f}%")
    for d in res["details"]:
        print(f"  - {d['persona']}: {d['vote']} (Confiança: {d['confidence']:.2f})")
