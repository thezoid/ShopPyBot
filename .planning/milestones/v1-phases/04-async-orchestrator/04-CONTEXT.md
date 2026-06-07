# Phase 4: Async Orchestrator - Context

**Gathered:** 2026-06-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Make all active platform plugins run concurrently in one async runtime (replacing Phase 2's deliberately-sequential loop), make SQLite safe under parallel writes, and remove every blocking `input()` from the async path (replace with an `asyncio.Event` notification pattern). Covers ASYNC-01..ASYNC-05.

NOT in scope: per-platform delay/jitter/headless config (Phase 6), new platforms (Phase 6), notifications (Phase 5), plugin crash-recovery/supervision beyond what the orchestrator needs to not deadlock.
</domain>

<decisions>
## Implementation Decisions

### Concurrency Architecture (ASYNC-01, ASYNC-02)
- Primary model: an `asyncio.TaskGroup` of per-plugin coroutines running in ONE event loop (natural fit since Phase-2 plugins are async nodriver). Use `ThreadPoolExecutor` / `run_in_executor` ONLY for genuinely blocking calls (e.g. the stdin listener, any sync library work), not to thread-wrap already-async plugin work. This satisfies ASYNC-01's intent (concurrent plugins under TaskGroup).
- Contingency (research-gated): if research shows nodriver cannot safely run multiple Browser instances in a single event loop, fall back to the literal ASYNC-01 reading — one thread per plugin, each thread running its own event loop + nodriver Browser. RESEARCH MUST resolve this before planning the execution model.
- Startup stagger: initialize each plugin's driver at least 1.5s apart (ASYNC-02) to avoid ChromeDriver/CDP port conflicts; startup logs must show the stagger.
- Poll interval: a single shared, configurable interval for this phase. Per-platform delay/jitter is explicitly deferred to Phase 6.

### Manual Intervention / input() Removal (ASYNC-03)
- All blocking `input()` calls in the async path (CAPTCHA solve, Amazon passkey/OTP sign-in) are replaced with an `asyncio.Event` notify-and-wait pattern: on intervention-needed, play an alert sound + log a clear actionable message, then await an Event.
- A single dedicated stdin-listener (run in a thread via run_in_executor) sets the relevant `asyncio.Event` when the user presses Enter. No `input()` is ever called on the event loop.
- Pause scope: only the plugin needing intervention pauses (awaits its Event); other plugins keep polling concurrently.
- Amazon sign-in/OTP follows the same Event pattern; if running unattended with no resolver, that plugin's auto-buy is skipped with a logged reason rather than blocking the loop.

### SQLite Concurrency (ASYNC-04, ASYNC-05)
- Enable WAL mode and `busy_timeout=5000` on connections; wrap all connection usage in context managers (no leaked connections).
- Serialize all writes (`update_item_purchased()` and any other mutations) through a single async write queue (`asyncio.Queue` drained by one writer task) so concurrent plugins never issue simultaneous writes. Reads can proceed concurrently under WAL.
- Target: zero `database is locked` errors under sustained 60+ minute two-platform operation (success criterion 4).

### Claude's Discretion
- Orchestrator file location/structure (e.g. extend core/registry.py or a new core/orchestrator.py), the exact write-queue API shape, the stdin-listener implementation details, and logging format for overlap/stagger evidence, provided the locked decisions above hold.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/registry.py` (Phase 2): eager discovery + lazy `setup()` per plugin + `teardown_all()`; the orchestrator builds on this (it already knows which plugins have matching items).
- `core/plugin_base.py` v2: async `setup`/`check_availability`/`auto_buy`/`teardown`; plugins are already coroutine-based, enabling the single-loop TaskGroup model.
- `main.py` (Phase 2): current `async_main` sequential loop (`for item in get_items(): await ...`) — this is what Phase 4 replaces with concurrent per-plugin tasks; preserve the pre-loop getpass CVV gate + AppConfig validation.
- `plugins/shopbot_plugin_amazon.py`: contains the 5 blocking `input()` calls flagged in Phase 2 (CAPTCHA + sign-in) explicitly deferred here (ASYNC-03).
- `models.py`: `update_item_purchased`, `get_items`, `initialize_db`, `DB_PATH` — the SQLite layer to put on WAL + busy_timeout + the write queue.

### Established Patterns
- One nodriver Browser process per plugin (Phase 2 D-04) — the stagger + concurrency must respect per-plugin browser isolation.
- Sequential execution was a deliberate Phase-2 choice (D-03) precisely so Phase 4 owns concurrency — no rework of plugin internals expected, only the orchestration layer + DB layer + input() removal.
- Secrets only via env/getpass, never logged (Phase 1) — the stdin listener handles only Enter/notification signals, never credentials.

### Integration Points
- Orchestrator sits between `main.py` entry (asyncio.run + pre-flight) and the per-plugin async methods, driven by the registry.
- The write queue wraps `models.update_item_purchased`; plugins enqueue instead of calling it directly (or call a thin async wrapper that enqueues).
</code_context>

<specifics>
## Specific Ideas

- Success criteria demand observable evidence: overlapping log timestamps across plugins (concurrency), >=1.5s-apart driver-init logs (stagger), and zero `database is locked` over 60+ min. Plans should produce logging that makes these checkable.
- Research must answer the single-loop-vs-thread-per-plugin nodriver question before the execution model is finalized.
</specifics>

<deferred>
## Deferred Ideas

- Per-platform delay / jitter / headless configuration (Phase 6).
- Plugin supervision / auto-restart on browser crash (not required by ASYNC-01..05; out of scope).
- New platforms + notifications (Phases 6 and 5).
</deferred>

---

*Phase: 4-async-orchestrator*
*Context gathered: 2026-06-03*
