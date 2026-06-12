"""Tests for core/retry.py: RetryPolicy, compute_delay, with_retry (REL-08).

Covers:
- compute_delay determinism with seeded rng
- compute_delay zero-jitter exact values
- compute_delay jitter bounded in [base**attempt, base**attempt + backoff_jitter]
- with_retry calls fn exactly max_attempts times when should_retry always returns True
- with_retry returns early when should_retry returns False
- with_retry awaits on_attempt before each call
- with_retry sleeps compute_delay between attempts but NOT after the final attempt
- CancelledError from asyncio.sleep propagates (not caught by with_retry)
"""
from __future__ import annotations

import asyncio
import random
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.retry import RetryPolicy, compute_delay, with_retry


# ---------------------------------------------------------------------------
# compute_delay tests
# ---------------------------------------------------------------------------

def test_compute_delay_zero_jitter_attempt_0():
    """backoff_base**0 == 1.0 with zero jitter."""
    policy = RetryPolicy(max_attempts=3, backoff_base=2.0, backoff_jitter=0.0)
    assert compute_delay(0, policy) == 1.0


def test_compute_delay_zero_jitter_attempt_1():
    """backoff_base**1 == 2.0 with zero jitter."""
    policy = RetryPolicy(max_attempts=3, backoff_base=2.0, backoff_jitter=0.0)
    assert compute_delay(1, policy) == 2.0


def test_compute_delay_zero_jitter_attempt_2():
    """backoff_base**2 == 4.0 with zero jitter."""
    policy = RetryPolicy(max_attempts=3, backoff_base=2.0, backoff_jitter=0.0)
    assert compute_delay(2, policy) == 4.0


def test_compute_delay_deterministic_with_seeded_rng():
    """Two fresh Random(42) instances produce identical results."""
    policy = RetryPolicy(max_attempts=3, backoff_base=2.0, backoff_jitter=0.5)
    result1 = compute_delay(1, policy, rng=random.Random(42))
    result2 = compute_delay(1, policy, rng=random.Random(42))
    assert result1 == result2


def test_compute_delay_jitter_bounded():
    """Result is in [backoff_base**attempt, backoff_base**attempt + backoff_jitter]."""
    policy = RetryPolicy(max_attempts=3, backoff_base=2.0, backoff_jitter=0.5)
    for attempt in range(3):
        result = compute_delay(attempt, policy, rng=random.Random(99))
        base = policy.backoff_base ** attempt
        assert base <= result <= base + policy.backoff_jitter


# ---------------------------------------------------------------------------
# with_retry tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_with_retry_calls_fn_max_attempts_when_should_retry_always_true():
    """with_retry calls fn exactly max_attempts times when should_retry always returns True."""
    policy = RetryPolicy(max_attempts=3, backoff_base=2.0, backoff_jitter=0.0)
    fn = AsyncMock(return_value="result")
    should_retry = MagicMock(return_value=True)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await with_retry(fn, policy, should_retry=should_retry)

    assert fn.call_count == 3
    assert result == "result"


@pytest.mark.asyncio
async def test_with_retry_returns_early_when_should_retry_false():
    """with_retry returns on first call when should_retry returns False."""
    policy = RetryPolicy(max_attempts=3, backoff_base=2.0, backoff_jitter=0.0)
    fn = AsyncMock(return_value="done")
    should_retry = MagicMock(return_value=False)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await with_retry(fn, policy, should_retry=should_retry)

    assert fn.call_count == 1
    assert result == "done"


@pytest.mark.asyncio
async def test_with_retry_no_should_retry_returns_after_first():
    """with_retry returns on first call when should_retry is None (default)."""
    policy = RetryPolicy(max_attempts=3, backoff_base=2.0, backoff_jitter=0.0)
    fn = AsyncMock(return_value="ok")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await with_retry(fn, policy)

    assert fn.call_count == 1
    assert result == "ok"


@pytest.mark.asyncio
async def test_with_retry_on_attempt_called_before_fn():
    """on_attempt(attempt) is awaited before each fn() call, with 0-indexed attempt."""
    policy = RetryPolicy(max_attempts=3, backoff_base=2.0, backoff_jitter=0.0)
    fn = AsyncMock(return_value="r")
    should_retry = MagicMock(return_value=True)
    on_attempt_calls = []

    async def on_attempt(attempt):
        on_attempt_calls.append(attempt)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await with_retry(fn, policy, should_retry=should_retry, on_attempt=on_attempt)

    assert on_attempt_calls == [0, 1, 2]


@pytest.mark.asyncio
async def test_with_retry_sleeps_between_attempts_not_after_last():
    """asyncio.sleep called max_attempts-1 times (not after final attempt)."""
    policy = RetryPolicy(max_attempts=3, backoff_base=2.0, backoff_jitter=0.0)
    fn = AsyncMock(return_value="r")
    should_retry = MagicMock(return_value=True)

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await with_retry(fn, policy, should_retry=should_retry)

    # 3 attempts: sleep between 0->1, between 1->2, but NOT after attempt 2
    assert mock_sleep.call_count == 2


@pytest.mark.asyncio
async def test_with_retry_backoff_sleep_uses_compute_delay():
    """asyncio.sleep is called with the compute_delay value (seeded rng, zero jitter)."""
    policy = RetryPolicy(max_attempts=3, backoff_base=2.0, backoff_jitter=0.0)
    fn = AsyncMock(return_value="r")
    should_retry = MagicMock(return_value=True)

    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    with patch("asyncio.sleep", side_effect=fake_sleep):
        await with_retry(fn, policy, should_retry=should_retry)

    # attempt 0 -> delay 2.0**0=1.0; attempt 1 -> delay 2.0**1=2.0
    assert sleep_calls == [1.0, 2.0]


@pytest.mark.asyncio
async def test_with_retry_propagates_cancelled_error():
    """CancelledError from asyncio.sleep propagates out of with_retry."""
    policy = RetryPolicy(max_attempts=3, backoff_base=2.0, backoff_jitter=0.0)
    fn = AsyncMock(return_value="r")
    should_retry = MagicMock(return_value=True)

    async def raise_cancelled(_delay):
        raise asyncio.CancelledError

    with patch("asyncio.sleep", side_effect=raise_cancelled):
        with pytest.raises(asyncio.CancelledError):
            await with_retry(fn, policy, should_retry=should_retry)
