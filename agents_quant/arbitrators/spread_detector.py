"""
Detector de Spread Assíncrono — Pilar 2 (Laus Quant & Arbitrators)
Integrado com as skills @macro_brazil (Pilar 5) e @mcp-ccxt-builder (Pilar 3).

Monitora de forma não-bloqueante a paridade entre a cotação oficial do dólar
fiduciário (AwesomeAPI) e o livro de ofertas de stablecoins (USDT/BRL, USDC/BRL).
Ao identificar janelas favoráveis (spread líquido > theta_min), submete a proposta
à validação determinística do Risk Guardrail antes de autorizar despacho para o MCP.
"""

import asyncio
import logging
import random
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Injeta caminhos para resolução dos pilares
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

guardrail_dir = project_root / "gateway_vault" / "guardrail"
if str(guardrail_dir) not in sys.path:
    sys.path.insert(0, str(guardrail_dir))

strategies_dir = project_root / "agents_quant" / "strategies"
if str(strategies_dir) not in sys.path:
    sys.path.insert(0, str(strategies_dir))

macro_skills_dir = project_root / "cognition_skills" / "skills" / "macro_brazil" / "scripts"
if str(macro_skills_dir) not in sys.path:
    sys.path.insert(0, str(macro_skills_dir))

try:
    from gateway_vault.guardrail.risk_validator import RiskGuardrail, RiskGuardrailException
except ImportError:
    from risk_validator import RiskGuardrail, RiskGuardrailException

try:
    from agents_quant.strategies.orderbook_scanner import OrderbookScanner
except ImportError:
    from orderbook_scanner import OrderbookScanner

try:
    from usd_brl_monitor import calculate_net_spread, fetch_usd_brl_quote
except ImportError:
    from cognition_skills.skills.macro_brazil.scripts.usd_brl_monitor import calculate_net_spread, fetch_usd_brl_quote

try:
    from agents_quant.mirofish_simulator.swarm_orchestrator import SwarmOrchestrator
except ImportError:
    try:
        from mirofish_simulator.swarm_orchestrator import SwarmOrchestrator
    except ImportError:
        SwarmOrchestrator = None

logger = logging.getLogger("LausSpreadDetector")


@dataclass
class SpreadOpportunity:
    """Representa uma oportunidade de arbitragem cambial detectada em tempo real."""
    opportunity_id: str
    timestamp: float
    symbol: str
    p_fiat_ask: float
    p_crypto_vwap: float
    gross_spread_pct: float
    total_costs_pct: float
    net_spread_pct: float
    net_spread_bps: float
    estimated_slippage_pct: float
    viable_volume_usd: float
    is_actionable: bool


@dataclass
class ArbitrageProposal:
    """Proposta formal de ordem gerada pelo arbitrador e auditada pelo Guardrail."""
    proposal_id: str
    timestamp: float
    symbol: str
    side: str
    amount_usd: float
    target_price: float
    expected_net_profit_usd: float
    latency_ms: float
    guardrail_approved: bool
    status: str
    guardrail_reason: Optional[str] = None
    swarm_result: Optional[Dict[str, Any]] = None
    net_spread_bps: Optional[float] = None
    estimated_slippage: Optional[float] = None


class AsyncSpreadDetector:
    """
    Detector de Spread Assíncrono para Arbitragem Fiduciária/Cripto.
    Segue a especificação dos Pilares 2, 3 e 5 do ecossistema Laus.
    """

    def __init__(
        self,
        symbol: str = "USDT/BRL",
        min_spread_bps: float = 65.0,
        poll_interval_sec: float = 2.0,
        max_order_usd: float = 500.0,
        max_slippage_pct: float = 0.50,
        max_latency_ms: float = 500.0,
        maker_taker_fee: float = 0.0010,
        withdrawal_fee_brl: float = 5.00,
        on_proposal_created: Optional[Callable[[ArbitrageProposal], Coroutine[Any, Any, None]]] = None,
        guardrail: Optional[RiskGuardrail] = None,
        swarm_orchestrator: Optional[Any] = None,
        enable_swarm: bool = False,
    ):
        self.symbol = symbol
        self.min_spread_bps = min_spread_bps
        self.poll_interval_sec = poll_interval_sec
        self.max_order_usd = max_order_usd
        self.max_slippage_pct = max_slippage_pct
        self.max_latency_ms = max_latency_ms
        self.maker_taker_fee = maker_taker_fee
        self.withdrawal_fee_brl = withdrawal_fee_brl
        self.on_proposal_created = on_proposal_created

        # Inicializa o Guardrail determinístico do Pilar 3
        self.guardrail = guardrail or RiskGuardrail(
            max_order_usd=self.max_order_usd,
            max_slippage_pct=self.max_slippage_pct,
        )

        # Configuração do MiroFish Swarm Simulator (Pilar 2 & 7)
        self.enable_swarm = enable_swarm or (swarm_orchestrator is not None)
        if self.enable_swarm:
            self.swarm_orchestrator = swarm_orchestrator or (SwarmOrchestrator(scenario="normal") if SwarmOrchestrator else None)
        else:
            self.swarm_orchestrator = swarm_orchestrator

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.detected_history: List[SpreadOpportunity] = []
        self.proposals_history: List[ArbitrageProposal] = []

    async def fetch_fiat_quote_async(self) -> Dict[str, Any]:
        """
        Consulta de forma assíncrona (não-bloqueante) a cotação de USD-BRL da AwesomeAPI.
        Executada em thread pool isolada para não degradar o loop de eventos.
        """
        try:
            return await asyncio.to_thread(fetch_usd_brl_quote)
        except Exception as e:
            logger.warning(f"Erro ao consultar AwesomeAPI: {e}. Usando fallback sintético.")
            return {
                "pair": "USD-BRL",
                "bid": 5.0230,
                "ask": 5.0240,
                "pct_change": 0.0,
                "timestamp": int(time.time()),
            }

    async def fetch_crypto_book_depth_async(
        self,
        fiat_ask: float,
        target_volume_usd: float = 250.0,
    ) -> Tuple[float, float, float]:
        """
        Consulta assíncrona ao livro L2 real via OrderbookScanner com cálculo de VWAP.
        Retorna (VWAP efetivo, Slippage estimado %, RTT Latência em ms).
        """
        start_time = time.time()
        try:
            # Consulta livro L2 real do Mercado Bitcoin ou fallback sintético em thread separada
            book = await asyncio.to_thread(OrderbookScanner.fetch_live_orderbook, "USDT-BRL")
            _, vwap_ask, slippage = OrderbookScanner.calculate_vwap_slippage(
                book["asks"], target_volume_usd
            )
            latency_ms = (time.time() - start_time) * 1000.0
            return vwap_ask, slippage, latency_ms
        except Exception as e:
            logger.debug(f"Falha na leitura direta L2: {e}. Aplicando modelo estocástico de contingência.")
            latency_ms = random.uniform(35.0, 95.0)
            await asyncio.sleep(latency_ms / 1000.0)
            crypto_premium_pct = random.uniform(0.0070, 0.0110)
            p_crypto_vwap = round(fiat_ask * (1.0 + crypto_premium_pct), 4)
            slippage_pct = round(0.04 + (target_volume_usd / 2000.0) * 0.15, 3)
            return p_crypto_vwap, slippage_pct, latency_ms

    def evaluate_spread(
        self,
        p_fiat: float,
        p_crypto: float,
        slippage_pct: float,
        volume_usd: float = 250.0,
    ) -> SpreadOpportunity:
        """Calcula métricas de spread segundo a fórmula do Pilar 2 e @macro_brazil."""
        capital_brl = volume_usd * p_fiat
        metrics = calculate_net_spread(
            p_crypto=p_crypto,
            p_fiat=p_fiat,
            capital_brl=capital_brl,
            maker_taker_fee=self.maker_taker_fee,
            withdrawal_fee_brl=self.withdrawal_fee_brl,
            slippage=slippage_pct / 100.0,
        )

        net_bps = metrics["net_spread_bps"]
        is_actionable = net_bps >= self.min_spread_bps

        return SpreadOpportunity(
            opportunity_id=f"OPP-{uuid.uuid4().hex[:8].upper()}",
            timestamp=time.time(),
            symbol=self.symbol,
            p_fiat_ask=p_fiat,
            p_crypto_vwap=p_crypto,
            gross_spread_pct=metrics["gross_spread_pct"],
            total_costs_pct=metrics["total_costs_pct"],
            net_spread_pct=metrics["net_spread_pct"],
            net_spread_bps=net_bps,
            estimated_slippage_pct=slippage_pct,
            viable_volume_usd=volume_usd,
            is_actionable=is_actionable,
        )

    async def stage_mcp_proposal(
        self,
        opportunity: SpreadOpportunity,
        latency_ms: float,
    ) -> ArbitrageProposal:
        """
        Formula a proposta estruturada e submete ao Risk Guardrail (skill @mcp-ccxt-builder).
        Nenhuma ordem é autorizada sem validação determinística de risco e latência.
        """
        proposal_id = f"PROP-{uuid.uuid4().hex[:8].upper()}"
        amount_usd = opportunity.viable_volume_usd
        expected_profit = amount_usd * (opportunity.net_spread_pct / 100.0)

        # 1. Checagem do Circuit Breaker de Latência (Pilar 6)
        if latency_ms > self.max_latency_ms:
            return ArbitrageProposal(
                proposal_id=proposal_id,
                timestamp=time.time(),
                symbol=self.symbol,
                side="buy",
                amount_usd=amount_usd,
                target_price=opportunity.p_crypto_vwap,
                expected_net_profit_usd=expected_profit,
                latency_ms=latency_ms,
                guardrail_approved=False,
                status="CIRCUIT_BREAKER_BLOCKED",
                guardrail_reason=f"Latência de {latency_ms:.1f}ms excede limite de {self.max_latency_ms}ms",
                net_spread_bps=opportunity.net_spread_bps,
                estimated_slippage=opportunity.estimated_slippage_pct,
            )

        # 2. Debate Multiagente MiroFish Swarm (Pilar 2 & 7) antes do Guardrail
        swarm_result = None
        if self.enable_swarm and self.swarm_orchestrator:
            opp_dict = {
                "symbol": self.symbol,
                "amount_usd": amount_usd,
                "net_spread_bps": opportunity.net_spread_bps,
                "estimated_slippage": opportunity.estimated_slippage_pct,
                "target_price": opportunity.p_crypto_vwap,
                "net_spread_pct": opportunity.net_spread_pct,
            }
            swarm_result = self.swarm_orchestrator.run_simulation(opp_dict)
            if swarm_result.get("final_decision") != "APPROVED":
                vetos = [
                    f"{e['agent']}: {e['comment']}"
                    for e in swarm_result.get("agent_evaluations", [])
                    if e.get("vote") == "VETO"
                ]
                reason = f"MiroFish Swarm Veto: {'; '.join(vetos)}" if vetos else "MiroFish Swarm: Consenso insuficiente (< 3 votos favoráveis)"
                logger.warning(f"🐟 Proposta {proposal_id} vetada pelo MiroFish Swarm: {reason}")
                proposal = ArbitrageProposal(
                    proposal_id=proposal_id,
                    timestamp=time.time(),
                    symbol=self.symbol,
                    side="buy",
                    amount_usd=amount_usd,
                    target_price=opportunity.p_crypto_vwap,
                    expected_net_profit_usd=expected_profit,
                    latency_ms=latency_ms,
                    guardrail_approved=False,
                    status="REJECTED_BY_SWARM",
                    guardrail_reason=reason,
                    swarm_result=swarm_result,
                    net_spread_bps=opportunity.net_spread_bps,
                    estimated_slippage=opportunity.estimated_slippage_pct,
                )
                self.proposals_history.append(proposal)
                if self.on_proposal_created:
                    await self.on_proposal_created(proposal)
                return proposal

        # 3. Validação Determinística no RiskGuardrail (Pilar 3)
        try:
            self.guardrail.validate_order(
                symbol=self.symbol,
                amount_usd=amount_usd,
                estimated_slippage=opportunity.estimated_slippage_pct,
            )
            approved = True
            status = "STAGED_FOR_MCP_EXECUTION"
            reason = None
        except RiskGuardrailException as e:
            approved = False
            status = "REJECTED_GUARDRAIL"
            reason = str(e)

        proposal = ArbitrageProposal(
            proposal_id=proposal_id,
            timestamp=time.time(),
            symbol=self.symbol,
            side="buy",
            amount_usd=amount_usd,
            target_price=opportunity.p_crypto_vwap,
            expected_net_profit_usd=expected_profit,
            latency_ms=latency_ms,
            guardrail_approved=approved,
            status=status,
            guardrail_reason=reason,
            swarm_result=swarm_result,
            net_spread_bps=opportunity.net_spread_bps,
            estimated_slippage=opportunity.estimated_slippage_pct,
        )

        self.proposals_history.append(proposal)

        if self.on_proposal_created:
            await self.on_proposal_created(proposal)

        return proposal

    async def poll_cycle(self) -> Optional[ArbitrageProposal]:
        """Executa um ciclo individual de detecção e validação de spread."""
        fiat_data = await self.fetch_fiat_quote_async()
        p_fiat = fiat_data["ask"]

        p_crypto, slippage, latency_ms = await self.fetch_crypto_book_depth_async(
            fiat_ask=p_fiat,
            target_volume_usd=250.0,
        )

        opportunity = self.evaluate_spread(
            p_fiat=p_fiat,
            p_crypto=p_crypto,
            slippage_pct=slippage,
            volume_usd=250.0,
        )
        self.detected_history.append(opportunity)

        if opportunity.is_actionable:
            proposal = await self.stage_mcp_proposal(opportunity, latency_ms=latency_ms)
            return proposal
        return None

    async def start(self, max_cycles: Optional[int] = None):
        """Inicia o loop assíncrono contínuo de monitoramento."""
        self._running = True
        logger.info(f"Detector de Spread iniciado para {self.symbol} (Threshold: {self.min_spread_bps} bps).")
        cycles = 0

        while self._running:
            try:
                proposal = await self.poll_cycle()
                if proposal and proposal.guardrail_approved:
                    logger.info(
                        f"🚀 [PROPOSTA LIBERADA]: {proposal.proposal_id} | "
                        f"Spread Líquido Ativo | Lucro Projetado: ${proposal.expected_net_profit_usd:.4f}"
                    )
            except Exception as e:
                logger.error(f"Erro no ciclo do detector de spread: {e}")

            cycles += 1
            if max_cycles and cycles >= max_cycles:
                break

            await asyncio.sleep(self.poll_interval_sec)

    def stop(self):
        """Interrompe a execução do detector."""
        self._running = False
        logger.info("Detector de Spread interrompido.")
