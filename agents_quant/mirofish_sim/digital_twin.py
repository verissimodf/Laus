"""
Laus Gêmeo Digital & Sandboxing - Paper Trading Contínuo (Pilar 7)
Espelha o comportamento do mercado em ambiente isolado para aferição de eficiência sem risco.
"""
import time
import random
from typing import Dict, Any, List

class DigitalTwinSandbox:
    def __init__(self, target_symbol: str):
        self.target_symbol = target_symbol
        self.paper_history: List[Dict[str, Any]] = []

    def replicate_market_state(self, real_spread: float, real_rate: float) -> Dict[str, Any]:
        """Clona o estado atual do mercado e insere ruído estocástico de volatilidade (Slippage sintético)."""
        # Adiciona um ruído matemático aleatório simulando oscilação de milissegundos do book
        ruido_spread = random.uniform(-0.05, 0.05)
        twin_spread = max(0.01, real_spread + ruido_spread)
        
        # Simula o slippage real gerado por latência de rede em Sandbox
        twin_slippage = random.uniform(0.05, 0.22)
        
        return {
            "symbol": self.target_symbol,
            "replicated_rate": round(real_rate, 4),
            "twin_spread_pct": round(twin_spread, 2),
            "twin_slippage_pct": round(twin_slippage, 2),
            "effective_spread": round(twin_spread - twin_slippage, 2)
        }

    def execute_paper_trade(self, amount_usd: float, market_state: Dict[str, Any]) -> Dict[str, Any]:
        """Executa uma ordem fantasma em Sandbox e calcula a eficiência de absorção do book."""
        pnl_estimado = amount_usd * (market_state["effective_spread"] / 100.0)
        sucesso = pnl_estimado > 0
        
        paper_tx = {
            "paper_tx_id": f"TWIN-{int(time.time()*1000)}",
            "timestamp": time.time(),
            "volume_usd": amount_usd,
            "simulated_pnl_usd": round(pnl_estimado, 4),
            "execution_status": "SUCCESS" if sucesso else "SLIPPAGE_KILL"
        }
        
        self.paper_history.append(paper_tx)
        return paper_tx

    def get_efficiency_report(self) -> Dict[str, Any]:
        """Mede a taxa de acerto do gêmeo digital."""
        if not self.paper_history:
            return {"accuracy_pct": 0.0, "total_paper_ops": 0}
            
        ops_com_lucro = sum(1 for tx in self.paper_history if tx["simulated_pnl_usd"] > 0)
        total_pnl = sum(tx["simulated_pnl_usd"] for tx in self.paper_history)
        
        return {
            "total_paper_ops": len(self.paper_history),
            "accuracy_pct": round((ops_com_lucro / len(self.paper_history)) * 100, 2),
            "cumulative_paper_pnl_usd": round(total_pnl, 4)
        }
