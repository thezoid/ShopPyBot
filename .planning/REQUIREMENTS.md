# ShopPyBot — Requirements

**Current Milestone:** v4.0 Win-the-Drop (Acquisition Core + Reliability)
**Defined:** 2026-06-10

Prior milestone requirements (v1 44 + v2.0 22 + v3.0 18) are archived at
`.planning/milestones/v2.0-REQUIREMENTS.md` and `.planning/milestones/v3.0-REQUIREMENTS.md`.
This file scopes v4.0 only.

---

## v4.0 Requirements (Active — Acquisition Core + Reliability)

### Acquisition — Verified Checkout

- [x] **BUY-01**: User can run the bot in a monitor-only mode (config flag and/or `--monitor-only`) that performs stock checks and fires alerts but never places an order, enforced once at the orchestrator before `auto_buy` so it applies to every plugin uniformly.
- [x] **BUY-02**: Every plugin routes its final place-order action through a single `place_order_guarded()` concrete method on the RetailerPlugin ABC that honors `test_mode`/monitor-only, so all 7 bundled plugins (and future community plugins) cannot place a live order under test/monitor mode by default. (Closes the confirmed hole where BestBuy and 5 others ignore `test_mode`.)
- [x] **BUY-03**: After `auto_buy` returns, the orchestrator verifies a real placed order using a primary confirmation-URL signal plus an order-number backup signal (with a settle delay), capturing the order id; `purchased` is written only on a confirmed order, never on a button click.
- [x] **BUY-04**: The bot records each checkout outcome (confirmed / failed / timed-out) with the captured order id and a timestamp in the database, providing the idempotency anchor and a basis for future outcome analytics.
- [x] **BUY-05**: On a non-confirmed checkout, the bot retries up to a configurable maximum with backoff, re-reading the persisted `purchased`/outcome state before each attempt so a succeeded-but-misdetected order is never re-submitted (no double-buy).
- [x] **BUY-06**: Each checkout runs under a per-step time budget with checkout-stage tracking and a hard per-item ceiling, so a slow step aborts cleanly (no half-submitted order, no orphaned browser state) rather than starving the drop window.
- [x] **BUY-07**: User can configure a shipping/billing profile that the bot fills during checkout on BestBuy and Amazon; payment uses the retailer-saved method plus CVV entered at runtime, and no full card number is persisted to disk or logs.

### Always-On Reliability

- [ ] **REL-01**: A supervisor wraps each plugin task so an unhandled exception in one plugin is absorbed before the asyncio TaskGroup boundary and that plugin restarts with exponential backoff, while every other plugin keeps running.
- [ ] **REL-02**: A plugin that exceeds a failure budget (N failures within a time window) is parked instead of crash-looping, and the operator is notified through the existing dispatcher.
- [x] **REL-03**: The bot detects a dead or disconnected Chrome process and cold-restarts that plugin's browser, re-applying stealth, proxy assignment, and login before resuming checks.
- [ ] **REL-04**: User can opt in to encrypted session/cookie persistence so the bot restores browser cookies across restarts (skipping re-login/MFA); cookies are encrypted via the existing CredentialStore machinery (never plaintext) and restored via the CDP path that avoids the nodriver `set_all()` bug.
- [ ] **REL-05**: Transient SQLite errors on the read path (item reads, notification-state reads, price reads) are caught and isolated so a single failed read degrades gracefully instead of crashing the poll loop.
- [ ] **REL-06**: Each item's check/buy cycle runs under an overall orchestrator timeout, so a stalled page or a long captcha pause on one item cannot freeze the other items on that retailer.
- [ ] **REL-07**: `BotService.get_status()` returns a structured per-plugin health surface (liveness, last-activity, last-error) queryable from the CLI and web UI, and sustained degradation is signaled through the notification dispatcher.
- [x] **REL-08**: Supervisor-restart (REL-01) and cart-retry (BUY-05) share one `RetryPolicy` implementation, so backoff behavior is defined in a single place and the two retry concepts cannot diverge or compound.

### Server Safety (opportunistic)

- [ ] **SRV-01**: The sound notifier degrades to a silent no-op on a headless host with no audio device instead of crashing at import, so the bot runs unattended on a server.
- [ ] **SRV-02**: SIGTERM and SIGINT trigger cooperative teardown (write-queue flush + browser teardown) so a container/systemd stop does not orphan Chrome; the signal bridge uses a platform-appropriate path (Windows has no `loop.add_signal_handler`).

---

## Future Requirements (Deferred to v4.1+)

- Request/API-mode (hybrid) checkout — faster than DOM, but per-site reverse-engineering and an arms race.
- Multi-account / multi-profile parallel attempts per item — most ToS-hostile; opt-in if ever.
- Checkout profile form-fill for the remaining 5 retailers (v4.0 covers BestBuy + Amazon).
- Richer health/observability on the web dashboard (beyond the CLI/status payload).
- Outcome analytics (success rate, time-to-checkout) built on the BUY-04 outcome records.

---

## Out of Scope (v4.0)

- Virtual-waiting-room / queue survival (Queue-it, PerimeterX press-and-hold, Akamai `_abck`, DataDome) — behavioral bot managers, not token CAPTCHAs; an arms race with no reliable open-source lever.
- Amazon WAF CAPTCHA auto-solve — re-deferred (`.planning/todos/pending/waf-auto-solve-followup.md`); manual-pause fallback remains.
- Storing full payment card / PAN anywhere — PCI scope; v4.0 relies on retailer-saved payment + CVV-at-runtime only.
- Captcha harvesting / solver farms.
- Public-release hardening (git-history scrub/squash, release-please tagging) — belongs to a dedicated release milestone (SEED-001, SEED-002).
- End-to-end live retail checkout tests in CI — legal/ToS risk; confirmation selectors are verified by manual UAT instead.

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BUY-01 | Phase 18 | Complete |
| BUY-02 | Phase 18 | Complete |
| BUY-03 | Phase 19 | Complete |
| BUY-04 | Phase 19 | Complete |
| BUY-05 | Phase 21 | Complete |
| BUY-06 | Phase 21 | Complete |
| BUY-07 | Phase 20 | Complete |
| REL-01 | Phase 22 | Pending |
| REL-02 | Phase 22 | Pending |
| REL-03 | Phase 22 | Complete |
| REL-04 | Phase 23 | Pending |
| REL-05 | Phase 22 | Pending |
| REL-06 | Phase 22 | Pending |
| REL-07 | Phase 24 | Pending |
| REL-08 | Phase 21 | Complete |
| SRV-01 | Phase 24 | Pending |
| SRV-02 | Phase 22 | Pending |
