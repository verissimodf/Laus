"""
Testes Automatizados para o MiroFish Swarm Simulator
Valida o comportamento do enxame em cenários normais, alta volatilidade e flash crash.
"""

import sys
import unittest
from pathlib import Path

# Garante resolução do pacote raiz independentemente do ponto de invocação
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from agents_quant.mirofish_simulator.swarm_orchestrator import SwarmOrchestrator

class TestMiroFishSwarm(unittest.TestCase):

    def setUp(self):
        self.standard_opportunity = {
            "net_spread_bps": 75,
            "estimated_slippage": 0.15,
            "amount_usd": 250.0
        }

    def test_normal_scenario_approval(self):
        orchestrator = SwarmOrchestrator(scenario="normal")
        result = orchestrator.run_simulation(self.standard_opportunity)
        
        self.assertEqual(result["final_decision"], "APPROVED")
        self.assertEqual(result["votes_summary"]["vetos"], 0)

    def test_flash_crash_scenario_veto(self):
        orchestrator = SwarmOrchestrator(scenario="flash_crash")
        result = orchestrator.run_simulation(self.standard_opportunity)
        
        self.assertEqual(result["final_decision"], "REJECTED_BY_SWARM")
        self.assertGreater(result["votes_summary"]["vetos"], 0)

    def test_risk_manager_amount_veto(self):
        risky_opportunity = {
            "net_spread_bps": 120,
            "estimated_slippage": 0.1,
            "amount_usd": 1500.0  # Acima do teto de $500
        }
        orchestrator = SwarmOrchestrator(scenario="normal")
        result = orchestrator.run_simulation(risky_opportunity)
        
        self.assertEqual(result["final_decision"], "REJECTED_BY_SWARM")
        
        # Verificar especificamente se o RiskManager vetou
        risk_eval = next(e for e in result["agent_evaluations"] if e["agent"] == "RiskManager")
        self.assertEqual(risk_eval["vote"], "VETO")

if __name__ == "__main__":
    unittest.main()
