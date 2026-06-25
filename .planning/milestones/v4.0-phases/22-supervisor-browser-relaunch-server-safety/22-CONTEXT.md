# Phase 22: Supervisor + Browser Relaunch + Server Safety - Context

**Gathered:** 2026-06-12
**Status:** Ready for planning

<domain>
## Phase Boundary

A single plugin crash or browser death cannot take down the rest of the bot; plugins restart automatically with backoff and full stealth/proxy/login restoration; the bot shuts down cleanly on SIGTERM (REL-01, REL-02, REL-03, REL-05, REL-06, SRV-02).

Deliverables:
1. A `supervise()` wrapper per plugin that absorbs all exceptions before the `asyncio.TaskGroup` boundary, restarts with exponential backoff (shared `RetryPolicy`), and parks after a failure budget (REL-01, REL-02).
2. A concrete `relaunch()` ABC method (teardown → proxy → setup+stealth → restore_session stub → login) the supervisor calls on browser death (REL-03).
3. SQLite read-path error isolation in `run_plugin` (REL-05).
4. Per-item `asyncio.timeout(item_timeout_secs)` around each check/buy cycle — the per-item ceiling deferred from Phase 21 (REL-06).
5. SIGTERM/SIGINT cooperative teardown bridge (write-queue flush + browser teardown), platform-appropriate for Windows (SRV-02).

Out of scope: real encrypted session restore (Phase 23 — this phase ships a no-op `restore_session` stub); the health surface (Phase 24).
</domain>

<decisions>
## Implementation Decisions

### Supervision Model & Failure Budget (REL-01, REL-02)
- A `supervise(plugin, ...)` wrapper coroutine runs `run_plugin` in a try/except loop and catches ALL exceptions so none reach the `asyncio.TaskGroup` boundary (REL-01). Every other plugin's coroutine keeps running.
- Failure budget threshold N = `CheckoutConfig.alert_on_errors` (default 3) within a module-constant rolling window (~600s). This reuses the existing `alert_on_errors` field (added in P18 for exactly this) rather than adding a new config section (P18 fixed the CheckoutConfig field set).
- Restart backoff is exponential via `core/retry.py` `compute_delay` (REL-08 reuse — the supervisor constructs its own `RetryPolicy` from `CheckoutConfig` backoff fields; the shared piece is the backoff math, not the cart-retry instance). The failure-count/attempt counter resets after a sustained-healthy interval.
- After the failure budget is exceeded, the plugin is PARKED (no further restart attempts) and a notification is dispatched through the existing dispatcher ("plugin X parked after N failures"). Other plugins are unaffected.

### Browser Relaunch & Lifecycle (REL-03)
- Dead/disconnected Chrome is detected by catching nodriver connection/browser-dead exceptions on tab operations within the supervised loop → triggers a relaunch.
- A concrete `relaunch()` ABC method executes the full sequence in order: `teardown()` → assign_proxy (if proxy enabled) → `setup()` (new browser + `apply_stealth` + proxy auth) → `restore_session()` (no-op stub) → `login()`. `apply_stealth` MUST be verified called on the relaunched browser (roadmap criterion 3).
- An additive `async def restore_session(self) -> bool` no-op default on the ABC returns False (Phase 23 replaces it with real Fernet cookie restore). No `PLUGIN_API_VERSION` bump (additive).
- The supervisor calls `plugin.relaunch()` on browser death before resuming the poll loop (a relaunch path within the supervised restart), rather than a full-process restart.

### Read Isolation + Per-Item Timeout + Signals (REL-05, REL-06, SRV-02)
- Each `run_in_executor` DB READ in `run_plugin` (items, notification-state, price reads) is wrapped in try/except `sqlite3.OperationalError` → log + skip this poll cycle, never crash the loop (REL-05).
- Each item's `_check_and_buy` runs under `async with asyncio.timeout(item_timeout_secs)` (from `CheckoutConfig`) — the per-item ceiling deferred from Phase 21. On timeout: log + continue to the next item. `write_queue.put()` calls stay OUTSIDE the timeout context so a timed-out item cannot orphan a pending DB write (REL-06).
- SIGTERM and SIGINT register via `loop.add_signal_handler` on POSIX; on Windows (`sys.platform == 'win32'` / `NotImplementedError`) fall back to `signal.signal`. The handler triggers cooperative teardown (SRV-02).
- On teardown (signal or normal), drain the remaining write-queue items before `registry.teardown_all()` closes browsers, so pending DB writes aren't lost.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/orchestrator.py` — `async_main` (L465) staggers setup then runs `asyncio.TaskGroup` (L497) with `_write_queue_drain` (L383) + one `run_plugin` (L172) per plugin; `teardown_all` at L511. The `supervise()` wrapper goes around `run_plugin` in the create_task call; the per-item timeout + read isolation go inside `run_plugin`; the signal bridge + write-queue flush go in `async_main`.
- `core/retry.py` (P21) — `RetryPolicy` + `compute_delay` + `with_retry`; generic, importable here for restart backoff (REL-08).
- `core/config_schema.py` — `CheckoutConfig` has `item_timeout_secs`, `alert_on_errors`, `backoff_base`, `backoff_jitter` (P18). No new fields needed.
- `core/plugin_base.py` — `setup()`/`teardown()`/`login()`; add concrete `relaunch()` + `restore_session()` no-op. `apply_stealth` is invoked in `setup()` today (confirm).
- `core/registry.py` — `assign_proxy`/proxy pool wiring; `teardown_all`.
- `core/service.py` — `_main`/`main` (L150/211); signal handling integrates with the async_main cancellation path.
- Existing notification dispatcher — used for the park notification.

### Established Patterns
- `asyncio.TaskGroup` for concurrent plugin coroutines; `run_in_executor` for blocking DB calls; write serialization via `_write_queue_drain`.
- `core/retry.py` backoff; `asyncio.timeout()` per-step (P21) — the per-item timeout mirrors this idiom one level up.
- Additive ABC hooks with no-op defaults (no API bump).
- Platform branching for Windows (e.g., the proxy/CDP code already branches on platform).

### Integration Points
- `core/orchestrator.py` (supervise wrapper, per-item timeout, read isolation, signal bridge, write-queue flush in async_main).
- `core/plugin_base.py` (relaunch() + restore_session() ABC methods).
- `core/registry.py` (assign_proxy reused in relaunch).
- `core/retry.py` (restart backoff reuse).
- Notification dispatcher (park alert).

</code_context>

<specifics>
## Specific Ideas

- RESEARCH flag (roadmap): the nodriver relaunch sequence interaction with CDP stealth script state must be validated against installed nodriver 0.50.3 — specifically whether `add_script_to_evaluate_on_new_document` persists across a `Browser.stop()` + restart or must be re-injected. plan-phase research should confirm; the relaunch() must guarantee `apply_stealth` runs on the new browser regardless.
- REL-01's "absorbed before the TaskGroup boundary" is the keystone: the supervise() wrapper must NEVER let an exception propagate out of its coroutine, or the TaskGroup cancels all siblings. A test must crash one plugin and assert the others keep running.
- The restore_session() stub returning False is the cross-phase contract Phase 23 fills (REL-04).
- The per-item timeout pairs with P21's per-step timeouts: per-step bounds each DOM action, per-item bounds the whole item cycle. write_queue.put stays outside both.

</specifics>

<deferred>
## Deferred Ideas

- Real encrypted session/cookie persistence (Fernet, CDP set_cookies restore) → Phase 23 (REL-04); this phase only ships the no-op restore_session stub.
- Health surface / per-plugin liveness + heartbeat + health_degraded alert → Phase 24 (REL-07).
- Live validation of supervisor restart + relaunch under a real browser crash → UAT debt (tracked, not blocking).

</deferred>
