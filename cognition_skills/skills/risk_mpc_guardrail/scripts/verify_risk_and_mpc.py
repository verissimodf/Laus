#!/usr/bin/env python3
"""
Validador de Risco e Simulação de Assinatura MPC (Pilar 3 e Pilar 6)
"""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

project_root = Path(__file__).resolve().parents[4]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Adiciona modulo de guardrail ao path
guardrail_dir = project_root / "gateway_vault" / "guardrail"
if str(guardrail_dir) not in sys.path:
    sys.path.insert(0, str(guardrail_dir))

from risk_validator import RiskGuardrail, RiskGuardrailException


def verify_order_safety(symbol: str, amount_usd: float, estimated_slippage: float, latency_ms: float = 85.0):
    print("=" * 60)
    print(f"🔐 RISK GUARDRAIL & MPC GATEWAY CHECK: {symbol}")
    print("=" * 60)

    # 1. Circuit Breaker de Latência
    if latency_ms > 500.0:
        print(f"[BLOQUEIO] Latência crítica de {latency_ms:.1f}ms (> 500ms). Circuit Breaker ativado!")
        return {"status": "BLOCKED_LATENCY", "latency_ms": latency_ms}

    print(f"[OK] Conectividade e Latência: {latency_ms:.1f}ms (< 500ms)")

    # 2. Risk Guardrail Determinístico
    guardrail = RiskGuardrail(max_order_usd=500.0, max_slippage_pct=0.5)
    try:
        guardrail.validate_order(symbol=symbol, amount_usd=amount_usd, estimated_slippage=estimated_slippage)
        print(f"[OK] Limite de Ordem: ${amount_usd:.2f} <= $500.00")
        print(f"[OK] Tolerância de Slippage: {estimated_slippage:.2f}% <= 0.50%")
    except RiskGuardrailException as e:
        print(f"[VETO GUARDRAIL]: {e}")
        return {"status": "VETOED", "reason": str(e)}

    # 3. Protocolo MPC 2-de-3
    print(f"[OK] Chaves MPC Verificadas (Share 1 Agente + Share 2 Vault Local).")
    print(f"[AUTORIZADO] Ordem assinada e pronta para transmissão via MCP.")
    print("=" * 60)
    return {"status": "AUTHORIZED", "symbol": symbol, "amount_usd": amount_usd}


if __name__ == "__main__":
    verify_order_safety("USDT/BRL", 250.0, 0.15, latency_ms=45.0)
