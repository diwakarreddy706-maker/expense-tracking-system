"""
Authoritative Circuit Breaker implementation for external services,
slow dependencies, and heavy I/O operations in AgriBOS ERP.

Prevents cascading failures and thread exhaustion by failing fast
or serving fallbacks when a dependency is degraded.
"""

import time
import threading
import logging
from functools import wraps
from typing import Callable, Any, Optional

logger = logging.getLogger('expense_tracking.resilience')


class CircuitBreakerOpenException(Exception):
    """Raised when an operation is attempted while the circuit breaker is OPEN."""
    pass


class CircuitBreaker:
    """
    Standard state-machine Circuit Breaker.
    States:
      - CLOSED: Calls pass through. Failures are counted.
      - OPEN: Calls fail immediately with fallback or CircuitBreakerOpenException.
      - HALF_OPEN: After recovery_timeout, one trial call is allowed to probe recovery.
    """
    STATE_CLOSED = 'CLOSED'
    STATE_OPEN = 'OPEN'
    STATE_HALF_OPEN = 'HALF_OPEN'

    def __init__(
        self,
        name: str = 'default',
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exceptions: tuple = (Exception,)
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions

        self._state = self.STATE_CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == self.STATE_OPEN:
                if (time.time() - self._last_failure_time) > self.recovery_timeout:
                    self._state = self.STATE_HALF_OPEN
                    logger.info("Circuit breaker [%s] transitioned to HALF_OPEN (probing recovery).", self.name)
            return self._state

    def record_success(self):
        with self._lock:
            self._failure_count = 0
            if self._state != self.STATE_CLOSED:
                logger.info("Circuit breaker [%s] recovered. Transitioned to CLOSED.", self.name)
            self._state = self.STATE_CLOSED

    def record_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.failure_threshold or self._state == self.STATE_HALF_OPEN:
                self._state = self.STATE_OPEN
                logger.warning(
                    "Circuit breaker [%s] tripped! Transitioned to OPEN. Failures: %d. Will retry after %.1fs.",
                    self.name, self._failure_count, self.recovery_timeout
                )

    def call(self, func: Callable, *args, fallback: Optional[Callable] = None, **kwargs) -> Any:
        current_state = self.state
        if current_state == self.STATE_OPEN:
            if fallback is not None:
                return fallback(*args, **kwargs)
            raise CircuitBreakerOpenException(
                f"Service '{self.name}' is temporarily unavailable (circuit breaker OPEN)."
            )

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except self.expected_exceptions as exc:
            self.record_failure()
            if fallback is not None:
                logger.warning("Circuit breaker [%s] invoked fallback due to error: %s", self.name, exc)
                return fallback(*args, **kwargs)
            raise exc

    def __call__(self, fallback: Optional[Callable] = None):
        """Decorator usage: @breaker(fallback=my_fallback)"""
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return self.call(func, *args, fallback=fallback, **kwargs)
            return wrapper
        return decorator


# Pre-configured registry for common subsystem dependencies
circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, failure_threshold: int = 5, recovery_timeout: float = 30.0) -> CircuitBreaker:
    if name not in circuit_breakers:
        circuit_breakers[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )
    return circuit_breakers[name]
