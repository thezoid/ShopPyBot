---
phase: 10-optional-web-ui
reviewed: 2026-06-04T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - web/__init__.py
  - web/security.py
  - web/log_reader.py
  - web/config_web.py
  - web/routes/api.py
  - web/routes/credentials.py
  - web/routes/config.py
  - web/routes/pages.py
  - core/cli/web.py
findings:
  critical: 3
  warning: 5
  info: 3
  total: 11
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-06-04
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

This is a localhost FastAPI dashboard that manages secret credentials over HTTP. The
security model (no secret values in responses, origin-checked POSTs, non-local bind
warning) is mostly implemented correctly in `web/routes/credentials.py` and
`web/routes/config.py`. However the review confirms three BLOCKER-class defects:

1. `web/routes/api.py` contains DUPLICATE `GET`/`POST /credentials` routes. Because
   `api_router` is included before `credentials_router` (both under `/api`), the api.py
   handlers win and the api.py `POST /credentials` has NO `SECRET_KEYS` allowlist gate.
   This permits arbitrary key injection into the credential store. The hardened
   `credentials.py` route is dead code as wired.
2. `write_web_config` writes the scalar `notifications.sound` key as a nested
   `{"sound": {"enabled": ...}}` object, corrupting `config.yml` so the next config
   load fails Pydantic validation (bool field receiving a dict).
3. `check_origin` allows any cross-origin POST whose Origin hostname is a loopback
   literal (`127.0.0.1`/`localhost`/`::1`) regardless of the server's actual host,
   weakening the CSRF guard for a non-local bind.

Secret leakage was checked end to end and is clean in the canonical paths: the
credentials GET returns name + is_set only, the dashboard template renders no secret
values and uses no `| safe`, and `log_reader` reads existing log lines without
introducing new secret exposure.

## Critical Issues

### CR-01: Duplicate /credentials routes bypass the SECRET_KEYS allowlist (arbitrary key injection)

**File:** `web/routes/api.py:106-124` (shadows `web/routes/credentials.py:18-44`); wiring at `web/__init__.py:37-38`
**Issue:** Both `api.py` and `credentials.py` register `GET /credentials` and
`POST /credentials`, both mounted under the `/api` prefix. In `create_app`,
`api_router` is included on line 37 BEFORE `credentials_router` on line 38. FastAPI
matches the first registered route for a path, so the api.py handlers serve all
`/api/credentials` traffic and the hardened credentials.py handlers are unreachable
dead code. The api.py `POST /credentials` (lines 118-124) does:

```python
get_store().set(body["key"], body["value"])
```

with no `if body["key"] not in SECRET_KEYS` gate. Any caller that passes `check_origin`
(e.g. same-origin JS, or any loopback Origin per CR-03) can write an arbitrary,
attacker-chosen key into the process credential store. With the EnvVarBackend this
mutates `os.environ` for the running process; with keyring/file backends it pollutes
the persisted store with arbitrary keys. It also raises an unhandled `KeyError` if
`key` or `value` is missing from the body (500 with stack context).
**Fix:** Delete the duplicate credential handlers from `web/routes/api.py` (lines
106-124 and the unused `import base64` is still needed for items, keep it; remove the
`from core.credentials import ...` lines that belong only to the deleted handlers).
Rely solely on the gated `web/routes/credentials.py`. After removal, confirm only one
`/api/credentials` route exists:

```python
# web/routes/api.py -- remove lines 102-124 entirely (the Credentials block).
# credentials.py already provides GET/POST /credentials with the SECRET_KEYS gate.
```

### CR-02: write_web_config corrupts config.yml for notifications.sound (scalar written as nested object)

**File:** `web/config_web.py:53-80`
**Issue:** `notifications.sound` is registered as a 3-tuple
`("notifications", "sound", bool)` (line 17), but `notifications.sound` is a scalar
`bool` field on `NotificationsConfig` (`core/config_schema.py:197`), not a nested
section. The write logic branches on `len(entry)`: any 3-tuple takes the "notifier-style"
else branch (lines 75-78), which writes:

```python
data["notifications"]["sound"]["enabled"] = coerced   # -> {"sound": {"enabled": true}}
```

The correct shape is `{"sound": true}`. After this write, the next `AppConfig` load
will fail Pydantic validation because `sound: bool` receives a dict, breaking config
loading for the whole bot (CLI and web). The discord/email/sms toggles are correct
because they genuinely are nested under `notifications.<channel>.enabled`.
**Fix:** Distinguish a true scalar-under-section from a nested toggle rather than keying
purely on tuple length. Simplest: make `notifications.sound` a 2-tuple
`("notifications", bool)` so it flows through the 2-tuple branch (which writes
`data["notifications"]["sound"] = coerced` using the full key as the leaf), or branch
on whether `sub_key == key.split(".")[1]` differs from the leaf. Recommended:

```python
WEB_ALLOWLIST = {
    **ALLOWLIST,
    "notifications.sound": ("notifications", bool),  # scalar -> 2-tuple
    "notifications.discord.enabled": ("notifications", "discord", bool),
    ...
}
```

Then ensure the 2-tuple branch uses the leaf name, not the full dotted key, as the YAML
key (see CR/WR note below): `data.setdefault(section, {})[key.split(".")[-1]] = coerced`.

### CR-03: check_origin accepts any loopback Origin even when server is bound non-local (CSRF gap)

**File:** `web/security.py:46`
**Issue:** The origin check passes when `hostname in _LOCAL_HOSTS`
(`{"127.0.0.1","localhost","::1"}`) regardless of the server's actual host. When the
dashboard is bound to a non-local interface (the explicitly warned-about deployment),
this means a request whose Origin is `http://127.0.0.1` (which a local attacker process
or a victim's own browser visiting attacker content can sometimes forge for fetch, and
which always passes for any locally-hosted malicious page) is accepted as same-origin
even though the real server host differs. The allowlist union with `_LOCAL_HOSTS` defeats
the point of comparing against `server_host` for the non-local-bind threat model that the
banner and stderr warning exist to address. The check should be: Origin host must equal
the server host (loopback comparison is already covered when the server itself is
loopback).
**Fix:** Drop the unconditional `_LOCAL_HOSTS` escape hatch; compare against the actual
server host only (optionally also accept loopback literals only when the server host is
itself loopback):

```python
server_host = request.url.hostname or "127.0.0.1"
allowed = {server_host}
if is_localhost(server_host):
    allowed |= _LOCAL_HOSTS
if hostname not in allowed:
    raise HTTPException(status_code=403, detail="CSRF: origin rejected")
```

Also consider: a missing Origin header is treated as same-origin and allowed (line 42).
That is standard for form posts, but combined with no token it means any client that
omits Origin (curl, non-browser local malware) bypasses the check entirely. Acceptable
for the localhost threat model only; documented here as a known limitation.

## Warnings

### WR-01: bot/stop uses deprecated get_event_loop in an async context

**File:** `web/routes/api.py:56`
**Issue:** `asyncio.get_event_loop().run_in_executor(...)` inside an async handler is
deprecated (Python 3.12+ emits a DeprecationWarning) and can return the wrong loop in
some runner configurations. The intent (offload the blocking 15s `svc.stop()` off the
event loop) is correct, but the API used is the deprecated one.
**Fix:** Use the running-loop accessor or the high-level helper:

```python
await asyncio.to_thread(svc.stop)
# or: loop = asyncio.get_running_loop(); await loop.run_in_executor(None, svc.stop)
```

### WR-02: add_item handler trusts client body with no validation; KeyError -> 500

**File:** `web/routes/api.py:81-88`
**Issue:** `add_item` reads `body["name"]`, `body["link"]`, `body["auto_buy"]`,
`body["quantity"]` directly. A missing field raises `KeyError` surfacing as an unhandled
500. There is no server-side validation of `link` (must be a URL the bot can route),
`quantity` (must be a positive int), or `auto_buy` (must be bool). CLAUDE.md requires all
external input validated server-side; the dashboard JS validates name/url client-side
only, which is trivially bypassed. Bad rows silently break the bot loop's URL routing.
**Fix:** Use `body.get(...)` with explicit presence/type checks and return 422 on invalid
input, mirroring the credentials/config routes:

```python
name = (body.get("name") or "").strip()
link = (body.get("link") or "").strip()
if not name or not link:
    return JSONResponse({"status": "error", "detail": "name and link required"}, status_code=422)
try:
    quantity = int(body.get("quantity", 1))
except (TypeError, ValueError):
    return JSONResponse({"status": "error", "detail": "quantity must be an integer"}, status_code=422)
```

### WR-03: bot/start and bot/stop have a check-then-act race; start() blocks the event loop

**File:** `web/routes/api.py:40-47` and `50-57`
**Issue:** Two issues. (1) `bot_start` checks `get_status().running` then calls
`svc.start()` non-atomically. `BotService.start()` is itself guarded (service.py:81), so
this is defense-in-depth only, but the handler's own pre-check can race with concurrent
requests and return inconsistent status. (2) `svc.start()` (service.py:117) blocks up to
5 seconds on `ready.wait(timeout=5.0)` and is called directly on the event loop, stalling
all other HTTP requests during startup. The stop path was correctly offloaded
(run_in_executor) but the start path was not.
**Fix:** Offload start the same way stop is offloaded:

```python
await asyncio.to_thread(svc.start)
```

### WR-04: Dead/misleading unpacking line in write_web_config

**File:** `web/config_web.py:60`
**Issue:** `_, *path_parts, typ = entry if len(entry) == 3 else (*entry, str)` assigns
`path_parts` and `typ`, neither of which is ever used: coercion uses `entry[-1]` (line
64) and the YAML key derivation uses `entry[0]`/`entry[1]` directly (lines 72-78). The
line is dead code that obscures the actual control flow and contributed to the CR-02 bug
going unnoticed.
**Fix:** Remove line 60 entirely; it has no effect on behavior.

### WR-05: 2-tuple config write uses the full dotted key as the YAML leaf

**File:** `web/config_web.py:74`
**Issue:** For 2-tuple (CLI-style) entries the code writes
`data.setdefault(section, {})[key] = coerced` where `key` is the full allowlist key. For
`test_mode`/`logging_level` the key has no dot so this happens to be correct
(`data["debug"]["test_mode"]`). But this is fragile: any future 2-tuple key containing a
dot would write the wrong (dotted) leaf, and it is inconsistent with the 3-tuple branch
which correctly uses `key.split(".")[-1]`. Combined with the CR-02 fix (moving
`notifications.sound` to a 2-tuple) this becomes an active bug, since the leaf must be
`sound`, not `notifications.sound`.
**Fix:** Use the leaf consistently: `data.setdefault(section, {})[key.split(".")[-1]] = coerced`.

## Info

### IN-01: Stale planning comments left in production route file

**File:** `web/routes/api.py:103` ("Plans 04/05 will fill these bodies"), `127` ("Config routes live in ...")
**Issue:** Comments referencing planning phases remain in the shipped file. The line 103
comment is also now incorrect (the bodies were filled, then duplicated). After removing
the duplicate credential routes (CR-01), these comments should go too.
**Fix:** Delete the stale planning comments.

### IN-02: log_reader is unbounded read of the full log file

**File:** `web/log_reader.py:20-21`
**Issue:** `read_text()` loads the entire day's log into memory then slices the last n
lines. For a long-running bot with a large daily log this reads the whole file each poll
(every 2s per the dashboard). Out of v1 performance scope, but flagged because it is a
correctness-adjacent robustness concern: a very large log file could spike memory on each
poll. Functionally correct otherwise.
**Fix:** If addressed later, read from the end (seek-based tail) or cap bytes read. No
change required for v1 correctness.

### IN-03: is_localhost relies on literal/loopback only; documented hostnames not resolved

**File:** `web/security.py:11-31`
**Issue:** `is_localhost` correctly handles `127.0.0.1`, `localhost`, `::1`, bracketed
and bare IPv6, and IPv4:port. It does not resolve arbitrary hostnames that may map to
loopback (e.g. a custom `/etc/hosts` alias). This is intentional and safe (fail-closed:
unknown host -> treated as non-local -> warning shown), so no action needed; noting for
completeness. The IPv4:port stripping via `rsplit(":", 1)` is correct, and the pure-IPv6
guard before stripping is correct.
**Fix:** None required. Behavior is fail-safe.

_Reviewed: 2026-06-04_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
