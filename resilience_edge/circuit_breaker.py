"""
Circuit Breaker de Latência e Conectividade (Pilar 6 - Resiliência de Infra)

Monitora continuamente a saúde de conexões de mercado, RTT de WebSockets e latência HTTP.
Transiciona entre CLOSED, HALF-OPEN e OPEN para proteger ordens contra flash spikes e degradação de link.
"""

import enum
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger("LausCircuitBreaker")


class CircuitState(enum.Enum):
    CLOSED = "CLOSED"        # Operação normal, ordens autorizadas
    HALF_OPEN = "HALF_OPEN"  # Estado de teste sob condições adversas
    OPEN = "OPEN"            # Circuito desarmado, ordens a mercado bloqueadas


@dataclass
class CircuitBreakerStatus:
    state: str
    last_latency_ms: float
    max_latency_threshold_ms: float
    consecutive_failures: int
    failure_threshold: int
    trip_reason: Optional[str]
    last_state_change: float


class LatencyCircuitBreaker:
    """
    Controlador de Circuit Breaker de latência de rede e saúde de infraestrutura.
    """

    def __init__(
        self,
        max_latency_ms: float = 500.0,
        failure_threshold: int = 3,
        cooldown_sec: float = 15.0,
        name: str = "primary_exchange_breaker",
    ):
        self.name = name
        self.max_latency_ms = max_latency_ms
        self.failure_threshold = failure_threshold
        self.cooldown_sec = cooldown_sec

        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._last_latency_ms = 0.0
        self._last_state_change = time.time()
        self._trip_reason: Optional[str] = None
        self._incident_history: List[Dict[str, Any]] = []

    @property
    def state(self) -> CircuitState:
        # Se estiver OPEN, verifica se o período de cooldown expirou para tentar HALF_OPEN
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_state_change >= self.cooldown_sec:
                self._state = CircuitState.HALF_OPEN
                self._last_state_change = time.time()
                logger.info(f"⚡ Circuit Breaker '{self.name}' entrou em modo HALF_OPEN (tentativa de recuperação).")
        return self._state

    def can_execute(self, expected_latency_ms: Optional[float] = None) -> bool:
        """
        Informa se novas ordens podem ser emitidas pelo sistema.
        Se expected_latency_ms for fornecido e exceder o teto, bloqueia preventivamente.
        """
        current_state = self.state
        if current_state == CircuitState.OPEN:
            return False

        if expected_latency_ms is not None and expected_latency_ms > self.max_latency_ms:
            self.record_failure(
                reason=f"Latência projetada de {expected_latency_ms:.1f}ms excede teto de {self.max_latency_ms}ms",
                latency_ms=expected_latency_ms,
            )
            return False

        return True

    def record_success(self, latency_ms: float):
        """Registra uma operação bem-sucedida com sua respectiva latência."""
        self._last_latency_ms = latency_ms

        if latency_ms > self.max_latency_ms:
            self.record_failure(
                reason=f"Latência medida de {latency_ms:.1f}ms ultrapassou limite de {self.max_latency_ms}ms",
                latency_ms=latency_ms,
            )
            return

        # Recuperação em caso de sucesso
        self._consecutive_failures = 0
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._last_state_change = time.time()
            self._trip_reason = None
            logger.info(f"✅ Circuit Breaker '{self.name}' restabelecido para CLOSED após validação.")

    def record_failure(self, reason: str, latency_ms: Optional[float] = None):
        """Registra falha de comunicação ou estouro de latência."""
        self._consecutive_failures += 1
        if latency_ms is not None:
            self._last_latency_ms = latency_ms

        logger.warning(f"⚠️ Circuit Breaker '{self.name}' falha ({self._consecutive_failures}/{self.failure_threshold}): {reason}")

        if self._consecutive_failures >= self.failure_threshold or self._state == CircuitState.HALF_OPEN:
            self.trip_breaker(reason)

    def trip_breaker(self, reason: str):
        """Força o desarmamento imediato do circuito para o estado OPEN."""
        self._state = CircuitState.OPEN
        self._last_state_change = time.time()
        self._trip_reason = reason
        self._incident_history.append({
            "timestamp": self._last_state_change,
            "reason": reason,
            "consecutive_failures": self._consecutive_failures,
        })
        logger.critical(f"🚨 CIRCUIT BREAKER TRIP: '{self.name}' DESARMADO -> OPEN! Motivo: {reason}")

    def reset(self):
        """Força o reset do circuito para o estado CLOSED."""
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._trip_reason = None
        self._last_state_change = time.time()
        logger.info(f"Circuit Breaker '{self.name}' resetado manualmente.")

    def get_status(self) -> CircuitBreakerStatus:
        """Retorna o status estruturado do circuito."""
        return CircuitBreakerStatus(
            state=self.state.value,
            last_latency_ms=self._last_latency_ms,
            max_latency_threshold_ms=self.max_latency_ms,
            consecutive_failures=self._consecutive_failures,
            failure_threshold=self.failure_threshold,
            trip_reason=self._trip_reason,
            last_state_change=self._last_state_change,
        )


if __name__ == "__main__":
    cb = LatencyCircuitBreaker(max_latency_ms=500.0, failure_threshold=2, cooldown_sec=1.0)
    print("Testando LatencyCircuitBreaker...")
    print("Can execute (50ms):", cb.can_execute(50.0))
    cb.record_success(50.0)
    print("State:", cb.get_status().state)

    print("\nSimulando spike de 600ms...")
    cb.record_failure("Spike 600ms", 600.0)
    cb.record_failure("Spike 620ms", 620.0)
    print("Can execute:", cb.can_execute())
    print("State:", cb.get_status().state, "| Reason:", cb.get_status().trip_reason)
