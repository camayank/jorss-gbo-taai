"""Retry pattern with exponential backoff.

Provides decorators for both async and sync functions with configurable
retry behavior, exponential backoff, and jitter.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import (
    Any,
    Callable,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    Sequence,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")
ExceptionTypes = Union[Type[Exception], Tuple[Type[Exception], ...]]


class RetryExhausted(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(
        self,
        message: str,
        attempts: int,
        last_exception: Optional[Exception] = None
    ):
        super().__init__(message)
        self.attempts = attempts
        self.last_exception = last_exception


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of retry attempts (including initial).
        base_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay between retries in seconds.
        backoff_multiplier: Multiplier for exponential backoff.
        jitter: Add random jitter to delays (0-1 range, as fraction of delay).
        retryable_exceptions: Exception types that should trigger retry.
        non_retryable_exceptions: Exception types that should not retry.
        on_retry: Callback function called on each retry.
    """
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: float = 0.1
    retryable_exceptions: ExceptionTypes = (Exception,)
    non_retryable_exceptions: ExceptionTypes = ()
    on_retry: Optional[Callable[[int, Exception, float], None]] = None

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number.

        Args:
            attempt: Current attempt number (1-indexed).

        Returns:
            Delay in seconds with exponential backoff and jitter.
        """
        # Exponential backoff
        delay = self.base_delay * (self.backoff_multiplier ** (attempt - 1))

        # Cap at max delay
        delay = min(delay, self.max_delay)

        # Add jitter
        if self.jitter > 0:
            jitter_range = delay * self.jitter
            delay = delay + random.uniform(-jitter_range, jitter_range)
            delay = max(0.0, delay)  # Ensure non-negative

        return delay

    def should_retry(self, exception: Exception) -> bool:
        """Determine if an exception should trigger a retry.

        Args:
            exception: The exception that was raised.

        Returns:
            True if the exception should trigger a retry.
        """
        # Check non-retryable first
        if self.non_retryable_exceptions:
            if isinstance(exception, self.non_retryable_exceptions):
                return False

        # Check retryable
        return isinstance(exception, self.retryable_exceptions)


def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_multiplier: float = 2.0,
    jitter: float = 0.1,
    retryable_exceptions: ExceptionTypes = (Exception,),
    non_retryable_exceptions: ExceptionTypes = (),
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
    config: Optional[RetryConfig] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for async functions with retry logic.

    Usage:
        @async_retry(max_attempts=3, base_delay=1.0)
        async def call_external_api():
            ...

        # Or with config object:
        @async_retry(config=RetryConfig(max_attempts=5))
        async def call_external_api():
            ...

    Args:
        max_attempts: Maximum retry attempts.
        base_delay: Initial delay between retries.
        max_delay: Maximum delay cap.
        backoff_multiplier: Exponential backoff multiplier.
        jitter: Random jitter factor (0-1).
        retryable_exceptions: Exceptions that trigger retry.
        non_retryable_exceptions: Exceptions that don't retry.
        on_retry: Callback on each retry.
        config: Optional RetryConfig object (overrides other params).

    Returns:
        Decorated async function with retry logic.
    """
    retry_config = config or RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        backoff_multiplier=backoff_multiplier,
        jitter=jitter,
        retryable_exceptions=retryable_exceptions,
        non_retryable_exceptions=non_retryable_exceptions,
        on_retry=on_retry,
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(1, retry_config.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    # Check if we should retry
                    if not retry_config.should_retry(e):
                        logger.debug(
                            f"Non-retryable exception in {func.__name__}: {e}"
                        )
                        raise

                    # Check if we have attempts left
                    if attempt >= retry_config.max_attempts:
                        logger.warning(
                            f"Retry exhausted for {func.__name__} "
                            f"after {attempt} attempts: {e}"
                        )
                        raise RetryExhausted(
                            f"Retry exhausted after {attempt} attempts",
                            attempts=attempt,
                            last_exception=e,
                        ) from e

                    # Calculate delay
                    delay = retry_config.calculate_delay(attempt)

                    logger.info(
                        f"Retry {attempt}/{retry_config.max_attempts} "
                        f"for {func.__name__} in {delay:.2f}s: {e}"
                    )

                    # Call retry callback if provided
                    if retry_config.on_retry:
                        retry_config.on_retry(attempt, e, delay)

                    # Wait before retry
                    await asyncio.sleep(delay)

            # Should not reach here, but handle gracefully
            raise RetryExhausted(
                f"Retry exhausted after {retry_config.max_attempts} attempts",
                attempts=retry_config.max_attempts,
                last_exception=last_exception,
            )

        return wrapper
    return decorator


def sync_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_multiplier: float = 2.0,
    jitter: float = 0.1,
    retryable_exceptions: ExceptionTypes = (Exception,),
    non_retryable_exceptions: ExceptionTypes = (),
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
    config: Optional[RetryConfig] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for sync functions with retry logic.

    Usage:
        @sync_retry(max_attempts=3, base_delay=1.0)
        def call_external_api():
            ...

    Args:
        Same as async_retry.

    Returns:
        Decorated sync function with retry logic.
    """
    retry_config = config or RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        backoff_multiplier=backoff_multiplier,
        jitter=jitter,
        retryable_exceptions=retryable_exceptions,
        non_retryable_exceptions=non_retryable_exceptions,
        on_retry=on_retry,
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(1, retry_config.max_attempts + 1):
                try:
                    return func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    if not retry_config.should_retry(e):
                        logger.debug(
                            f"Non-retryable exception in {func.__name__}: {e}"
                        )
                        raise

                    if attempt >= retry_config.max_attempts:
                        logger.warning(
                            f"Retry exhausted for {func.__name__} "
                            f"after {attempt} attempts: {e}"
                        )
                        raise RetryExhausted(
                            f"Retry exhausted after {attempt} attempts",
                            attempts=attempt,
                            last_exception=e,
                        ) from e

                    delay = retry_config.calculate_delay(attempt)

                    logger.info(
                        f"Retry {attempt}/{retry_config.max_attempts} "
                        f"for {func.__name__} in {delay:.2f}s: {e}"
                    )

                    if retry_config.on_retry:
                        retry_config.on_retry(attempt, e, delay)

                    time.sleep(delay)

            raise RetryExhausted(
                f"Retry exhausted after {retry_config.max_attempts} attempts",
                attempts=retry_config.max_attempts,
                last_exception=last_exception,
            )

        return wrapper
    return decorator


class RetryContext:
    """Context manager for retry logic.

    Provides more control over retry behavior when decorators
    aren't suitable.

    Usage:
        async with RetryContext(max_attempts=3) as ctx:
            while ctx.should_continue:
                try:
                    result = await some_operation()
                    break
                except Exception as e:
                    await ctx.handle_exception(e)
    """

    def __init__(
        self,
        config: Optional[RetryConfig] = None,
        **kwargs: Any,
    ):
        """Initialize retry context.

        Args:
            config: RetryConfig instance or kwargs for RetryConfig.
        """
        self.config = config or RetryConfig(**kwargs)
        self.attempt = 0
        self.last_exception: Optional[Exception] = None
        self._exhausted = False

    @property
    def should_continue(self) -> bool:
        """Check if retry should continue."""
        return not self._exhausted and self.attempt < self.config.max_attempts

    async def handle_exception(self, exception: Exception) -> None:
        """Handle an exception during retry.

        Args:
            exception: The exception that occurred.

        Raises:
            The exception if not retryable or exhausted.
        """
        self.last_exception = exception
        self.attempt += 1

        if not self.config.should_retry(exception):
            self._exhausted = True
            raise

        if self.attempt >= self.config.max_attempts:
            self._exhausted = True
            raise RetryExhausted(
                f"Retry exhausted after {self.attempt} attempts",
                attempts=self.attempt,
                last_exception=exception,
            ) from exception

        delay = self.config.calculate_delay(self.attempt)

        logger.info(
            f"Retry {self.attempt}/{self.config.max_attempts} in {delay:.2f}s"
        )

        if self.config.on_retry:
            self.config.on_retry(self.attempt, exception, delay)

        await asyncio.sleep(delay)

    async def __aenter__(self) -> "RetryContext":
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit async context."""
        return False  # Don't suppress exceptions
