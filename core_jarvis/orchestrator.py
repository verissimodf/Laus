"""
Laus Core - Jarvis Orchestrator (Pilar 1)
Central de eventos assíncronos, roteamento de intenções e despacho de agentes.
"""
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from .bus import EventBus
except ImportError:
    from bus import EventBus

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("LausJarvis")


class JarvisOrchestrator:
    def __init__(self, bus: Optional[EventBus] = None, kill_switch_path: Optional[str] = None):
        self.active_agents = {}
        default_path = Path(__file__).resolve().parents[1] / ".laus_state" / "kill_switch.json"
        self.kill_switch_path = Path(
            kill_switch_path or os.environ.get("LAUS_KILL_SWITCH_PATH", str(default_path))
        )
        self.emergency_stop, self.emergency_stop_reason = self._load_kill_switch()
        self.bus = bus or EventBus()
        logger.info(
            "Jarvis Orchestrator inicializado em modo seguro (kill switch %s).",
            "ATIVO" if self.emergency_stop else "inativo",
        )

    def _load_kill_switch(self):
        """Carrega o latch persistido; corrupção/leitura negada bloqueia por segurança."""
        try:
            with self.kill_switch_path.open("r", encoding="utf-8") as state_file:
                state = json.load(state_file)
            if not isinstance(state, dict) or not isinstance(state.get("active"), bool):
                raise ValueError("formato de estado inválido")
            return state["active"], state.get("reason")
        except FileNotFoundError:
            return False, None
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            logger.critical("Estado do kill switch ilegível; bloqueando despacho: %s", exc)
            return True, "KILL_SWITCH_STATE_UNREADABLE"

    def _persist_kill_switch(self, reason: str):
        self.kill_switch_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.kill_switch_path.with_suffix(self.kill_switch_path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as state_file:
            json.dump({"active": True, "reason": reason}, state_file)
            state_file.flush()
            os.fsync(state_file.fileno())
        os.replace(temp_path, self.kill_switch_path)

    async def register_agent(self, name: str, agent_instance):
        self.active_agents[name] = agent_instance
        logger.info("Agente registrado: %s", name)

    async def dispatch_event(self, event_type: str, payload: Dict[str, Any]):
        if self.emergency_stop:
            logger.warning("DISPATCH BLOQUEADO: Kill switch ativado!")
            return {"status": "aborted", "reason": "emergency_stop"}

        logger.info("Processando evento: %s", event_type)
        await self.bus.publish(event_type, payload)
        return {"status": "dispatched", "event": event_type}

    def trigger_kill_switch(self, reason: str):
        self.emergency_stop = True
        self.emergency_stop_reason = reason
        try:
            self._persist_kill_switch(reason)
        except OSError:
            logger.exception("Falha ao persistir kill switch; processo permanece bloqueado")
        logger.critical("KILL SWITCH ATIVADO! Motivo: %s", reason)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.bus.publish("system.emergency", {"reason": reason, "status": "HALTED"}))
        except RuntimeError:
            pass
