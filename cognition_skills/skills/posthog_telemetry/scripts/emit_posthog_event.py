#!/usr/bin/env python3
"""
Emissor de Eventos de Telemetria PostHog Self-Hosted (Pilar 4)
"""
import json
import sys
import time
from typing import Any, Dict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def capture_laus_event(event_name: str, distinct_id: str, properties: Dict[str, Any], host: str = "http://localhost:8000"):
    payload = {
        "event": event_name,
        "distinct_id": distinct_id,
        "properties": {
            **properties,
            "$lib": "laus-python-telemetry",
            "timestamp": time.time(),
        }
    }
    print(f"📊 [POSTHOG EVENT EMITTED -> {host}]:")
    print(f"     Evento:      {payload['event']}")
    print(f"     Distinct ID: {payload['distinct_id']}")
    print(f"     Propriedades:")
    for k, v in properties.items():
        print(f"       • {k}: {v}")
    return payload


def run_sample_telemetry():
    print("=" * 60)
    print("📈 TESTE DE TELEMETRIA POSTHOG — LAUS CONSOLE UI (PILAR 4)")
    print("=" * 60)

    # 1. Invocação de Skill
    capture_laus_event(
        event_name="laus_skill_invoked",
        distinct_id="agent_jarvis_core_01",
        properties={
            "skill_name": "macro-brazil",
            "pillar": 5,
            "execution_duration_ms": 142.5,
            "status": "SUCCESS"
        }
    )

    # 2. Ordem Executada
    capture_laus_event(
        event_name="laus_order_filled",
        distinct_id="agent_quant_freqtrade_02",
        properties={
            "symbol": "USDT/BRL",
            "side": "buy",
            "amount_usd": 250.0,
            "rate_brl": 5.485,
            "net_pnl_usd": 2.125,
            "environment": "shadow_paper_trading"
        }
    )
    print("=" * 60)


if __name__ == "__main__":
    run_sample_telemetry()
