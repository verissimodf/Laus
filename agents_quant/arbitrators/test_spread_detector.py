#!/usr/bin/env python3
"""
Validação do Detector de Spread Assíncrono (Pilar 2)
Integrado com @macro_brazil e @mcp-ccxt-builder.
"""

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

project_root = Path(__file__).resolve().parents[2]
quant_dir = project_root / "agents_quant"
if str(quant_dir) not in sys.path:
    sys.path.insert(0, str(quant_dir))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from arbitrators.spread_detector import ArbitrageProposal, AsyncSpreadDetector


async def mock_mcp_dispatcher_callback(proposal: ArbitrageProposal):
    """Callback invocado quando uma proposta passa pela validação do Guardrail."""
    status_emoji = "✅ [APROVADA PELO GUARDRAIL]" if proposal.guardrail_approved else "❌ [VETADA PELO GUARDRAIL]"
    print(f"\n📢 [DISPATCH CALLBACK -> MCP SERVER]: {proposal.proposal_id}")
    print(f"     Status:           {status_emoji} -> {proposal.status}")
    print(f"     Par:              {proposal.symbol} ({proposal.side.upper()})")
    print(f"     Volume Alocado:   ${proposal.amount_usd:.2f} USD")
    print(f"     Preço Alvo VWAP:  R$ {proposal.target_price:.4f}")
    print(f"     Lucro Estimado:   +${proposal.expected_net_profit_usd:.4f} USD")
    print(f"     RTT Latência:     {proposal.latency_ms:.1f}ms")
    if proposal.guardrail_reason:
        print(f"     Motivo do Veto:   {proposal.guardrail_reason}")


async def main():
    print("=" * 70)
    print("⚡ LAUS QUANT — TESTE DO DETECTOR DE SPREAD ASSÍNCRONO (PILAR 2)")
    print("=" * 70)

    detector = AsyncSpreadDetector(
        symbol="USDT/BRL",
        min_spread_bps=50.0,         # Gatilho de 50 bps para validação de ciclo
        poll_interval_sec=1.0,
        max_order_usd=500.0,
        max_slippage_pct=0.50,
        max_latency_ms=500.0,
        on_proposal_created=mock_mcp_dispatcher_callback,
    )

    print("Iniciando 3 ciclos assíncronos de detecção...")
    await detector.start(max_cycles=3)

    print("\n" + "=" * 70)
    print("📊 RESUMO DOS CICLOS EXECUTADOS")
    print("=" * 70)
    for opp in detector.detected_history:
        print(f"• ID: {opp.opportunity_id} | Fiat: R${opp.p_fiat_ask:.4f} | Crypto: R${opp.p_crypto_vwap:.4f}")
        print(f"  Spread Bruto: {opp.gross_spread_pct:+.3f}% | Custos: -{opp.total_costs_pct:.3f}% | "
              f"Líquido: {opp.net_spread_pct:+.3f}% ({opp.net_spread_bps:+.1f} bps) | "
              f"Acionável: {'SIM' if opp.is_actionable else 'NÃO'}")

    print("\nPropostas submetidas ao Guardrail:", len(detector.proposals_history))
    for p in detector.proposals_history:
        print(f"  - Proposta {p.proposal_id}: {p.status} (Aprovada: {p.guardrail_approved})")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
