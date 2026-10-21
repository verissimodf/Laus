"""
Laus Quant & Swarm Simulator (Pilar 2)
Motores quantitativos, scanners de profundidade L2, arbitradores e consenso Swarm.
"""

from .strategies.orderbook_scanner import OrderbookScanner
from .mirofish_sim.swarm_engine import MiroFishSwarmSimulator, SwarmPersona
from .mirofish_sim.llm_swarm import MiroFishCognitiveSwarm
from .mirofish_sim.digital_twin import DigitalTwinSandbox
from .arbitrators.spread_detector import AsyncSpreadDetector, SpreadOpportunity, ArbitrageProposal

__all__ = [
    # Strategies & Scanners
    "OrderbookScanner",
    # Swarm & Simulation
    "MiroFishSwarmSimulator",
    "SwarmPersona",
    "MiroFishCognitiveSwarm",
    "DigitalTwinSandbox",
    # Arbitrators
    "AsyncSpreadDetector",
    "SpreadOpportunity",
    "ArbitrageProposal",
]
