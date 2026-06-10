# Phase 13: Anti-Detection Layer 1 — Fingerprint + Proxy - Context

**Gathered:** 2026-06-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a browser-fingerprint stealth layer and opt-in proxy rotation to the bot. At every browser startup the bot applies JS fingerprint patches (`window.chrome`, `navigator.plugins`, `navigator.languages`, screen dimensions) via a new `core/stealth.py`, and sets WebRTC Chrome preferences to prevent real-IP leaks. Users can opt into proxy rotation via a `proxy:` config section (disabled by default); the bot detects ban signals and rotates proxies, retiring failing proxies for a cooldown. Each proxy is scoped to its plugin instance (`self._proxy`) and rotated only at browser restart, never mid-session. No plugin ABC version bump.

</domain>

<decisions>
## Implementation Decisions

### Fingerprint Stealth
- Hand-rolled CDP injection: `core/stealth.py` builds the patch JS and injects it via CDP `addScriptToEvaluateOnNewDocument` (or the nodriver equivalent) at browser startup. NO new dependency (honors CLAUDE.md "no new deps unless necessary").
- Patches required: `window.chrome`, `navigator.plugins`, `navigator.languages`, screen-dimension spoofing.
- WebRTC: set Chrome preferences at launch to prevent real-IP leak through the proxy tunnel.

### Proxy Rotation
- Opt-in `proxy:` config section, disabled by default. Lists `scheme://[user:pass@]host:port` URLs.
- Accept authenticated proxies (`user:pass@`) — credentials treated as secrets, never logged plaintext. The startup log line is `Proxy rotation: enabled, pool_size=N` (no credentials).
- Rotation order: round-robin (sequential cycling) — deterministic and testable.
- Each proxy scoped to its plugin instance via `self._proxy`; rotation happens only at browser restart, not mid-session.

### Ban Detection + Retirement
- Ban signals: HTTP 403 / 429 / 503, challenge-redirect, block-phrase in response body.
- Retire a proxy after **3 consecutive failures** (configurable), with a **300s (5 min) cooldown** (configurable) before it re-enters the pool.
- On ban signal: rotate to the next proxy (at restart boundary per scoping rule above).

### Claude's Discretion
- Exact block-phrase list, config schema field names/shape (follow existing `core/config_schema.py` conventions), internal class/module structure of `core/stealth.py` and the proxy pool/manager, and how rotation integrates with `core/plugin_base.py` browser launch — all at Claude's discretion, guided by codebase conventions and RESEARCH.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/plugin_base.py` — async `setup()` builds the nodriver Browser; `self.driver` set there. Stealth + proxy hook into this launch path. `self._proxy` lives on the plugin instance.
- `core/config_schema.py` — existing config validation; the `proxy:` section schema should follow its conventions.
- `core/credentials.py` — secret-handling pattern for proxy credentials (avoid plaintext logging).
- `core/registry.py`, `core/service.py`, `core/orchestrator.py` — plugin lifecycle; restart boundary is where proxy rotation applies.

### Established Patterns
- Stack is `nodriver` (async CDP Browser), Python, SQLite. CDP is available for script injection and prefs.
- pytest under `tests/`; new logic (config parsing, rotation/threshold) needs unit coverage (STAB-03 in Phase 17 will validate v3.0 features broadly).

### Integration Points
- Browser launch in `core/plugin_base.py` subclasses (amazon/bestbuy plugins) — stealth applied at every startup.
- Config load path — new `proxy:` section, disabled by default; sample.config.yml updated.

</code_context>

<specifics>
## Specific Ideas

- Startup log line must be exactly: `Proxy rotation: enabled, pool_size=N`.
- No plugin ABC version bump (success criterion 1).
- WebRTC leak prevention is mandatory (success criterion 4).

</specifics>

<deferred>
## Deferred Ideas

- CAPTCHA solving — Phase 14 (Anti-Detection Layer 2).
- Broad test hardening for all v3.0 features — Phase 17.

</deferred>
