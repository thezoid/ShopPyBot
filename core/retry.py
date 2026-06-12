"""Single source of exponential backoff for all retry sites (REL-08).

Provides RetryPolicy (dataclass), compute_delay (pure function), and
with_retry (async helper). Phase 22 supervisor reuses RetryPolicy +
compute_delay directly -- no plugin or models imports in this module.

Semantic note: max_attempts is the TOTAL number of call attempts.
  max_attempts=1 -> single attempt, no retry (equivalent to max_cart_retries=0).
  max_attempts=4 -> first attempt + 3 retries (equivalent to max_cart_retries=3).
Callers constructing RetryPolicy from CheckoutConfig must pass
  max_attempts = config.checkout.max_cart_retries + 1.
"""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass


@dataclass
class RetryPolicy:
    """Retry and backoff configuration.

    Fields mirror CheckoutConfig knobs (core/config_schema.py):
      max_attempts  -- total call attempts (1 = single attempt, no retry)
      backoff_base  -- exponential base; delay at attempt N = backoff_base**N
      backoff_jitter -- max random jitter added to base delay (seconds)
    """

    max_attempts: int
    backoff_base: float
    backoff_jitter: float


def compute_delay(attempt: int, policy: RetryPolicy, rng=random) -> float:
    """Return sleep duration before the next attempt (seconds).

    attempt is 0-indexed: attempt 0 -> backoff_base**0 = 1.0 for base=2.0.
    rng defaults to the random module; pass random.Random(seed) for determinism.
    Result is in [backoff_base**attempt, backoff_base**attempt + backoff_jitter].
    """
    base = policy.backoff_base ** attempt
    jitter = rng.uniform(0, policy.backoff_jitter)
    return base + jitter


async def with_retry(fn, policy: RetryPolicy, should_retry=None, on_attempt=None, rng=random):
    """Call fn() up to policy.max_attempts times with exponential backoff.

    Args:
        fn:           Async callable with no required arguments.
        policy:       RetryPolicy controlling attempts and backoff.
        should_retry: Optional callable(result) -> bool. Return True to retry.
                      None means return after the first call (no retry).
        on_attempt:   Optional async callable(attempt: int). Awaited before
                      each fn() call; 0-indexed attempt number.
        rng:          RNG source for compute_delay. Injectable for determinism.

    Returns the last result from fn().
    CancelledError from asyncio.sleep propagates to the caller (not caught here).
    """
    result = None
    for attempt in range(policy.max_attempts):
        if on_attempt is not None:
            await on_attempt(attempt)
        result = await fn()
        if should_retry is None or not should_retry(result):
            return result
        if attempt < policy.max_attempts - 1:
            await asyncio.sleep(compute_delay(attempt, policy, rng))
    return result
