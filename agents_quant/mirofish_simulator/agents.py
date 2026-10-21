"""
MiroFish Swarm Simulator - Personas dos Agentes Especializados
Cada agente avalia o sinal de mercado sob uma ótica comportamental distinta.
"""

from typing import Dict, Any

class SwarmAgent:
    def evaluate(self, market_data: Dict[str, Any], opportunity: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class BullAnalystAgent(SwarmAgent):
    """Foco em momentum de alta, quebra de resistência e otimização de lucro."""
    def evaluate(self, market_data: Dict[str, Any], opportunity: Dict[str, Any]) -> Dict[str, Any]:
        spread = opportunity.get("net_spread_bps", 0)
        trend = market_data.get("trend", "neutral")
        
        score = 0.8 if spread > 50 else 0.4
        if trend == "bullish":
            score += 0.2
            
        return {
            "agent": "BullAnalyst",
            "vote": "APPROVE" if score >= 0.7 else "NEUTRAL",
            "confidence": min(score, 1.0),
            "comment": f"Momentum favorável. Spread líquido de {spread} bps."
        }


class BearAnalystAgent(SwarmAgent):
    """Foco em risco sistêmico, reversão à média e armadilhas de liquidez."""
    def evaluate(self, market_data: Dict[str, Any], opportunity: Dict[str, Any]) -> Dict[str, Any]:
        volatility = market_data.get("volatility", "low")
        slippage = opportunity.get("estimated_slippage", 0.1)
        
        score = 0.9
        if volatility == "extreme" or slippage > 0.4:
            score = 0.1
            
        return {
            "agent": "BearAnalyst",
            "vote": "APPROVE" if score >= 0.5 else "VETO",
            "confidence": score,
            "comment": f"Volatilidade: {volatility}, Slippage estimado: {slippage}%."
        }


class RiskManagerAgent(SwarmAgent):
    """Guardião estrito do capital, drawdown e alocação de risco (Kelly Fracionado)."""
    def evaluate(self, market_data: Dict[str, Any], opportunity: Dict[str, Any]) -> Dict[str, Any]:
        amount = opportunity.get("amount_usd", 0)
        max_limit = 500.0
        
        if amount > max_limit:
            return {
                "agent": "RiskManager",
                "vote": "VETO",
                "confidence": 1.0,
                "comment": f"Montante de ${amount} excede o limite prudencial de ${max_limit}."
            }
            
        return {
            "agent": "RiskManager",
            "vote": "APPROVE",
            "confidence": 0.95,
            "comment": "Exposição dentro dos limites de risco aceitáveis."
        }


class MacroMarketMakerAgent(SwarmAgent):
    """Avalia o impacto de taxas de câmbio (AwesomeAPI) e infraestrutura bancária (BrasilAPI)."""
    def evaluate(self, market_data: Dict[str, Any], opportunity: Dict[str, Any]) -> Dict[str, Any]:
        fx_change = market_data.get("usd_brl_pct_change", 0.0)
        bank_status = market_data.get("bank_network_status", "stable")
        
        if bank_status != "stable" or abs(fx_change) > 2.0:
            return {
                "agent": "MacroMarketMaker",
                "vote": "VETO",
                "confidence": 0.9,
                "comment": f"Instabilidade macro: FX Var={fx_change}%, Status Bancário={bank_status}."
            }
            
        return {
            "agent": "MacroMarketMaker",
            "vote": "APPROVE",
            "confidence": 0.85,
            "comment": "Cenário macroeconômico estável para liquidação."
        }