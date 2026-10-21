"""
Laus Core - Jarvis Orchestrator (Pilar 1)
Central de eventos assíncronos, roteamento de intenções e despacho de agentes.
"""
import asyncio
import logging
from typing import Dict, Any, Optional

try:
    from .bus import EventBus
except ImportError:
    from bus import EventBus

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("LausJarvis")

class JarvisOrchestrator:
    def __init__(self, bus: Optional[EventBus] = None):
        self.active_agents = {}
        self.emergency_stop = False
        self.bus = bus or EventBus()
        logger.info("Jarvis Orchestrator inicializado em modo seguro.")

    async def register_agent(self, name: str, agent_instance):
        self.active_agents[name] = agent_instance
        logger.info(f"Agente registrado: {name}")

    async def dispatch_event(self, event_type: str, payload: Dict[str, Any]):
        if self.emergency_stop:
            logger.warning("DISPATCH BLOQUEADO: Kill switch ativado!")
            return {"status": "aborted", "reason": "emergency_stop"}

        logger.info(f"Processando evento: {event_type}")
        # Publica no barramento de eventos assíncrono
        await self.bus.publish(event_type, payload)
        return {"status": "dispatched", "event": event_type}

    def trigger_kill_switch(self, reason: str):
        self.emergency_stop = True
        logger.critical(f"🚨 KILL SWITCH ATIVADO! Motivo: {reason}")
        # Dispara evento síncrono/assíncrono no barramento
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.bus.publish("system.emergency", {"reason": reason, "status": "HALTED"}))
        except RuntimeError:
            pass

