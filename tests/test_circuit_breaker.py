"""
Unit tests for Circuit Breaker implementation.
"""

from django.test import SimpleTestCase
from apps.audit.circuit_breaker import CircuitBreaker, CircuitBreakerOpenException


class CircuitBreakerTests(SimpleTestCase):
    def test_circuit_breaker_closed_on_success(self):
        breaker = CircuitBreaker(name="test_service", failure_threshold=3, recovery_timeout=0.2)
        result = breaker.call(lambda x: x * 2, 5)
        self.assertEqual(result, 10)
        self.assertEqual(breaker.state, CircuitBreaker.STATE_CLOSED)

    def test_circuit_breaker_trips_to_open_after_threshold(self):
        breaker = CircuitBreaker(name="failing_service", failure_threshold=2, recovery_timeout=0.1)

        def faulty_call():
            raise ValueError("Dependency outage")

        # Call 1: failure
        with self.assertRaises(ValueError):
            breaker.call(faulty_call)

        # Call 2: failure -> trips circuit
        with self.assertRaises(ValueError):
            breaker.call(faulty_call)

        self.assertEqual(breaker.state, CircuitBreaker.STATE_OPEN)

        # Call 3: should fast-fail without calling faulty_call
        with self.assertRaises(CircuitBreakerOpenException):
            breaker.call(faulty_call)

    def test_circuit_breaker_serves_fallback_when_open(self):
        breaker = CircuitBreaker(name="fallback_service", failure_threshold=1, recovery_timeout=0.1)

        def faulty():
            raise ConnectionError("Down")

        def fallback():
            return "cached_fallback_data"

        # Fails and triggers fallback
        res = breaker.call(faulty, fallback=fallback)
        self.assertEqual(res, "cached_fallback_data")
        self.assertEqual(breaker.state, CircuitBreaker.STATE_OPEN)

        # Open circuit directly serves fallback
        res2 = breaker.call(faulty, fallback=fallback)
        self.assertEqual(res2, "cached_fallback_data")
