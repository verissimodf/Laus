"""
MiroFish Swarm Simulator - Orquestrador do Enxame
Executa o debate multiagente e consolida a decisão estatística de sandbox.
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Garante resolução do pacote raiz
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from agents_quant.mirofish_simulator.agents import (
    BullAnalystAgent,
    BearAnalystAgent,
    RiskManagerAgent,
    MacroMarketMakerAgent
)
from agents_quant.mirofish_simulator.environment import MarketSandboxEnvironment

class SwarmOrchestrator:
    def __init__(self, scenario: str = "normal"):
        self.env = MarketSandboxEnvironment(scenario=scenario)
        self.agents = [
            BullAnalystAgent(),
            BearAnalystAgent(),
            RiskManagerAgent(),
            MacroMarketMakerAgent()
        ]

    def run_simulation(
        self,
        opportunity: Dict[str, Any],
        market_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        state = market_state if market_state is not None else self.env.get_current_state()
        evaluations: List[Dict[str, Any]] = []
        
        veto_count = 0
        approve_count = 0
        total_confidence = 0.0

        for agent in self.agents:
            res = agent.evaluate(state, opportunity)
            evaluations.append(res)
            
            if res["vote"] == "VETO":
                veto_count += 1
            elif res["vote"] == "APPROVE":
                approve_count += 1
                
            total_confidence += res["confidence"]

        avg_confidence = total_confidence / len(self.agents) if self.agents else 0.0

        # Regra de Consenso: Se houver qualquer veto ou aprovações menores que 3, a operação é rejeitada no sandbox.
        final_decision = "APPROVED" if (veto_count == 0 and approve_count >= 3) else "REJECTED_BY_SWARM"

        return {
            "scenario": self.env.scenario if market_state is None else "custom_override",
            "market_state": state,
            "final_decision": final_decision,
            "votes_summary": {
                "approves": approve_count,
                "vetos": veto_count,
                "neutral": len(self.agents) - (approve_count + veto_count)
            },
            "average_confidence": round(avg_confidence, 4),
            "agent_evaluations": evaluations
        }
