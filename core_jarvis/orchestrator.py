"""
Laus Core - Jarvis Orchestrator (Pilar 1)
Central de eventos assíncronos, roteamento de intenções e despacho de agentes.
"""
import asyncio
from contextlib import contextmanager
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from dotenv import load_dotenv

try:
    from .bus import EventBus
except ImportError:
    from bus import EventBus

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("LausJarvis")


class JarvisOrchestrator:
    def __init__(self, bus: Optional[EventBus] = None, kill_switch_path: Optional[str] = None):
        project_root = Path(__file__).resolve().parents[1]
        load_dotenv(project_root / ".env", override=False)
        self.active_agents = {}
        default_path = project_root / ".laus_state" / "kill_switch.json"
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

    def refresh_kill_switch(self) -> bool:
        """Refresh a persisted activation without allowing an external reset to clear the latch."""
        active, reason = self._load_kill_switch()
        if active:
            self.emergency_stop = True
            self.emergency_stop_reason = reason
        return self.emergency_stop

    @contextmanager
    def _kill_switch_write_lock(self):
        """Serialize kill-switch file updates across processes on Windows and POSIX."""
        self.kill_switch_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.kill_switch_path.with_suffix(self.kill_switch_path.suffix + ".lock")
        with lock_path.open("a+b") as lock_file:
            if os.name == "nt":
                import msvcrt

                lock_file.seek(0, os.SEEK_END)
                if lock_file.tell() == 0:
                    lock_file.write(b"\\0")
                    lock_file.flush()
                while True:
                    try:
                        lock_file.seek(0)
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                        break
                    except OSError:
                        time.sleep(0.05)
                try:
                    yield
                finally:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _write_kill_switch_state(self, state: Dict[str, Any]):
        self.kill_switch_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.kill_switch_path.with_suffix(self.kill_switch_path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as state_file:
            json.dump(state, state_file)
            state_file.flush()
            os.fsync(state_file.fileno())
        os.replace(temp_path, self.kill_switch_path)

    def _persist_kill_switch(self, reason: str):
        with self._kill_switch_write_lock():
            self._write_kill_switch_state({"active": True, "reason": reason})

    def _persist_kill_switch_reset(
        self,
        reason: str,
        expected_activation_reason: Optional[str] = None,
    ):
        with self._kill_switch_write_lock():
            persisted_active, persisted_reason = self._load_kill_switch()
            if persisted_active and persisted_reason != expected_activation_reason:
                raise ValueError(
                    "Estado do kill switch mudou em outro processo; revise o novo incidente antes do reset"
                )
            self._write_kill_switch_state({
                "active": False,
                "reason": None,
                "last_reset": {
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "reason": reason,
                },
            })

    def reset_kill_switch(self, confirmation: str, reason: str) -> bool:
        """Reset only after an explicit local confirmation and a recorded operator reason."""
        if confirmation != "RESET KILL SWITCH":
            raise ValueError("Confirmação inválida; digite RESET KILL SWITCH")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("O motivo do reset é obrigatório")
        if not self.emergency_stop:
            return False

        reset_reason = reason.strip()
        # Persist the inactive state first; keep the in-memory latch active on failure.
        self._persist_kill_switch_reset(
            reset_reason,
            expected_activation_reason=self.emergency_stop_reason,
        )
        self.emergency_stop = False
        self.emergency_stop_reason = None
        logger.warning("KILL SWITCH RESETADO pelo operador. Motivo: %s", reset_reason)
        return True

    async def register_agent(self, name: str, agent_instance):
        self.active_agents[name] = agent_instance
        logger.info("Agente registrado: %s", name)

    async def dispatch_event(self, event_type: str, payload: Dict[str, Any]):
        if self.refresh_kill_switch():
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
