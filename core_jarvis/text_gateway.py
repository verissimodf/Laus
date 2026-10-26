"""Deterministic operator text gateway with explicit skill permissions.

No free-form shell, arbitrary Python, trading, or remote reset is available.
"""
import argparse
import json
import os
from pathlib import Path

from accounting_ledger.ledger_engine import AccountingLedger
from cognition_skills.runtime import SkillRuntime
from core_jarvis.orchestrator import JarvisOrchestrator


def command(text):
    orchestrator = JarvisOrchestrator()
    state = Path(os.environ.get("LAUS_STATE_DIR", ".laus_state"))
    state.mkdir(parents=True, exist_ok=True)
    runtime = SkillRuntime(state / "episodes.db")
    ledger = AccountingLedger(os.environ.get("LAUS_LEDGER_PATH", str(state / "paper.db")))
    runtime.register("status", lambda: {"kill_switch": orchestrator.refresh_kill_switch(),
                                      "reason": orchestrator.emergency_stop_reason}, {"system:read"})
    runtime.register("summary", ledger.get_daily_summary, {"ledger:read"})
    runtime.register("reconcile", ledger.reconcile, {"ledger:read"})

    def halt():
        orchestrator.trigger_kill_switch("Local operator text gateway")
        return {"kill_switch": True, "scope": "paper"}

    runtime.register("halt", halt, {"system:halt"})
    try:
        if text not in {"status", "summary", "reconcile", "halt"}:
            raise ValueError("Supported commands: status, summary, reconcile, halt")
        return runtime.invoke(text, {}, granted={"system:read", "ledger:read", "system:halt"})
    finally:
        ledger.conn.close()
        runtime.conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["status", "summary", "reconcile", "halt"])
    print(json.dumps(command(parser.parse_args().command), indent=2))
