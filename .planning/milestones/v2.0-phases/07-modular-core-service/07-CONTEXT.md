# Phase 7: Modular Core Service - Context

**Gathered:** 2026-06-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Refactor the v1 code so all bot logic lives behind a single importable `BotService` API that every front-end (the `python main.py` shim now, the CLI in Phase 9, the web UI in Phase 10) calls; make the package pip-installable with a `shoppybot` entry point. Covers MOD-01, MOD-02, MOD-03.

NOT in scope: the full `cli/` package (Phase 9), the credential store (Phase 8 — BotService accepts secrets as parameters for now), the web UI (Phase 10), cross-platform CI (Phase 11). This is an internal refactor: NO behavior change, the existing 214-test suite must stay green unmodified.
</domain>

<decisions>
## Implementation Decisions

### BotService API & Async Model (MOD-01)
- `core/service.py` defines `BotService` wrapping registry + orchestrator + config. It exposes every operation front-ends need: `start(...)`, `stop()`, `list_items()`, `add_item(...)`, `remove_item(...)`, `get_status()`, `get_config()`.
- `start()` launches the async orchestrator in a BACKGROUND task/thread and returns (so a web UI can call it without blocking); `stop()` signals shutdown via an asyncio.Event / cancellation so teardown_all runs. A blocking convenience (`run()`) wraps start + wait for the CLI/shim.
- The core service NEVER calls `getpass` or reads interactive input. The front-end collects secrets (CVV via getpass, env/cred values) and passes them INTO `start(...)`. This keeps the service usable from the web UI (which cannot prompt) and from Phase 8's credential store.
- `get_status()` / `list_items()` return sync, plain data (running state, item list as plain tuples/dicts) that any front-end renders. Front-ends do NOT touch the registry, orchestrator, or DB directly.

### Package Layout (MOD-03) — lowest-risk refactor
- Keep `core/`, `plugins/`, `notifications/` exactly where they are (NO move into src/). Add a `pyproject.toml` declaring those packages + a `shoppybot` console entry point. This avoids rewriting every import and minimizes risk to the green suite.
- Entry point: `shoppybot = "core.service:main"` where `core/service.py` has a module-level `main()` that runs the service (a real `cli/` home arrives in Phase 9).
- `pip install -e .` must succeed on Ubuntu and Windows.

### main.py Shim (MOD-02/MOD-03)
- `main.py` becomes a THIN shim: it preserves the v1 pre-flight (AppConfig validation, DB seed, getpass CVV gate), then collects/forwards secrets into `BotService(...).run(...)`. `python main.py` keeps working and delegates immediately to the service.
- The shim is the only place that bypasses nothing meaningful — it IS a front-end and must go through BotService for the actual run; pre-flight validation/secret collection is allowed in the shim.

### Phase 7 Boundary
- Phase 7 delivers `core/service.py` + `pyproject.toml` + the `main.py` shim ONLY. The full `cli/` package and MOD-02's `cli/` grep test land in Phase 9 (no `cli/` dir exists yet in Phase 7). Phase 7 still proves the boundary by routing the shim through BotService.

### Claude's Discretion
- Exact BotService method signatures, the background-run mechanism (asyncio task vs thread+loop — pick what cleanly supports start/stop from both sync and async callers), the pyproject build backend (setuptools), and how get_status reports running state, provided the locked decisions hold and the 214-test suite stays green.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/orchestrator.py` `async_main(cfg, cvv)`: the async run loop BotService.start wraps in a background task + a stop signal.
- `core/registry.py` PluginRegistry: discovery/lifecycle the service owns.
- `core/config_schema.py` AppConfig: config load/validation the service exposes via get_config.
- `models.py` `*_sync` functions (get_items_sync/add_items_sync/update_item_purchased_sync): list_items/add_item/remove_item delegate here (add a remove_item_sync if missing).
- `main.py`: current entry (AppConfig validation, DB seed, getpass CVV gate, asyncio.run(async_main)) — becomes the shim; preserve the pre-flight, route the run through BotService.

### Established Patterns
- Async + run_in_executor for blocking I/O (Phase 4); secrets passed in, never getpass-ed in the loop.
- One nodriver Browser per plugin; teardown_all on shutdown — stop() must trigger this.
- 214 tests green; this refactor changes structure, not behavior — tests must pass unmodified.

### Integration Points
- BotService is the seam between front-ends (main.py shim now; cli/, web/ later) and the engine (registry + orchestrator + config + models).
- stop() must cleanly cancel the background run + teardown browsers (no orphaned Chrome).
</code_context>

<specifics>
## Specific Ideas

- Success criterion 4 is the guardrail: the existing suite passes WITHOUT modification. If a test must change, that signals a behavior regression — stop and reconsider.
- get_status/list_items must be callable without starting the bot (web UI shows state before run).
- Keep `python main.py` working verbatim for users who never adopt the new entry point.
</specifics>

<deferred>
## Deferred Ideas

- Full `cli/` package + `shoppybot` subcommands (Phase 9).
- Credential store (Phase 8) — until then BotService takes secrets as params / reads env as today.
- Web UI (Phase 10); cross-platform CI matrix (Phase 11).
</deferred>

---

*Phase: 7-modular-core-service*
*Context gathered: 2026-06-03*
