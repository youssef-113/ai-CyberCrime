"""
Retry and Circuit Breaker Utilities for Microservice Calls

Implements exponential backoff with jitter and circuit breaker pattern
for resilient microservice communication.
"""

import asyncio
import logging
import time
from typing import Callable, Any, Optional, TypeVar, Awaitable
from enum import Enum

logger = logging.getLogger("api.retry")

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker for preventing cascading failures
    
    Patterns:
    - CLOSED: All requests pass through
    - OPEN: Requests are rejected immediately (fail-fast)
    - HALF_OPEN: Allow limited requests to test if service recovered
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker entering HALF_OPEN state")
            else:
                raise Exception(
                    f"Circuit breaker OPEN - service unavailable (recovery in "
                    f"{self.recovery_timeout - (time.time() - self.last_failure_time):.0f}s)"
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    async def call_async(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """Execute async function with circuit breaker protection"""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker entering HALF_OPEN state")
            else:
                raise Exception(
                    f"Circuit breaker OPEN - service unavailable"
                )
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery"""
        return (
            self.last_failure_time and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    def _on_success(self):
        """Reset failure counter on success"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        """Increment failure counter and possibly open circuit"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker OPEN after {self.failure_count} failures"
            )


async def retry_with_backoff(
    func: Callable[..., Awaitable[T]],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    *args,
    **kwargs
) -> T:
    """
    Retry async function with exponential backoff and jitter
    
    Args:
        func: Async function to call
        max_retries: Maximum number of retry attempts
        initial_delay: Starting delay in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
        jitter: Add random jitter to delays
        *args, **kwargs: Arguments to pass to func
    
    Returns:
        Result from successful function call
    
    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            if attempt >= max_retries:
                logger.error(
                    f"All {max_retries} retries exhausted for {func.__name__}: {str(e)}"
                )
                raise
            
            # Calculate delay with exponential backoff
            delay = min(
                initial_delay * (exponential_base ** attempt),
                max_delay
            )
            
            # Add jitter (±20%)
            if jitter:
                import random
                jitter_amount = delay * 0.2
                delay = delay + random.uniform(-jitter_amount, jitter_amount)
                delay = max(delay, initial_delay * 0.5)  # Don't go below 50% of initial
            
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries} for {func.__name__} failed: {str(e)} "
                f"(retrying in {delay:.2f}s)"
            )
            
            await asyncio.sleep(delay)
    
    raise last_exception


def get_retry_config_for_service(service_name: str) -> dict:
    """
    Get optimized retry configuration for a specific service
    
    Different services need different retry strategies:
    - OCR: Long timeout, higher retries (model loading)
    - Classifier: Medium timeout, few retries (LLM calls)
    - RAG: Medium timeout, more retries (embeddings)
    - Verification: Long timeout, few retries (agent loops)
    - PDF: Medium timeout, few retries (rendering)
    - Chatbot: Long timeout, few retries (LLM)
    """
    configs = {
        "ocr": {
            "timeout": 60.0,
            "max_retries": 2,
            "initial_delay": 1.0,
            "max_delay": 30.0,
        },
        "classifier": {
            "timeout": 30.0,
            "max_retries": 1,
            "initial_delay": 0.5,
            "max_delay": 10.0,
        },
        "rag": {
            "timeout": 30.0,
            "max_retries": 2,
            "initial_delay": 0.5,
            "max_delay": 15.0,
        },
        "verification": {
            "timeout": 90.0,
            "max_retries": 1,
            "initial_delay": 1.0,
            "max_delay": 10.0,
        },
        "pdf": {
            "timeout": 30.0,
            "max_retries": 1,
            "initial_delay": 0.5,
            "max_delay": 10.0,
        },
        "chatbot": {
            "timeout": 60.0,
            "max_retries": 1,
            "initial_delay": 1.0,
            "max_delay": 10.0,
        },
    }
    return configs.get(service_name, configs["ocr"])  # Default to OCR config


class ServiceCallError(Exception):
    """Raised when a microservice call fails"""
    def __init__(self, service: str, error: str, status_code: Optional[int] = None):
        self.service = service
        self.error = error
        self.status_code = status_code
        super().__init__(f"{service} service error: {error}")


def format_error_response(service: str, error: Exception, status_code: int = 502) -> dict:
    """Format microservice error for API response"""
    error_msg = str(error)
    
    return {
        "error": {
            "service": service,
            "message": error_msg,
            "type": type(error).__name__,
        },
        "status_code": status_code,
    }
