---
phase: 21-per-step-timeouts-unified-retry-cart-retry
plan: "01"
subsystem: core/retry
tags: [retry, backoff, REL-08, ci-guard, tdd]
dependency_graph:
  requires: [core/config_schema.py:CheckoutConfig]
  provides: [core/retry.py:RetryPolicy, core/retry.py:compute_delay, core/retry.py:with_retry]
  affects: [Phase 22 supervisor (will import RetryPolicy + compute_delay), Plan 21-03 cart-retry]
tech_stack:
  added: []
  patterns: [injectable-rng for deterministic tests, AST walk CI guard, TDD RED/GREEN]
key_files:
  created: [core/retry.py, tests/test_retry.py, tests/test_no_retry_loops.py]
  modified: []
decisions:
  - max_attempts is total attempts (1 = single, no retry); callers pass max_cart_retries+1
  - rng defaults to random module; tests use random.Random(seed) for determinism (Pitfall 3)
  - No try/except around asyncio.sleep in with_retry; CancelledError propagates (Pitfall 6)
  - AST guard uses node.target.id=="attempt" predicate; captcha/stealth poll loops exempt via "_" variable
metrics:
  duration: "5min"
  completed: "2026-06-12T01:56:42Z"
  tasks_completed: 2
  files_created: 3
---

# Phase 21 Plan 01: core/retry.py + CI AST Guard Summary

RetryPolicy dataclass + compute_delay pure function + with_retry async helper as the single exponential backoff source for REL-08; AST CI guard statically enforces the single-source invariant.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for RetryPolicy/compute_delay/with_retry | bc7ce43 | tests/test_retry.py |
| 1 (GREEN) | core/retry.py implementation | 6a8dc9e | core/retry.py |
| 2 | tests/test_no_retry_loops.py AST CI guard | 5ca7841 | tests/test_no_retry_loops.py |

## What Was Built

`core/retry.py` (71 lines): three exports consumed by Plans 21-03 and Phase 22.

- `RetryPolicy`: stdlib `@dataclass` with `max_attempts: int`, `backoff_base: float`, `backoff_jitter: float`. Fields mirror `CheckoutConfig` knobs.
- `compute_delay(attempt, policy, rng)`: pure function returning `backoff_base**attempt + rng.uniform(0, backoff_jitter)`. Injectable `rng` (defaults to `random` module) enables seeded deterministic tests.
- `with_retry(fn, policy, should_retry, on_attempt, rng)`: async loop up to `policy.max_attempts`; awaits `on_attempt(attempt)` before each call; sleeps `compute_delay` between attempts but not after the final attempt; propagates `CancelledError` (no try/except around `asyncio.sleep`).

`tests/test_retry.py` (170 lines): 12 unit tests covering compute_delay zero-jitter exact values, determinism with seeded rng, jitter bounds, with_retry max_attempts exhaustion, early-return on False should_retry, on_attempt 0-indexed callback order, sleep count (max_attempts-1), sleep delay values, CancelledError propagation.

`tests/test_no_retry_loops.py` (88 lines): AST CI guard scanning `core/`, `plugins/`, `models.py`, `main.py`. Excludes `core/retry.py` (permitted location). Flags any `ast.For` node where `target.id == "attempt"` iterates `range(...)`. Non-vacuous file guard asserts `core/retry.py` exists. Captcha (`for _ in range(_MAX_POLLS)`) and stealth (`for _ in range(len(self._entries))`) poll loops are structurally exempt via `_` variable name.

## Verification

- `pytest tests/test_retry.py tests/test_no_retry_loops.py`: 13 passed
- Full suite: 639 passed, 2 skipped (pre-existing)
- No new external dependencies (all stdlib: asyncio, random, dataclasses)

## Deviations from Plan

None. Plan executed exactly as written.

## TDD Gate Compliance

- RED commit: bc7ce43 (`test(21-01): add failing tests...`) -- ImportError confirmed
- GREEN commit: 6a8dc9e (`feat(21-01): add core/retry.py...`) -- 12 tests pass
- REFACTOR: not needed; implementation clean on first pass

## Known Stubs

None. All three exported symbols are fully implemented and tested.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. `core/retry.py` is pure stdlib (asyncio, random, dataclasses) with no I/O. Threat mitigations T-21-01 (DoS: loop bounded by max_attempts) and T-21-02 (Tampering: AST guard enforces single-backoff-source) are fully implemented.

## Self-Check: PASSED

- core/retry.py: FOUND
- tests/test_retry.py: FOUND
- tests/test_no_retry_loops.py: FOUND
- Commits bc7ce43, 6a8dc9e, 5ca7841: FOUND
