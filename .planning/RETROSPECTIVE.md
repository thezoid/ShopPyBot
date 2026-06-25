# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v4.0 — Win-the-Drop

**Shipped:** 2026-06-25
**Phases:** 7 (18-24) | **Plans:** 29 | **Suite:** 755 passed, 2 skipped

### What Was Built
- Safety gate: monitor-only mode + `place_order_guarded()` ABC closing the 6-of-7 `test_mode` place-order hole (P18).
- Verified checkout: order-confirmation detection + `order_id`/`confirmed_at`/`checkout_attempts` columns — `purchased` only on a real order number (P19).
- Checkout profile + BestBuy/Amazon form-fill, CVV-at-runtime, no card data persisted (P20).
- Unified `RetryPolicy` + per-step `asyncio.timeout()` + idempotent cart-retry (P21).
- Per-coroutine supervisor + browser relaunch + DB read isolation + per-item timeout + SIGTERM/SIGINT bridge (P22).
- Fernet-encrypted session persistence via raw CDP restore, bypassing the nodriver `set_all()` bug (P23).
- Health surface (`HealthRegistry`, `get_status`, `health_degraded` alert, `shoppybot status`) + headless pygame crash guard (P24).

### What Worked
- **Foundation phase first.** P18 (safety gate + `CheckoutConfig`) had "do first, all downstream depend on it" — every later phase could be built and tested with live orders suppressed by monitor-only. No phase risked a real purchase during development.
- **Single enforcement points.** One `place_order_guarded()` on the ABC (not per-plugin patches) and one `RetryPolicy` (not per-call-site loops) — both backed by CI guards (grep/AST) that fail the build on regression.
- **Idempotency designed before its consumer.** P19 added the `order_id` anchor; P21's cart-retry read it. Designing the anchor a phase ahead of the retry that needs it avoided a double-buy redesign.
- **Clean integration close.** Integration checker verified all 6 cross-phase seams with 0 blockers; PLUGIN_API_VERSION stayed 2 (all additions additive).

### What Was Inefficient
- **Live UAT can't run on the dev box.** 17 live-environment items (confirmation/form-fill/relaunch/SIGTERM/session/headless selectors + scenarios) accumulated as deferred debt. Correct per policy, but the real acceptance bar for an acquisition bot is a live drop, which CI/dev can't exercise.
- **STATE.md drifted stale.** It froze mid-Phase-23 (status "verifying", phase table showing 18-21 "Not started") while ROADMAP.md stayed authoritative. At milestone close this forced a desync diagnosis before any action was safe.
- **ROADMAP Phase Details not pruned at v3.0 close.** Archived v3.0 phases 12-17 left full detail in the live ROADMAP, so `roadmap.analyze` false-positived them as incomplete `no_directory` phases — which would have driven an autonomous run to "re-execute" already-shipped work.

### Patterns Established
- **Foundation-phase-first** for any milestone that touches a dangerous action (place-order): ship the gate before the feature.
- **Confirmed-outcome idempotency**: never treat a UI action as success; capture a retailer-side identifier and gate retries on it.
- **Security invariants as CI guards**: AST assertion (no CVV in `writeLog` args), grep assertion (no `for attempt in range(` outside `core/retry.py`), zero-write integration test under monitor-only.
- **Explicit UAT-debt ledger** in STATE.md Deferred Items — live checks that can't run in CI are tracked, not silently dropped.

### Key Lessons
1. **Prune ROADMAP "Phase Details" at every milestone close.** Leaving archived-milestone detail in the live ROADMAP desyncs `roadmap.analyze` and can mislead a future autonomous run. (Fixed this close: live ROADMAP now collapses to per-milestone `<details>` only.)
2. **Keep STATE.md in sync, or treat ROADMAP as the sole source of truth.** A stale STATE.md cost a diagnosis step at close. Prefer reconciling STATE at phase transitions.
3. **Design idempotency anchors one phase ahead of the retry that reads them** — it removes rework and closes the double-buy window by construction.

### Cost Observations
- Model mix: not tracked this milestone.
- Notable: milestone closed via `/gsd-autonomous` lifecycle tail after the phase work + audit were already complete; the run's main value was catching the ROADMAP/STATE desync before executing anything.

---

## Cross-Milestone Trends

### Cumulative Quality

| Milestone | Tests (suite) | Notable |
|-----------|---------------|---------|
| v2.0 | 341 passed | Modular core + CredentialStore (no plaintext on disk) |
| v3.0 | 548 passed, 2 skipped | Anti-detection + ecosystem + price monitoring |
| v4.0 | 755 passed, 2 skipped | Verified checkout + always-on reliability |

### Top Lessons (Verified Across Milestones)

1. Prune archived-milestone detail from the live ROADMAP at close — keeps `roadmap.analyze` accurate and ROADMAP constant-size.
2. Single enforcement points (one ABC gate, one RetryPolicy) backed by CI guards beat per-site patches for safety-critical invariants.
