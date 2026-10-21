"""
MiroFish Swarm Simulator (Pilar 2)
"""
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class SwarmAgentVote:
    persona: str
    approves: bool
    confidence: float
    reason: str

class MiroFishSwarmSimulator:
    def simulate_order_impact(self, symbol: str, amount_usd: float, spread_pct: float) -> Dict[str, Any]:
        votes = [
            SwarmAgentVote("LiquidityProvider_Bot", amount_usd <= 280.0, 0.88, "Volume compativel com profundidade L2"),
            SwarmAgentVote("WhaleMomentum_Bot", spread_pct >= 0.50, 0.82, "Spread compensa volatilidade"),
            SwarmAgentVote("SpreadArbitrageur_Bot", True, 0.91, "Janela de latencia favoravel")
        ]
        total_w = sum(v.confidence for v in votes)
        app_w = sum(v.confidence for v in votes if v.approves)
        score = app_w / total_w
        return {
            "approved": score >= 0.70,
            "consensus_score": round(score, 3),
            "votes": [v.__dict__ for v in votes]
        }
