# Domain Pitfalls: ShopPyBot v4.0 Win-the-Drop (Checkout Automation + Reliability)

**Domain:** Async nodriver/asyncio checkout bot adding verified-checkout, idempotent retry,
encrypted session persistence, per-coroutine supervision, and unified backoff to an existing
modular core (BotService + CredentialStore + plugin ABC).
**Researched:** 2026-06-10
**Supersedes:** v3.0 PITFALLS.md for v4.0 scope only; v3.0 pitfalls (proxy, CAPTCHA,
fingerprint, price monitoring) remain in force and are not repeated here.
**Overall Confidence:** HIGH for acquisition correctness, PCI handling, and asyncio
interaction patterns (directly traceable to existing code). MEDIUM for nodriver browser
relaunch specifics (nodriver public API surface is small; patterns inferred from CDPlib
behavior and Phase 13 ship experience).

---

## Critical Pitfalls

### Pitfall 1: Double-Buy via Non-Idempotent Checkout Retry

**What goes wrong:**
`auto_buy` returns `False` on any exception in its outer `try/except`. If the exception
fires after `place_order.click()` but before `return True`, the orchestrator (seeing
`False`) treats the attempt as failed. On the next poll cycle `purchased` is still `False`
in the DB, so `_check_and_buy` re-enters `auto_buy` and submits a second order. For
limited-release items at $400-$700+ this is a serious financial error, not a UI glitch.

**Why it happens:**
The current `auto_buy` contract is `bool` with no idempotency guard. The site may have
already charged and shipped order 1 by the time order 2 is attempted. The write-queue
drain path (`_dispatch_write`) is the only place `update_item_purchased_sync` is called,
and it only fires when `auto_buy` returns `True`.

**How to avoid:**
1. After `place_order.click()`, wait for and check the order confirmation page BEFORE
   returning `True`. Return `True` only when a confirmed order number or "Thank you" page
   element is detected (see Pitfall 2).
2. Introduce an `in_progress` state column in the `items` table (or a transient in-memory
   set on the plugin instance). Set it before `place_order.click()`; clear it on confirmed
   success or explicit failure. The next poll cycle skips items in `in_progress` state even
   if `purchased` is still `False`.
3. Gate the retry-on-cart logic (Pitfall 5) on whether the confirmation page was already
   seen this session — never retry a click that already advanced past cart.
4. In the checkout time-budget cancellation path (Pitfall 5), set `in_progress=False` AND
   query the order history API or confirmation page BEFORE concluding the order failed.

**Warning signs:**
- `"Order placed"` log line appears twice for the same URL in the same run.
- Two confirmation emails arrive for the same item.
- `purchased` DB flag is `False` after an `"Order placed"` log (write queue fell behind or
  the drain task was cancelled mid-flight).

**Phase to address:** Acquisition Core — verified-checkout + bounded retry phase.

---

### Pitfall 2: False-Positive Order Confirmation Detection

**What goes wrong:**
`auto_buy` in `shopbot_plugin_bestbuy.py` (line 310) logs `"Order placed on BestBuy"` and
returns `True` immediately after `place_order.click()` with no page-state verification.
The button may have been clicked on a stale/expired session page that re-rendered as an
error; the bot marks the item purchased, the notification fires, and the human discovers
no order exists.

Conversely, the Amazon plugin (lines 412-416) checks `test_mode` but skips confirmation
scraping in live mode: it clicks `#submitOrderButtonId` and returns `True` without reading
the resulting page. If Amazon's checkout redirects to a re-auth step, CVV challenge, or
out-of-stock page instead of a thank-you page, `True` is returned for a non-order.

**Why it happens:**
Click-and-assume is the pattern inherited from the v1 Selenium bot. It worked when a human
was watching. In unattended drop mode it is silently wrong.

**How to avoid:**
1. After `place_order.click()`, `await tab.get(...)` is not needed: nodriver stays on the
   current tab after a click. Instead, use `tab.find()` or `tab.select()` to detect the
   confirmation element within a bounded timeout (e.g., 30s).
2. For BestBuy: detect `".thank-you-enhancement__order-number"` or an element matching
   `/order[- ]*\d{7,}/i` (regex on `tab.text`).
3. For Amazon: detect `"#widget-purchaseConfirmationStatus"` or `"#orderConfirmations"`.
4. Treat any timeout or absence of the confirmation element as a definitive `False` return;
   log the page title and body excerpt (first 200 chars, never logging credential fields)
   for post-mortem.
5. Add a `_confirm_order` helper that is separately unit-testable with mock tab responses.

**Warning signs:**
- Notification fires but no order in retailer account order history.
- `purchased=True` in DB but email inbox has no confirmation from the retailer.
- `tab.text` after the click contains "sign in", "session expired", or "out of stock".

**Phase to address:** Acquisition Core — order-confirmation capture phase.

---

### Pitfall 3: Fragile Site-Specific Selectors That Silently Break

**What goes wrong:**
CSS selectors like `".a-dropdown-prompt"` in `shopbot_plugin_bestbuy.py` (line 272) are
copy-pasted from the legacy Selenium bot and carry a comment noting they look like Amazon
selectors. When BestBuy updates their DOM, `tab.select()` returns `None`, the `if
qty_dropdown:` guard is silently skipped, and the bot proceeds to checkout with the wrong
quantity (or crashes at a later step). There is no observable difference in logs between
"selector found, quantity set correctly" and "selector not found, skipping".

The broader risk: all 7 plugins use their own selector sets with no shared testing
harness. A single BestBuy redesign silently breaks the BestBuy plugin without alerting
the Amazon or Target plugin operators.

**How to avoid:**
1. For each required selector (add-to-cart, CVV input, place-order, confirmation element),
   log a WARNING when `select()` returns `None` rather than silently continuing. The warning
   should include the selector string: `f"Selector {selector!r} not found on {url}"`.
2. Gate place-order on CVV entry success: if `cvv_field` is `None` and `self._cvv` is set,
   return `False` with a logged WARNING rather than proceeding without CVV.
3. Treat `place_order = None` as an unrecoverable checkout failure; return `False`
   immediately (current code already does this but the log says only "Place order button
   not found" without the selector name -- add it).
4. Define a `SELECTORS` dict at module top level so the roadmapper can see all selectors in
   one place and the test fixture can patch them. Avoids selector strings scattered through
   multi-hundred-line `auto_buy` methods.
5. In tests, add a "stale selector" test case: mock tab that returns `None` for all
   selectors and assert `auto_buy` returns `False` with a WARNING in the log.

**Warning signs:**
- `auto_buy` completes without hitting the CVV step (no `"send_keys"` log on CVV field).
- "Checkout button not found" or "Place order button not found" in logs for items that are
  genuinely available and in cart.
- A DOM audit diff (periodically `GET` the page outside of bot context and diff selector
  presence) shows selectors have disappeared.

**Phase to address:** Acquisition Core — checkout form-fill phase; add a "selector
health-check" step to the checkout plan.

---

### Pitfall 4: Payment Data Handling / PCI Scope

**What goes wrong:**
Three failure modes exist for the CVV-at-runtime pattern:

(a) **CVV written to a log**: the existing `auto_buy` in `shopbot_plugin_bestbuy.py`
    calls `writeLog(f"Error during BestBuy auto-buy: {exc.__class__.__name__}", "ERROR")`
    which is correctly redacted. But if a future checkout phase adds per-step debug logging
    like `writeLog(f"Sending keys to CVV field: {self._cvv}", "DEBUG")` the CVV lands in
    `logs/YYYYMONTHDD.log` in plaintext. Log files are not covered by CredentialStore
    encryption.

(b) **Full card number stored for convenience**: the checkout profile will contain billing
    address + name. It is tempting to also store the card number and expiration in the
    same CredentialStore record. Never do this. The BestBuy/Amazon flow uses retailer-saved
    payment methods (the CVV is the only runtime secret). Storing the full PAN moves the
    user into PCI DSS scope even for personal use, and creates a high-value target in
    `creds.bin` or OS keyring.

(c) **CVV in a retry loop that logs attempts**: if bounded retry-on-cart (Pitfall 5)
    passes `self._cvv` through each retry iteration, any exception handler that logs
    `str(exc)` risks capturing the CVV if it appears in a stack frame. Use
    `exc.__class__.__name__` only (existing policy per STATE.md Research Flags / PITFALLS 6.4).

**How to avoid:**
1. CVV remains `getpass`-only at startup; `self._cvv` is the only in-memory location.
   Never add `CVV` to `SECRET_KEYS` or store it in `CredentialStore`.
2. Never log `self._cvv`, never log `str(exc)` on checkout paths (use
   `exc.__class__.__name__` per existing policy).
3. Billing/shipping checkout profile fields are NOT payment card data. Store them in
   CredentialStore under keys like `BB_SHIPPING_NAME`, `BB_SHIPPING_ADDRESS`, etc. They are
   not PCI-sensitive and do not require the same treatment as CVV.
4. Do not store card number, expiration, or full card holder data in CredentialStore.
   The flow must rely on retailer-saved payment method + CVV-at-runtime only.
5. Add a CI grep assertion (similar to existing SC1 `os.environ` guard) that rejects any
   `writeLog` call with `_cvv` in the arguments on checkout code paths.

**Warning signs:**
- `logs/` files contain strings matching `/\d{3,4}/` adjacent to "cvv" or "card".
- `CredentialStore` key list contains `CVV`, `CARD_NUMBER`, or `PAN`.
- Debug log verbosity increased to level 5 during testing and a CVV value appears in
  the log file.

**Phase to address:** Acquisition Core — checkout profile + form-fill phase; add SC grep
check to that phase's test plan.

---

### Pitfall 5: Time-Budget Cancellation Leaving a Half-Submitted Order

**What goes wrong:**
`asyncio.timeout()` or `asyncio.wait_for()` wrapping the entire `auto_buy` coroutine will
raise `asyncio.TimeoutError` (or `asyncio.CancelledError` when a `TaskGroup` task is
cancelled) at any `await` point inside the method -- including inside nodriver's own
`tab.send()` calls. If the coroutine is cancelled after `place_order.click()` but before
the confirmation check completes, the browser tab is left on the checkout page in a
partially submitted state. The Chrome subprocess continues running; the next call to
`self.driver.main_tab` may be operating on a stale post-click page state.

The converse risk: if the timeout fires BEFORE `place_order.click()`, the cart may hold the
reserved item, blocking other purchasers and triggering a cart-expiry at the retailer that
makes the item temporarily unavailable to the bot on the next poll.

**Why it happens:**
Per-item orchestrator timeouts (a v4.0 requirement) are straightforward for
`check_availability` (stateless per-poll). Applying the same pattern to `auto_buy` (which
is stateful and has side effects at the retailer) requires explicit checkpointing.

**How to avoid:**
1. Do not wrap the entire `auto_buy` call in a single `asyncio.timeout`. Instead, apply
   timeout budgets per-step: navigate (10s), add-to-cart (15s), checkout-proceed (15s),
   CVV entry (10s), place-order click (10s), confirmation wait (30s). Use
   `asyncio.timeout(N)` as a context manager around each `await` separately.
2. Track checkout progress via a local state variable inside `auto_buy`:
   `stage = "cart" | "cvv" | "placed" | "confirmed"`. On `CancelledError`, catch it
   in a finally block, log the stage, then re-raise. The orchestrator logs the stage to
   assist post-mortem.
3. After catching `CancelledError` at stage `"placed"` or later, set `in_progress=True`
   in the DB rather than leaving `purchased=False` so the next poll cycle does not
   immediately re-submit.
4. For browser orphan prevention: `teardown()` already calls `self.driver.stop()` in the
   `finally` of `async_main`. Per-item timeout should NOT call `teardown()`; only the
   top-level shutdown path should. A per-item timeout should cancel the task and let
   `async_main`'s `finally` handle browser cleanup.

**Warning signs:**
- Browser process consumes CPU after a timeout event (still rendering checkout page).
- Two orders in retailer account from the same drop session.
- `purchased=False` in DB after the "Order placed" log appeared (drain task cancelled
  while the write was in flight).

**Phase to address:** Acquisition Core — per-item/per-step checkout time budget phase.

---

### Pitfall 6: Monitor-Only Gate That Fails to Block Place-Order in All 7 Plugins

**What goes wrong:**
The Amazon plugin implements `test_mode` correctly (lines 391-428): it pauses before and
after the buy-now click, and explicitly skips `place_order.click()`. The BestBuy plugin
has NO `test_mode` guard at all -- `place_order.click()` fires unconditionally when the
button is found (lines 303-309). The 5 other plugins (Walmart, Target, GameStop,
SquareEnix, Newegg) were built before checkout was real and have no place-order path yet,
but they will need the gate when checkout is added in v4.0.

A central `monitor_only` mode (v4.0 requirement) that is not threaded through the plugin
ABC and tested per-plugin will have the same gap. If even one plugin bypasses the gate,
the monitor-only mode cannot be trusted for demo or test environments.

**Why it happens:**
`test_mode` is read from `self.config.debug.test_mode` inside the plugin, which requires
the plugin to actively check it. There is no architectural enforcement from the base class.

**How to avoid:**
1. Add `monitor_only: bool` to `AppConfig.debug` (or as a top-level field). Read it once
   in `orchestrator.async_main` and pass it to `run_plugin` as a flag.
2. In `run_plugin`, gate the `await _try_auto_buy(...)` call with `if not monitor_only`.
   This prevents `auto_buy` from being called at all when monitor-only mode is active,
   regardless of plugin implementation. This is the single enforcement point.
3. Separately, fix the BestBuy `test_mode` gap: add the same `if not test_mode: ...
   place_order.click()` pattern from Amazon to BestBuy. Test it with the existing
   `test_pause_event` pattern.
4. For new checkout implementations in other plugins, the ABC should document that
   `auto_buy` MUST respect `self.config.debug.test_mode`; but the orchestrator-level gate
   in step 2 is the authoritative guard.
5. Add a CI test: mock all 7 plugins, set `monitor_only=True`, assert `auto_buy` is never
   called (by asserting zero calls to `write_queue.put` with tag `"purchased"`).

**Warning signs:**
- BestBuy `auto_buy` places a real order during a "monitor-only" session.
- Any plugin's `auto_buy` is called when `monitor_only=True` is set in config.
- The `_try_auto_buy` orchestrator function shows up in call traces during monitor-only
  runs (add a log line to `_try_auto_buy` that is easy to grep).

**Phase to address:** Acquisition Core — central monitor-only run mode + close test_mode
place-order hole phase.

---

### Pitfall 7: Per-Coroutine Restart Crash-Loops With No Backoff

**What goes wrong:**
The current `run_plugin` coroutine (orchestrator.py line 168) runs inside
`asyncio.TaskGroup`. If the plugin raises an unhandled exception, `TaskGroup` cancels all
sibling tasks and the entire bot exits. The v4.0 per-coroutine supervision requirement
inverts this: individual plugin coroutines should restart independently rather than taking
down the whole group.

The naive fix -- wrapping `run_plugin` in a `while True: try/except` restart loop -- will
crash-loop at maximum speed if the plugin has a persistent error (e.g., login fails every
time because `BB_PASSWORD` was rotated). 100+ browser launches per minute will trigger
an OS-level Chrome process limit, exhaust disk space with crash dumps, and get the
bot's IP banned in seconds.

**How to avoid:**
1. Implement exponential backoff with jitter for the per-plugin restart supervisor:
   `delay = min(base * 2**attempts, max_delay) + random.uniform(0, 1)`.
   Recommended values: `base=5s`, `max_delay=300s`. Reset `attempts=0` on a successful
   poll cycle (defined as `check_availability` returning without exception).
2. Add a `max_restarts` cap per plugin per run (e.g., 10). After hitting the cap, log
   CRITICAL and stop restarting that plugin without killing siblings.
3. Distinguish retryable errors (network timeout, nodriver `ConnectionError`) from
   non-retryable errors (login credential failure, `RuntimeError: proxy pool exhausted`).
   Non-retryable errors should go straight to the `max_restarts` cap without any delay.
4. The supervisor should live outside `asyncio.TaskGroup` or use a shielded
   `asyncio.create_task` per plugin so that one plugin's restart loop cannot propagate
   `ExceptionGroup` cancellation to sibling plugins.

**Warning signs:**
- Log shows the same plugin "setup failed: ..." message repeating with no delay.
- Chrome process count in `ps`/Task Manager grows without bound.
- Bot exits entirely when one plugin fails (current behavior -- not the v4.0 target).

**Phase to address:** Always-On Reliability — per-coroutine supervision + backoff restart.

---

### Pitfall 8: Browser Relaunch That Forgets Stealth, Proxy, and Login

**What goes wrong:**
`_staggered_setup` (orchestrator.py lines 284-308) applies `assign_proxy`, `assign_solver`,
and `plugin.setup()` (which calls `apply_stealth` and `setup_proxy_auth`) in one pass at
bot startup. A v4.0 browser-crash detection + relaunch path that calls only
`plugin.setup()` will relaunch Chrome but will NOT re-apply stealth patches or
authenticated proxy handlers, and will NOT re-log in. The browser comes up clean, hits
the target site without stealth or proxy, gets banned immediately, and the crash-detection
fires again -- producing a ban-loop.

**Why it happens:**
`setup()` in both plugins (`shopbot_plugin_bestbuy.py` line 158, `shopbot_plugin_amazon.py`
line 193) does correctly call `apply_stealth` and `setup_proxy_auth`. The danger is in
the relaunch caller forgetting to also call `plugin.login()` after `setup()`. Login state
is not persisted across browser restarts in the current design (no session/cookie
persistence until Pitfall 9 is addressed).

**How to avoid:**
1. Define a `_cold_start(plugin, registry)` helper that encapsulates the full relaunch
   sequence: `registry.assign_proxy(plugin)` + `registry.assign_solver(plugin)` +
   `await plugin.setup()` + `await plugin.login()`. This is the single path both
   `_staggered_setup` and the crash-recovery code use.
2. After session/cookie persistence is implemented (Pitfall 9), the relaunch path should
   also call `session_store.restore(plugin)` before `plugin.login()` so that a valid
   session avoids re-triggering the passkey/OTP flow.
3. Add a `stealth_applied: bool` flag to the plugin base class (or check via CDP
   `Page.getScriptExecutionStatus`) as a post-relaunch assertion before the first
   navigation.
4. Test: mock `nodriver.start` to raise `OSError` on first call (simulating a crash), then
   succeed on second call. Assert that `apply_stealth` and `setup_proxy_auth` are called
   on both the first and second startup.

**Warning signs:**
- After a relaunch, the bot hits the site and immediately returns a ban-page response
  (`_handle_ban` returns `True` on the first request).
- `apply_stealth` log line (`"[STAGGER-N] Initializing ..."`) appears once at startup but
  not after a crash recovery.
- Proxy provider dashboard shows direct-IP traffic appearing after the relaunch interval.

**Phase to address:** Always-On Reliability — browser-crash detection + relaunch.

---

### Pitfall 9: Session/Cookie Persistence Leaking Auth Material to Plaintext

**What goes wrong:**
nodriver's `Browser` object accumulates cookies (including session tokens, CSRF tokens,
and auth cookies) in the browser process state. Persisting these across restarts requires
serializing them via CDP `Network.getAllCookies` and writing the result to disk. If written
as a plain JSON file alongside `config.yml` or in `data/`, this is plaintext auth material
on disk -- the exact security posture that the v2.0 `CredentialStore` was built to prevent
(STATE.md Key Decisions: "No secrets in SQLite", "Dynamic CredentialStore").

**Why it happens:**
Session persistence is not currently implemented. The temptation on implementation is to
use `json.dump(cookies, open("sessions/bestbuy.json", "w"))` because it is five lines and
appears to be "just browser state, not a password."

**How to avoid:**
1. Route session/cookie persistence through the existing `EncryptedFileBackend` or a
   new `SessionStore` wrapper that uses the same Fernet + scrypt approach from
   `core/credentials.py`. The key for the session store should come from the same
   `SHOPBOT_STORE_PASSPHRASE` or OS keyring path.
2. Never write raw CDP cookie dicts to a plain file. The serialized value for each plugin
   should be stored under a key like `BB_SESSION_COOKIES` (add to `SECRET_KEYS` list).
3. On restore, verify cookie freshness: check `expires` timestamps and discard expired
   cookies before injection. A stale session token is worse than none (it causes a
   "session expired" redirect that the selector-based login flow does not handle cleanly).
4. Session store write must use the same atomic write pattern (`mkstemp` + `os.replace`)
   that `EncryptedFileBackend._save` uses to prevent partial writes on crash.

**Warning signs:**
- A `.json` or `.pickle` file appears in `data/` or `sessions/` containing the string
  `"session-token"` or `"cookie"`.
- `git status` shows an untracked `sessions/` directory with readable content.
- `CredentialStore.list()` does not include session-cookie keys, but session files exist.

**Phase to address:** Always-On Reliability — encrypted session/cookie persistence.

---

### Pitfall 10: Per-Item asyncio Timeout That Cancels Mid-DB-Write or Mid-Checkout

**What goes wrong:**
`asyncio.CancelledError` propagates through every `await` without warning. The
write-queue drain task (`_write_queue_drain`, orchestrator.py line 271) awaits
`_dispatch_write`, which calls `loop.run_in_executor(None, update_item_purchased_sync)`.
If the per-item orchestrator timeout fires while the executor thread is running the SQLite
write, the `CancelledError` cancels the `await` in the drain coroutine but the executor
thread continues to completion in the background. The `queue.task_done()` in the `finally`
block fires normally. In this case, the write actually completes, but the drain task's
exception handler may log a spurious error.

The more serious case: if the per-item timeout is applied to `_check_and_buy` directly
(not via the write queue), the `await write_queue.put(...)` calls inside
`_check_and_buy` may be cancelled before the item is enqueued, leaving the DB in an
inconsistent state (`set_available` fired but `clear_available` never will, or `purchased`
was not marked despite a confirmed order).

**How to avoid:**
1. Never cancel the write-queue drain task (`_write_queue_drain`) via per-item timeout.
   The drain task must run to natural completion on shutdown only (current `finally:
   await asyncio.wait_for(write_queue.join(), timeout=10)` is correct; preserve it).
2. Apply per-item timeouts only to the `check_availability` + `auto_buy` portion of
   `_check_and_buy`, not to the `write_queue.put(...)` calls that follow them. Structure:
   ```python
   try:
       async with asyncio.timeout(item_timeout):
           available = await plugin.check_availability(link)
           # ...auto_buy path...
   except asyncio.TimeoutError:
       writeLog(f"[{plugin.__class__.__name__}] Item timeout for {link}", "WARNING")
       return
   # write_queue.put calls are OUTSIDE the timeout context
   await write_queue.put(("set_available", link, now_iso))
   ```
3. On `CancelledError` (from TaskGroup shutdown, not per-item timeout), do NOT suppress
   it. Let it propagate after logging the item URL and current stage.

**Warning signs:**
- `"DB write failed for ..."` log followed by the item not being marked `purchased`
  despite an order confirmation log in the same run.
- `asyncio.InvalidStateError` or `queue.task_done()` called too many times (indicates the
  drain task was cancelled mid-loop).
- Items that were set available are never cleared on the next poll (missed
  `clear_available` because the put was cancelled).

**Phase to address:** Always-On Reliability — per-item orchestrator timeout.

---

### Pitfall 11: DB Error Isolation That Silently Swallows Real Corruption

**What goes wrong:**
The `_dispatch_write` function (orchestrator.py line 240) wraps the entire write in
`try/except Exception` and logs the error, then continues. This is correct for transient
SQLite locks (`OperationalError: database is locked`). But `sqlite3.DatabaseError` and
`sqlite3.CorruptionError` indicate actual file corruption -- continuing silently means
subsequent reads return garbage data, availability state diverges from reality, and the
bot may never buy anything (or buy things it already owns) for the rest of the session.

**Why it happens:**
A blanket `except Exception` at the write-queue drain level is the right shape for
transient errors, but it makes no distinction between transient and fatal.

**How to avoid:**
1. Distinguish exception types at the write-queue drain level:
   - `sqlite3.OperationalError` with message containing "locked": log WARNING, do NOT
     re-raise; the write will succeed on retry.
   - `sqlite3.DatabaseError` / `sqlite3.CorruptionError`: log CRITICAL, raise the
     exception (which will propagate out of the drain task and cancel the TaskGroup,
     triggering a clean shutdown with the existing `teardown_all` path).
2. For read-path errors in `run_plugin` (the `get_items_sync` call), wrap in
   `try/except sqlite3.OperationalError` only. A true `DatabaseError` on a read should
   immediately stop the poll loop with a CRITICAL log rather than looping forever on
   a corrupted `items` table.
3. Add a startup DB integrity check: call `PRAGMA integrity_check` on startup in
   `initialize_db` and raise `RuntimeError` if it returns anything other than `"ok"`.
   This catches corruption before any writes attempt to proceed.

**Warning signs:**
- `"DB write failed for ..."` log appearing every poll cycle for the same item URL
  (write never succeeds -- permanent failure being retried endlessly).
- SQLite file size grows to 0 bytes or becomes non-parseable (file deleted mid-write
  without atomic replace -- should not happen with the existing `os.replace` pattern, but
  watch for it if session store is added without the same atomic-write guard).
- `get_items_sync` returns an empty list when items are known to exist.

**Phase to address:** Always-On Reliability — DB read-path error isolation phase.

---

### Pitfall 12: Two Divergent Retry Implementations (Orchestrator Transient-Retry vs Checkout Retry-on-Cart)

**What goes wrong:**
v4.0 adds two distinct retry concepts:
- **Orchestrator transient retry**: retry a failed `check_availability` or `auto_buy` call
  due to network error or nodriver connection reset (per-coroutine supervision in Pitfall 7).
- **Checkout retry-on-cart**: if `auto_buy` fails at the "add to cart" step (item went
  out of stock in the window between `check_availability` and `auto_buy`), wait briefly
  and re-attempt the cart add up to N times.

If these are implemented independently (one in `run_plugin`, one inside `auto_buy`), they
will have different backoff parameters, different logging, different exception handling,
and different interaction with the `in_progress` state (Pitfall 1). When both fire
simultaneously (a cart error during an already-retrying plugin), the bot may attempt
`max_supervisor_retries * max_cart_retries` orders -- multiplicative, not additive.

**How to avoid:**
1. Define a single `RetryPolicy` dataclass in `core/retry.py`:
   ```python
   @dataclass
   class RetryPolicy:
       max_attempts: int
       base_delay: float
       max_delay: float
       jitter: bool = True
       retryable_exceptions: tuple = (Exception,)
   ```
2. Implement one `async def with_retry(coro_fn, policy: RetryPolicy)` utility that both
   the supervisor restart path and the checkout cart-retry path use.
3. The supervisor retry (Pitfall 7) uses `RetryPolicy(max_attempts=10, base_delay=5,
   max_delay=300)`.
4. The checkout cart-retry uses `RetryPolicy(max_attempts=3, base_delay=2, max_delay=10)`
   and is scoped only to the "add to cart" step -- never to `place_order.click()` or later
   (per Pitfall 1).
5. The two policies are configured independently in `AppConfig` so operators can tune them
   without touching code.

**Warning signs:**
- `auto_buy` has its own `for attempt in range(N)` loop AND the supervisor also has a
  restart loop -- both are independently retrying with no shared state.
- Log shows "attempt 1/3" interleaved with "restarting plugin" messages making the
  actual retry count ambiguous.
- Cart retry fires after a confirmed-order step (retry should be gated to pre-CVV stages).

**Phase to address:** Always-On Reliability — one unified transient retry/backoff phase;
must be built before checkout retry is added to any plugin.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `return True` after `place_order.click()` without confirmation check | Simple, works when site is healthy | Double-buy on session edge cases; false purchase notifications | Never; confirmation check is required for v4.0 |
| Single `asyncio.timeout` around entire `auto_buy` | Easy to implement | Orphans browser state mid-checkout; CancelledError at click fires double-buy risk | Never for place-order step; per-step timeouts only |
| Blanket `except Exception` in write-queue drain | Prevents drain task crash | Swallows DB corruption silently | Only for `OperationalError` "locked"; fatal errors must propagate |
| Storing session cookies as plain JSON | 5-line implementation | Plaintext auth material on disk; violates v2.0 security posture | Never; must use CredentialStore-equivalent encryption |
| One global `test_mode` check inside Amazon plugin only | Works for Amazon UAT | Other plugins (BestBuy) have no gate; monitor-only mode cannot be trusted | Never; orchestrator-level gate required for all plugins |
| Inline backoff in `run_plugin` | Avoids a new module | Two backoff implementations diverge silently over time | Never; single `RetryPolicy` utility required |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| nodriver `tab.select()` on post-click page | Calling `select()` on a stale tab reference after a click navigates the page | After `click()` on a submit/place-order button, use `await asyncio.sleep(0)` + `tab.find()` or wait for the confirmation element on the same tab object -- nodriver updates `main_tab` in place after navigation |
| nodriver `Browser.stop()` in a crash-recovery path | Calling `stop()` and immediately calling `nodriver.start()` in the same event loop tick | `stop()` is synchronous but Chrome process termination is async at the OS level; add a brief `await asyncio.sleep(1)` or poll `psutil` for process exit before relaunching |
| CredentialStore `get()` during checkout | Calling `get_store().get("BB_PASSWORD")` inside the hot checkout path | Call `get_store().get(...)` once in `login()` and cache the value for the session; `EncryptedFileBackend.get()` decrypts the entire file on every call (O(keys) decrypt per access) |
| CDP `Network.getAllCookies` for session persistence | Serializing and storing the full CDP cookie dict including `httpOnly` session tokens | Only persist cookies that are not `httpOnly` and not marked `secure`-only; or accept that restoration requires post-inject verification via `tab.evaluate("document.cookie")` |
| `asyncio.timeout()` wrapping nodriver `tab.send()` | The timeout cancels the Python `await` but not the underlying CDP message handler; nodriver may still process the response | After a timeout in a nodriver `tab.send()` call, treat the tab state as unknown; do not re-use the tab for further checkout steps without a fresh page navigation |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| `writeLog(f"CVV: {self._cvv}", "DEBUG")` on any code path | CVV in plaintext log files, unencrypted | SC grep CI assertion blocking `_cvv` in any `writeLog` argument |
| Storing full card number in `CredentialStore` for "convenience" | PCI DSS scope for personal tool; high-value target in `creds.bin` | Only CVV at runtime; billing address is fine in store; full PAN never |
| `str(exc)` in exception handlers on checkout paths | Stack trace may contain CVV if it appeared in a method argument | `exc.__class__.__name__` only (existing policy per STATE.md PITFALLS 6.4) |
| Session cookie file in repo directory without `.gitignore` entry | Auth cookies committed to git history | `sessions/` and `data/*.bin` must be in `.gitignore`; CI check for these patterns |
| `monitor_only` flag readable from config.yml (not enforced in code) | User edits config, flag change not picked up mid-run | Read flag once at startup into `async_main` local; changes require restart |
| Checkout profile (shipping address) logged at INFO level | Address in log files; low risk but unnecessary | Log only "checkout profile loaded for {platform}" not the address values |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| `EncryptedFileBackend.get()` called per-checkout-step | Decrypt latency adds 50-100ms per call; noticeable on drops with sub-second windows | Cache credentials in plugin `__init__` or `setup()`, not in hot path | Any drop where checkout must complete in under 5s |
| `get_items_sync` called once per poll inside `run_plugin` (current) | On a 30-item list this is fine; on 200 items with 7 plugins it is 1400 DB reads/minute | Add item-URL-to-plugin routing cache in orchestrator; only re-fetch when DB write occurs | More than ~50 items across all plugins |
| nodriver `tab.select()` with `timeout=10` called sequentially for every selector | Each miss waits 10s; a 5-selector checkout path can take 50s on a broken DOM | Short timeout (2-3s) for optional elements; long timeout (10-15s) for required ones | Any drop where checkout window is under 60s |
| Single write-queue drain for all plugins | Current design serializes all DB writes; 7 plugins checking simultaneously causes write queue backlog during drops | Acceptable for v4.0 scope (SQLite single-writer); monitor queue depth; escalate to WAL mode if backlog exceeds 100 items | More than ~20 simultaneous availability detections |

---

## "Looks Done But Isn't" Checklist

- [ ] **Order confirmation:** `auto_buy` returns `True` but confirmation element was NOT verified -- check that `_confirm_order` is called and its return value gates the `True` return.
- [ ] **BestBuy test_mode gate:** `test_mode: true` in config -- verify `place_order.click()` is NOT called by asserting no "Order placed on BestBuy" log and no `write_queue.put("purchased", ...)` event.
- [ ] **Monitor-only mode:** all 7 plugins have `auto_buy` enabled in config, `monitor_only: true` is set -- assert zero `auto_buy` calls and zero `purchased` write-queue entries.
- [ ] **CVV in logs:** after a full checkout run with debug logging at level 5, grep log file for the CVV value -- must return zero matches.
- [ ] **Relaunch stealth:** after a simulated browser crash and relaunch, assert `apply_stealth` was called on the new tab (check for the `cdp.page.add_script_to_evaluate_on_new_document` CDP command in the nodriver mock).
- [ ] **Double-buy guard:** simulate `place_order.click()` succeeding but confirmation timeout firing -- assert `purchased` is NOT set and `in_progress` IS set; assert the next poll skips the item.
- [ ] **Session cookie encryption:** session restoration path -- assert no plaintext `.json` file was written; assert `CredentialStore.set()` was called with the session key.
- [ ] **Retry policy unification:** grep for `for attempt` or `for i in range` in checkout paths -- any such loop outside `core/retry.py` is a second independent retry implementation.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Double-buy detected | HIGH | Check retailer order history immediately; cancel second order via retailer cancel page (usually cancellable within 30 min); mark item `purchased=True` in DB manually via `shoppybot items` CLI |
| False-positive purchased notification | MEDIUM | Set `purchased=False` in DB via CLI; re-enable monitoring; add confirmation selector to CI test to prevent recurrence |
| CVV in log file | HIGH | Rotate payment card CVV with bank immediately; delete log file; audit for other credential exposure; add SC grep CI check before next run |
| Browser crash loop (no backoff) | MEDIUM | Kill all Chrome processes (`pkill chrome` / Task Manager); restart bot; backoff implementation is the permanent fix |
| Session cookie plaintext on disk | HIGH | Delete session file; revoke session via retailer "sign out all devices"; migrate to encrypted session store; add `.gitignore` entry |
| DB corruption | HIGH | Stop bot; restore from last `data/shop_py_bot.db` backup (or delete and re-seed from config); add `PRAGMA integrity_check` to startup path |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Double-buy / non-idempotent retry | Acquisition Core: verified-checkout + bounded retry | Test: mock `place_order.click()` succeeds, confirmation times out; assert `purchased=False`, `in_progress=True` |
| 2. False-positive confirmation | Acquisition Core: order-confirmation capture | Test: mock tab returning "session expired" after click; assert `auto_buy` returns `False` |
| 3. Fragile checkout selectors | Acquisition Core: checkout form-fill | Test: "all selectors None" mock; assert `auto_buy` returns `False` with WARNING log |
| 4. CVV / PCI handling | Acquisition Core: checkout profile + form-fill | CI SC grep: no `_cvv` in `writeLog` args; no `CVV`/`CARD_NUMBER` in `SECRET_KEYS` |
| 5. Time-budget orphaned order | Acquisition Core: per-item/per-step checkout time budget | Test: timeout fires at each checkout stage; assert browser cleanup and correct DB state |
| 6. Monitor-only gate | Acquisition Core: central monitor-only + test_mode hole | Test: 7 plugins, `monitor_only=True`; assert `auto_buy` never called |
| 7. Restart crash-loop | Always-On Reliability: per-coroutine supervision + backoff | Test: plugin raises on 3 consecutive setups; assert delay between attempts follows exponential curve |
| 8. Relaunch forgetting stealth | Always-On Reliability: browser-crash detection + relaunch | Test: mock crash + relaunch; assert `apply_stealth` + `setup_proxy_auth` + `login` all called |
| 9. Session cookie plaintext | Always-On Reliability: encrypted session/cookie persistence | Test: session save path; assert no plaintext file written; assert `CredentialStore.set()` called |
| 10. Timeout cancels mid-DB-write | Always-On Reliability: per-item orchestrator timeout | Test: timeout fires after `place_order.click()` but before `write_queue.put`; assert write-queue item still enqueued |
| 11. DB corruption swallowed silently | Always-On Reliability: DB read-path error isolation | Test: mock `sqlite3.DatabaseError`; assert CRITICAL log and TaskGroup shutdown |
| 12. Two retry implementations | Always-On Reliability: unified transient retry/backoff | Grep CI assertion: no `for attempt` loop outside `core/retry.py`; both supervisor and cart-retry use `RetryPolicy` |

---

## ToS / Legal / Ethical Cautions

These apply to v4.0 specifically because v4.0 adds *actual purchase execution*, not just
monitoring.

**Financial Risk (not ToS):** Automated purchase of high-demand items at market price
carries real financial exposure. A double-buy (Pitfall 1) on a $700 GPU cannot be
"undone" once the item ships. This is the primary reason Pitfall 1 is Critical.

**Retailer Terms of Service:** Both BestBuy and Amazon prohibit automated purchasing in
their ToS. Checkout automation that bypasses CAPTCHA and fills CVV fields is explicitly
in-scope for these prohibitions. Consequences include account suspension, order
cancellation after fulfillment, and IP/device banning. The bot should document this
clearly in `SECURITY.md` and `README.md`. Open-source distribution does not reduce
personal liability for ToS violations.

**Scalefair / Per-Household Limits:** Retailers enforce per-household purchase limits on
limited-release items. Automated enforcement detection is improving. Purchasing multiple
units across the configured `quantity` field may trigger order cancellations. Recommend
defaulting `quantity=1` and documenting the risk of higher values.

**Payment Method Risk:** Using CVV-at-runtime with a stored payment method means that
anyone who gains access to the bot process (or the OS session) can trigger purchases.
Document this in `SECURITY.md`. Recommend using a dedicated card with a low credit limit
or a virtual card number for bot use.

**Open-Source Distribution Warning:** Publishing working checkout automation code creates
an attractive basis for bulk scalpers. `README.md` and `CONTRIBUTING.md` should include
a clear statement that mass-scalping, multi-account farming, and resale automation are
out-of-scope use cases and not supported. This is already partially addressed by the
project's deferred items (multi-account, API-mode checkout), but should be an explicit
statement, not just an absence.

**Jurisdiction:** In most jurisdictions, personal use automation is not illegal per se,
but using it to acquire goods for resale may implicate consumer protection, anti-scalping,
or unfair competition statutes (California AB 2929 for tickets; analogous laws are being
considered for electronics in several US states). This is a follow-on risk, not a v4.0
blocker, but the maintainer should be aware.

---

## Sources

- Code reading: `core/orchestrator.py`, `core/credentials.py`, `core/stealth.py`,
  `plugins/shopbot_plugin_bestbuy.py`, `plugins/shopbot_plugin_amazon.py`
- Project context: `.planning/PROJECT.md`, `.planning/STATE.md` Research Flags
- Existing pitfall decisions from STATE.md (log `exc.__class__.__name__` never `str(exc)`
  on credentialed paths -- PITFALLS 6.4; proxy pool exhausted fail-loud -- Pitfall 2;
  stealth before first navigation -- Pitfall 8)
- asyncio cancellation semantics: Python 3.11+ `asyncio.timeout()` documentation
- nodriver architecture: Phase 13 ship experience (CDP Fetch auth, stealth injection,
  `Browser.stop()` synchronous teardown)
- PCI DSS scope reference: PCI DSS v4.0 requirements 3.x (card data storage prohibition)

---
*Pitfalls research for: ShopPyBot v4.0 Win-the-Drop checkout automation + reliability*
*Researched: 2026-06-10*
