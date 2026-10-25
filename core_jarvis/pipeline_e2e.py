"""
pipeline_e2e.py - Laus Integrated E2E Execution & Decision Pipeline
Unifies:
  - Pilar 1: core_jarvis (JarvisOrchestrator & Kill Switch)
  - Pilar 2: agents_quant (AsyncSpreadDetector & ArbitrageProposal)
  - Pilar 3: gateway_vault (RiskGuardrail & Safety Thresholds)
  - Pilar 4: console_ui / telemetry (PostHog Event Capture)
  - Pilar 8: accounting_ledger (Double-Entry Bookkeeping & IN 1888 Compliance)
"""

import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Configure project paths
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

core_jarvis_dir = Path(__file__).resolve().parent
if str(core_jarvis_dir) not in sys.path:
    sys.path.insert(0, str(core_jarvis_dir))

guardrail_dir = project_root / "gateway_vault" / "guardrail"
if str(guardrail_dir) not in sys.path:
    sys.path.insert(0, str(guardrail_dir))

ledger_dir = project_root / "accounting_ledger"
if str(ledger_dir) not in sys.path:
    sys.path.insert(0, str(ledger_dir))

telemetry_dir = project_root / "cognition_skills" / "skills" / "posthog_telemetry" / "scripts"
if str(telemetry_dir) not in sys.path:
    sys.path.insert(0, str(telemetry_dir))

quant_dir = project_root / "agents_quant" / "arbitrators"
if str(quant_dir) not in sys.path:
    sys.path.insert(0, str(quant_dir))

mirofish_dir = project_root / "agents_quant" / "mirofish_simulator"
if str(mirofish_dir) not in sys.path:
    sys.path.insert(0, str(mirofish_dir))

try:
    from .orchestrator import JarvisOrchestrator
except ImportError:
    from orchestrator import JarvisOrchestrator
from risk_validator import RiskGuardrail, RiskGuardrailException
from ledger_engine import AccountingLedger
from spread_detector import ArbitrageProposal, AsyncSpreadDetector
from emit_posthog_event import capture_laus_event

try:
    from agents_quant.mirofish_simulator.swarm_orchestrator import SwarmOrchestrator
except ImportError:
    try:
        from swarm_orchestrator import SwarmOrchestrator
    except ImportError:
        SwarmOrchestrator = None

logger = logging.getLogger("LausE2EPipeline")


class LausE2EPipeline:
    """
    Orquestrador E2E do loop de arbitragem, governança de risco e registro contábil.
    """

    def __init__(
        self,
        orchestrator: Optional[JarvisOrchestrator] = None,
        ledger: Optional[AccountingLedger] = None,
        guardrail: Optional[RiskGuardrail] = None,
        swarm_orchestrator: Optional[Any] = None,
        enable_swarm: bool = False,
        db_path: Optional[str] = None,
        max_order_usd: float = 500.0,
        max_slippage_pct: float = 0.50,
        max_daily_drawdown_usd: Optional[float] = None,
        environment: str = "shadow_paper_trading",
    ):
        self.orchestrator = orchestrator or JarvisOrchestrator()
        self.guardrail = guardrail or RiskGuardrail(
            max_order_usd=max_order_usd,
            max_slippage_pct=max_slippage_pct,
            max_daily_drawdown_usd=max_daily_drawdown_usd,
        )

        self.enable_swarm = enable_swarm or (swarm_orchestrator is not None)
        if self.enable_swarm:
            self.swarm_orchestrator = swarm_orchestrator or (SwarmOrchestrator(scenario="normal") if SwarmOrchestrator else None)
        else:
            self.swarm_orchestrator = swarm_orchestrator
        
        target_db = db_path or str(project_root / "accounting_ledger" / "laus_vault.db")
        self.ledger = ledger or AccountingLedger(target_db)
        self.environment = environment
        
        self.executed_trades = []
        self.rejected_proposals = []

    async def handle_proposal_callback(self, proposal: ArbitrageProposal) -> Dict[str, Any]:
        """
        Callback injetado diretamente no AsyncSpreadDetector.
        Processa cada proposta gerada pelo ciclo quantitativo.
        """
        return await self.execute_pipeline_turn(proposal)

    async def execute_pipeline_turn(
        self,
        proposal: ArbitrageProposal,
        fiat_rate: float = 5.0240,
        effective_spread_pct: float = 0.75,
    ) -> Dict[str, Any]:
        """
        Executa um ciclo completo de decisão e liquidação para a proposta fornecida.
        """
        # 1. Checagem do Kill Switch Central do Jarvis (Pilar 1)
        if self.orchestrator.emergency_stop:
            logger.warning(f"🚨 Pipeline rejeitou proposta {proposal.proposal_id}: Kill Switch ativo!")
            self.rejected_proposals.append({
                "proposal_id": proposal.proposal_id,
                "reason": "KILL_SWITCH_ACTIVE",
            })
            capture_laus_event(
                event_name="laus_order_rejected_kill_switch",
                distinct_id="pipeline_e2e",
                properties={
                    "proposal_id": proposal.proposal_id,
                    "symbol": proposal.symbol,
                    "amount_usd": proposal.amount_usd,
                },
            )
            return {
                "success": False,
                "status": "ABORTED_BY_KILL_SWITCH",
                "proposal_id": proposal.proposal_id,
                "reason": "Emergency stop is active in JarvisOrchestrator",
            }

        # 2. Avaliação de Consenso MiroFish Swarm (Pilar 2 & 7) se ativo e ainda não avaliado
        if self.enable_swarm and self.swarm_orchestrator and not proposal.swarm_result:
            opp_dict = {
                "symbol": proposal.symbol,
                "amount_usd": proposal.amount_usd,
                "target_price": proposal.target_price,
                "net_spread_bps": getattr(proposal, "net_spread_bps", 60.0) or 60.0,
                "estimated_slippage": getattr(proposal, "estimated_slippage", 0.15) or 0.15,
                "net_spread_pct": (proposal.expected_net_profit_usd / proposal.amount_usd * 100.0) if proposal.amount_usd > 0 else 0.5,
            }
            swarm_res = self.swarm_orchestrator.run_simulation(opp_dict)
            proposal.swarm_result = swarm_res
            if swarm_res.get("final_decision") != "APPROVED":
                vetos = [
                    f"{e['agent']}: {e['comment']}"
                    for e in swarm_res.get("agent_evaluations", [])
                    if e.get("vote") == "VETO"
                ]
                reason = f"MiroFish Swarm Veto: {'; '.join(vetos)}" if vetos else "MiroFish Swarm: Consenso insuficiente (< 3 votos favoráveis)"
                proposal.status = "REJECTED_BY_SWARM"
                proposal.guardrail_approved = False
                proposal.guardrail_reason = reason

        # 3. Verificação de Bloqueio por Circuit Breaker de Latência, Swarm ou Guardrail (Pilares 2, 3, 6)
        if proposal.status in ("CIRCUIT_BREAKER_BLOCKED", "REJECTED_BY_SWARM") or not proposal.guardrail_approved:
            if proposal.status == "REJECTED_BY_SWARM":
                logger.warning(
                    f"🐟 Proposta {proposal.proposal_id} vetada pelo MiroFish Swarm: {proposal.guardrail_reason}"
                )
                capture_laus_event(
                    event_name="laus_order_rejected_swarm",
                    distinct_id="pipeline_e2e",
                    properties={
                        "proposal_id": proposal.proposal_id,
                        "symbol": proposal.symbol,
                        "amount_usd": proposal.amount_usd,
                        "reason": proposal.guardrail_reason,
                        "votes_summary": proposal.swarm_result.get("votes_summary") if proposal.swarm_result else {},
                        "average_confidence": proposal.swarm_result.get("average_confidence") if proposal.swarm_result else 0.0,
                    },
                )
            else:
                logger.warning(
                    f"⚠️ Proposta {proposal.proposal_id} vetada pelo Guardrail/Circuit Breaker: {proposal.guardrail_reason}"
                )
                capture_laus_event(
                    event_name="laus_order_vetoed_by_guardrail",
                    distinct_id="pipeline_e2e",
                    properties={
                        "proposal_id": proposal.proposal_id,
                        "symbol": proposal.symbol,
                        "amount_usd": proposal.amount_usd,
                        "reason": proposal.guardrail_reason,
                        "status": proposal.status,
                    },
                )
            self.rejected_proposals.append({
                "proposal_id": proposal.proposal_id,
                "reason": proposal.guardrail_reason or proposal.status,
                "status": proposal.status,
            })
            return {
                "success": False,
                "status": proposal.status,
                "proposal_id": proposal.proposal_id,
                "reason": proposal.guardrail_reason,
                "swarm_result": proposal.swarm_result,
            }

        # 4. Telemetria de Consenso MiroFish Swarm quando aprovado
        if proposal.swarm_result and proposal.swarm_result.get("final_decision") == "APPROVED":
            capture_laus_event(
                event_name="laus_swarm_consensus_reached",
                distinct_id="mirofish_swarm",
                properties={
                    "proposal_id": proposal.proposal_id,
                    "symbol": proposal.symbol,
                    "amount_usd": proposal.amount_usd,
                    "votes_summary": proposal.swarm_result.get("votes_summary"),
                    "average_confidence": proposal.swarm_result.get("average_confidence"),
                },
            )

        # 5. Revalidação no momento do registro usando o PnL paper do dia UTC.
        daily_state = self.ledger.get_daily_summary()
        try:
            self.guardrail.validate_order(
                symbol=proposal.symbol,
                amount_usd=proposal.amount_usd,
                estimated_slippage=proposal.estimated_slippage,
                daily_realized_pnl_usd=daily_state["paper_realized_pnl_usd"],
            )
        except RiskGuardrailException as exc:
            reason = str(exc)
            self.rejected_proposals.append({
                "proposal_id": proposal.proposal_id,
                "reason": reason,
                "status": "DAILY_DRAWDOWN_LIMIT",
            })
            capture_laus_event(
                event_name="laus_order_vetoed_by_guardrail",
                distinct_id="pipeline_e2e",
                properties={
                    "proposal_id": proposal.proposal_id,
                    "symbol": proposal.symbol,
                    "status": "DAILY_DRAWDOWN_LIMIT",
                    "guardrail_code": "DAILY_DRAWDOWN_LIMIT",
                },
            )
            return {
                "success": False,
                "status": "DAILY_DRAWDOWN_LIMIT",
                "proposal_id": proposal.proposal_id,
                "reason": reason,
                "daily_paper_pnl_usd": daily_state["paper_realized_pnl_usd"],
            }

        # 6. Registro de simulação paper (sem envio ou confirmação de ordem)
        # Os valores registrados são estimativas do simulador, não execução nem apuração fiscal
        ledger_entry = self.ledger.record_arbitrage_trade(
            symbol=proposal.symbol,
            amount_usd=proposal.amount_usd,
            rate=fiat_rate,
            spread_pct=effective_spread_pct,
            source=f"PAPER_SIMULATION_{self.environment.upper()}",
            evidence=proposal.market_evidence,
        )

        trade_record = {
            "proposal_id": proposal.proposal_id,
            "timestamp": time.time(),
            "symbol": proposal.symbol,
            "side": proposal.side,
            "amount_usd": proposal.amount_usd,
            "rate_brl": fiat_rate,
            "ledger_entry": ledger_entry,
            "environment": self.environment,
            "latency_ms": proposal.latency_ms,
            "swarm_result": proposal.swarm_result,
            "market_evidence": proposal.market_evidence,
        }
        self.executed_trades.append(trade_record)

        # 6. Telemetria PostHog Self-Hosted (Pilar 4)
        has_swarm_consensus = bool(proposal.swarm_result and proposal.swarm_result.get("final_decision") == "APPROVED")
        capture_laus_event(
            event_name="laus_paper_trade_recorded",
            distinct_id="agent_quant_arbitrator",
            properties={
                "proposal_id": proposal.proposal_id,
                "symbol": proposal.symbol,
                "side": proposal.side,
                "amount_usd": proposal.amount_usd,
                "rate_brl": fiat_rate,
                "net_profit_usd": ledger_entry["net_profit_usd"],
                "fee_usd": ledger_entry["fee_usd"],
                "tax_provision_brl": ledger_entry["tax_provision_brl"],
                "entry_id": ledger_entry["entry_id"],
                "environment": self.environment,
                "swarm_consensus": has_swarm_consensus,
            },
        )

        # 7. Notificação de Despacho no Orquestrador
        await self.orchestrator.dispatch_event(
            event_type="PAPER_TRADE_RECORDED",
            payload={
                "proposal_id": proposal.proposal_id,
                "ledger_entry_id": ledger_entry["entry_id"],
                "net_profit_usd": ledger_entry["net_profit_usd"],
                "swarm_consensus": has_swarm_consensus,
            },
        )

        logger.info(
            f"🧪 [PAPER PIPELINE] Proposta {proposal.proposal_id} registrada no Ledger #{ledger_entry['entry_id']}: "
            f"Net PnL=${ledger_entry['net_profit_usd']:.4f} USD | IR=R${ledger_entry['tax_provision_brl']:.2f}"
            + (f" | MiroFish Swarm: {proposal.swarm_result.get('votes_summary')}" if proposal.swarm_result else "")
        )

        return {
            "success": True,
            "status": "PAPER_TRADE_RECORDED",
            "proposal_id": proposal.proposal_id,
            "ledger_result": ledger_entry,
            "swarm_result": proposal.swarm_result,
        }
