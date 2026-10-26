"""Paper-only worker: durable proposals, idempotent accounting, heartbeat."""
import argparse
import asyncio
import json
from dataclasses import asdict
import os
from pathlib import Path
import signal
import time

from agents_quant.arbitrators.spread_detector import ArbitrageProposal, AsyncSpreadDetector
from core_jarvis.durable_bus import DurableEventBus
from core_jarvis.orchestrator import JarvisOrchestrator
from core_jarvis.pipeline_e2e import LausE2EPipeline
from cognition_skills.runtime import SkillRuntime
from dotenv import load_dotenv


async def run(cycles=None):
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    if os.environ.get("LAUS_ENVIRONMENT", "shadow") not in ("shadow", "homologation", "shadow_paper_trading"):
        raise ValueError("Worker only supports paper environments")
    state = Path(os.environ.get("LAUS_STATE_DIR", ".laus_state"))
    state.mkdir(parents=True, exist_ok=True)
    bus = DurableEventBus(state / "events.db")
    pipeline = LausE2EPipeline(orchestrator=JarvisOrchestrator(bus=bus))
    skills = SkillRuntime(state / "episodes.db")
    skills.register("paper-decision", lambda result: result, {"paper:audit"})

    async def consume(_, payload):
        if time.time() - payload.get("timestamp", 0) > 10:
            result = {"success": False, "status": "STALE_PROPOSAL", "proposal_id": payload["proposal_id"]}
            pipeline.ledger.record_decision(payload["proposal_id"], result)
            skills.invoke("paper-decision", {"result": result}, granted={"paper:audit"})
            return
        result = await pipeline.execute_pipeline_turn(ArbitrageProposal(**payload))
        skills.invoke("paper-decision", {"result": result}, granted={"paper:audit"})

    async def stage(proposal):
        await bus.publish("agent.proposals", asdict(proposal))

    bus.subscribe("agent.proposals", consume, consumer="paper-ledger-v1")
    await bus.recover()
    await pipeline.flush_outbox()
    detector = AsyncSpreadDetector(on_proposal_created=stage, guardrail=pipeline.guardrail)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass
    count = 0
    try:
        while not stop.is_set() and (cycles is None or count < cycles):
            # An active kill switch keeps the service alive but prevents market proposals.
            if not pipeline.orchestrator.refresh_kill_switch():
                try:
                    await detector.poll_cycle()
                except Exception as exc:
                    await bus.publish("system.market_unavailable", {"error_type": type(exc).__name__})
            (state / "worker.heartbeat").write_text(str(time.time()), encoding="utf-8")
            snapshot = state / "worker.status.json.tmp"
            snapshot.write_text(json.dumps({"timestamp": time.time(),
                "emergency_stop": pipeline.orchestrator.emergency_stop,
                "reason": pipeline.orchestrator.emergency_stop_reason}), encoding="utf-8")
            os.replace(snapshot, state / "worker.status.json")
            count += 1
            if cycles is None or count < cycles:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=detector.poll_interval_sec)
                except asyncio.TimeoutError:
                    pass
    finally:
        pipeline.ledger.conn.close()
        bus.conn.close()
        skills.conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int)
    asyncio.run(run(parser.parse_args().cycles))
