#!/usr/bin/env python3
"""
Simulador de Consenso Swarm MiroFish e Gêmeo Digital (Pilares 2 e 7)
"""
import sys
import os
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Adiciona raiz do projeto ao path se necessário
project_root = Path(__file__).resolve().parents[4]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Adiciona modulos necessarios ao path
mirofish_dir = project_root / "agents_quant" / "mirofish_sim"
if str(mirofish_dir) not in sys.path:
    sys.path.append(str(mirofish_dir))

from swarm_simulator import MiroFishSwarmSimulator
from agents_quant.mirofish_sim.digital_twin import DigitalTwinSandbox


def evaluate_candidate_order(symbol: str = "USDT/BRL", amount_usd: float = 250.0, spread_pct: float = 0.85):
    print("=" * 60)
    print(f"🐟 MIROFISH SWARM & DIGITAL TWIN VALIDATION: {symbol}")
    print("=" * 60)

    # 1. Simulação Swarm
    swarm = MiroFishSwarmSimulator()
    swarm_result = swarm.simulate_order_impact(symbol=symbol, amount_usd=amount_usd, spread_pct=spread_pct)
    print(f"Consenso do Enxame: {swarm_result['consensus_score'] * 100:.1f}% | Aprovado: {swarm_result['approved']}")
    for vote in swarm_result["votes"]:
        status = "VOTO FAVORÁVEL" if vote["approves"] else "VETO"
        print(f"  - [{vote['persona']}]: {status} (Confiança: {vote['confidence']:.2f}) -> {vote['reason']}")

    # 2. Replicação no Gêmeo Digital (Paper Trading)
    twin = DigitalTwinSandbox(target_symbol=symbol)
    market_state = twin.replicate_market_state(real_spread=spread_pct, real_rate=5.45)
    paper_tx = twin.execute_paper_trade(amount_usd=amount_usd, market_state=market_state)

    print(f"\nGêmeo Digital (Slippage Replicado):")
    print(f"  - Spread Replicado: {market_state['twin_spread_pct']:.2f}% | Slippage Sintético: {market_state['twin_slippage_pct']:.2f}%")
    print(f"  - Spread Efetivo Final: {market_state['effective_spread']:.2f}%")
    print(f"  - Status Execução Paper: {paper_tx['execution_status']} | PnL Projetado: ${paper_tx['simulated_pnl_usd']:.4f}")
    print("=" * 60)

    return {
        "swarm_approved": swarm_result["approved"],
        "paper_status": paper_tx["execution_status"],
        "ready_for_guardrail": swarm_result["approved"] and paper_tx["execution_status"] == "SUCCESS"
    }


if __name__ == "__main__":
    evaluate_candidate_order()
