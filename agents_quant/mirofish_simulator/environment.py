"""
MiroFish Swarm Simulator - Gêmeo Digital (Digital Twin Environment)
Simula feeds de mercado em tempo real e cenários de estresse estocástico.
"""

from typing import Dict, Any

class MarketSandboxEnvironment:
    def __init__(self, scenario: str = "normal"):
        self.scenario = scenario

    def get_current_state(self) -> Dict[str, Any]:
        if self.scenario == "flash_crash":
            return {
                "trend": "bearish",
                "volatility": "extreme",
                "usd_brl_pct_change": -3.5,
                "bank_network_status": "degraded"
            }
        elif self.scenario == "high_volatility":
            return {
                "trend": "neutral",
                "volatility": "high",
                "usd_brl_pct_change": 1.2,
                "bank_network_status": "stable"
            }
        else: # Normal
            return {
                "trend": "bullish",
                "volatility": "low",
                "usd_brl_pct_change": -0.33,
                "bank_network_status": "stable"
            }