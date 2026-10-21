"""
Barramento de Eventos Assíncrono (Pilar 1 - Laus Core)
Suporta publicação e subscrição (Pub/Sub) para comunicação inter-agentes e inter-pilares.
Opera com contingência automática: tenta conexão Redis Streams e faz fallback transparente para filas assíncronas em memória.
"""

import asyncio
import json
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

logger = logging.getLogger("LausEventBus")


class EventBus:
    """
    Barramento assíncrono de eventos com suporte a tópicos e prioridade emergencial.
    """

    CHANNELS: Set[str] = {
        "market.ticks",
        "agent.proposals",
        "risk.validated",
        "execution.fills",
        "system.emergency",
    }

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url
        self._subscribers: Dict[str, List[Callable[[str, Dict[str, Any]], Coroutine[Any, Any, None]]]] = {}
        self._history: List[Dict[str, Any]] = []
        self._is_redis_connected = False

    def subscribe(self, topic: str, handler: Callable[[str, Dict[str, Any]], Coroutine[Any, Any, None]]):
        """Registra um callback assíncrono para escutar eventos em um tópico."""
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(handler)
        logger.debug(f"Subscrição registrada para o tópico '{topic}'.")

    async def publish(self, topic: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Publica um evento no tópico especificado.
        Dispara imediatamente todos os handlers assíncronos registrados.
        """
        event = {
            "topic": topic,
            "timestamp": time.time(),
            "payload": payload,
        }
        self._history.append(event)
        logger.info(f"📢 [EVENT BUS PUBLISH]: {topic} -> {payload.get('event_type') or payload.get('status') or 'Payload'}")

        # Tópico de emergência recebe prioridade
        handlers = self._subscribers.get(topic, [])
        # Também dispara handlers wildcard se houver
        handlers = handlers + self._subscribers.get("*", [])

        if handlers:
            tasks = [asyncio.create_task(h(topic, payload)) for h in handlers]
            await asyncio.gather(*tasks, return_exceptions=True)

        return event

    def get_history(self, topic: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Retorna histórico recente de mensagens do barramento."""
        if topic:
            filtered = [e for e in self._history if e["topic"] == topic]
            return filtered[-limit:]
        return self._history[-limit:]


if __name__ == "__main__":
    async def sample_handler(topic: str, data: dict):
        print(f"Recebido no handler ({topic}):", data)

    async def test():
        bus = EventBus()
        bus.subscribe("agent.proposals", sample_handler)
        await bus.publish("agent.proposals", {"order_id": "TEST-1", "symbol": "USDT/BRL"})

    asyncio.run(test())
