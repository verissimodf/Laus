#!/usr/bin/env python3
"""
Emissor de eventos para PostHog Self-Hosted.

O envio é opt-in: defina POSTHOG_ENABLED=true e POSTHOG_API_KEY com o token
público do projeto. Apenas propriedades permitidas são transmitidas.
"""
import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict

logger = logging.getLogger("LausPostHog")

ALLOWED_PROPERTIES = {
    "proposal_id",
    "symbol",
    "side",
    "amount_usd",
    "rate_brl",
    "net_profit_usd",
    "net_pnl_usd",
    "fee_usd",
    "tax_provision_brl",
    "entry_id",
    "environment",
    "swarm_consensus",
    "status",
    "guardrail_code",
    "pillar",
    "skill_name",
    "execution_duration_ms",
}


def capture_laus_event(
    event_name: str,
    distinct_id: str,
    properties: Dict[str, Any],
    host: str = "http://localhost:8000",
):
    safe_properties = {
        key: value for key, value in properties.items()
        if key in ALLOWED_PROPERTIES
    }
    payload = {
        "event": event_name,
        "distinct_id": distinct_id,
        "properties": {
            **safe_properties,
            "$lib": "laus-python-telemetry",
            "timestamp": time.time(),
        },
    }

    enabled = os.environ.get("POSTHOG_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
    project_token = os.environ.get("POSTHOG_API_KEY", "").strip()
    configured_host = os.environ.get("POSTHOG_HOST", host).strip().rstrip("/")

    if not enabled:
        logger.debug("PostHog desabilitado; evento %s não enviado.", event_name)
        return payload
    if not project_token:
        logger.warning("PostHog habilitado sem POSTHOG_API_KEY; evento %s descartado.", event_name)
        return payload
    if not configured_host.startswith(("http://", "https://")):
        logger.warning("POSTHOG_HOST inválido; evento %s descartado.", event_name)
        return payload

    endpoint = configured_host
    if not endpoint.endswith("/i/v0/e"):
        endpoint += "/i/v0/e"
    request_payload = {"token": project_token, **payload}
    request = urllib.request.Request(
        endpoint + "/",
        data=json.dumps(request_payload, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            logger.debug("PostHog respondeu HTTP %s para evento %s.", response.status, event_name)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("Falha ao enviar evento PostHog %s: %s", event_name, exc)
    return payload


def run_sample_telemetry():
    capture_laus_event(
        event_name="laus_skill_invoked",
        distinct_id="agent_jarvis_core_01",
        properties={
            "skill_name": "macro-brazil",
            "pillar": 5,
            "execution_duration_ms": 142.5,
            "status": "SUCCESS",
        },
    )


if __name__ == "__main__":
    run_sample_telemetry()
