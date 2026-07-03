# Phase 30: Breakfix Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-02
**Phase:** 30-breakfix-hardening
**Areas discussed:** BF-02 latch durability, BF-02 unconfirmed-order handling, BF-01 WAF fallback behavior, BF-03 verify scope + contract

> **Provenance:** Operator was away (no response within the question window). All
> selections below are Claude's best-judgment defaults against the locked ROADMAP
> success criteria and the v4.2 fail-safe/code-actionable milestone rule. Marked
> for operator review before planning.

---

## BF-02 latch durability

| Option | Description | Selected |
|--------|-------------|----------|
| In-memory per-run flag | Simple `self._order_submitted`; dies on browser relaunch / supervisor restart | |
| DB-persisted write-ahead marker | Marker written to SQLite before the click; survives crash/relaunch; reuses existing DB-read guard | ✓ |

**Choice (Claude):** DB-persisted write-ahead marker.
**Notes:** v4.0 ships browser relaunch + supervisor restart; a relaunch mid-place-order is exactly the double-buy window an in-memory flag cannot cover. `_pre_attempt_check` already re-reads DB state per attempt, so a persisted marker is a natural extension. → CONTEXT D-01/D-02.

---

## BF-02 unconfirmed-order handling

| Option | Description | Selected |
|--------|-------------|----------|
| Fail-safe abort + alert + needs-review | Once click fires, never re-click place-order; confirm once, else mark needs-review + notify; earlier stages still retryable | ✓ |
| Retry place-order after re-verify | Attempt confirmation then re-click if unconfirmed | |

**Choice (Claude):** Fail-safe abort + alert + needs-review.
**Notes:** Governing principle = miss-a-buy over risk-a-double-buy for the milestone's one HIGH item. Confirmation sentinel is barred as an idempotency key (`core/confirmation.py:26-31`). → CONTEXT D-03/D-04/D-05.

---

## BF-01 WAF fallback behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Single solve attempt then manual pause | One `solve_amazon_waf` try; any failure → manual pause; shared spend cap | ✓ |
| Retry-then-pause | Retry the WAF solve once before falling back | |

**Choice (Claude):** Single solve attempt then manual pause.
**Notes:** ~30s gokuProps freshness window makes a retry likely stale and a wasted 2captcha spend. Fallback preserved on every non-success path (disabled/no-balance/cap/API-fail/timeout/injection-fail/stale gokuProps); never hard-fail the item. WAF solves share the reCAPTCHA `_solve_count`/`max_solves_per_run` budget. → CONTEXT D-06..D-10.

---

## BF-03 verify scope + contract

| Option | Description | Selected |
|--------|-------------|----------|
| Uniform mechanism, all 7 plugins | Shared verification in ABC/helper; generic signal + platform-specific override; `login() -> bool` | ✓ |
| Mechanism + Amazon/BestBuy real signals only | Special-case the 2 live-tested platforms; leave 5 community plugins unverified | |

**Choice (Claude):** Uniform mechanism, all 7 plugins.
**Notes:** DRY + consistent safety — a failed/ambiguous login can never report success on any plugin. The 5 community plugins with "TODO" selectors use the generic signal (URL off the sign-in page + login form gone); live selector tuning stays operator debt. Contract: ABC `login() -> None` becomes `-> bool` (default `True` for login-less plugins), `PLUGIN_API_VERSION` stays 2 (additive, per v4.0 `place_order_guarded` precedent). Verified-failed login aborts the buy before checkout + alerts, also checked at the `relaunch()` call site. Ambiguous == not-success (locked by success criterion 3). → CONTEXT D-11..D-15.

---

## Claude's Discretion

- WAF token/voucher injection JS (mirror the reCAPTCHA `_inject_token` pattern).
- Precise per-platform login selectors/URL fragments (Amazon/BestBuy now; 5 others generic).
- Name/shape of the new "possibly-placed" abort exception and the DB marker column (follow `_AlreadyConfirmed` / `get_item_order_state_sync`).
- Whether "needs manual review" is a new column vs derived (marker-set AND order_id-NULL) — derived preferred if it avoids a schema addition.

## Deferred Ideas

- Live AWS-WAF auto-solve acceptance (30s gokuProps window) — operator debt.
- Live place-order-timeout double-buy edge proof — operator debt.
- Per-retailer live login-selector tuning for the 5 community plugins — community selector-TODO debt bucket.
- Auditing/extending the persisted latch to any non-Amazon plugin-local place-order timeout wrapping, if found — later cleanup.
</content>
