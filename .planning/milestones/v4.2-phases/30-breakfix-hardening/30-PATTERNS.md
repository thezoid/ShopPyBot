# Phase 30: Breakfix Hardening - Pattern Map

**Mapped:** 2026-07-02
**Files analyzed:** 12 (2 core modified, 7 plugins modified, 1 DB module modified, 2 exceptions/helpers net-new-but-inline)
**Analogs found:** 12 / 12

**Codebase note:** `.planning/codebase/*.md` maps are STALE (pre-v2.0 monolith) and were NOT used. All analogs below are read directly from the current v4.1 modular `core/` + `plugins/` layout.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `models.py` (+2 accessors, +1 column) | model | CRUD | `models.py:133-158` (`get_item_order_state_sync`/`update_item_confirmed_sync`, same file) | exact |
| `core/orchestrator.py` (`_PossiblyPlaced` + `_pre_attempt_check` extension + `_try_auto_buy` except clause + alert) | controller/orchestrator | event-driven | `core/orchestrator.py:376-423` (`_AlreadyConfirmed` + `_pre_attempt_check`, same file) | exact |
| `plugins/shopbot_plugin_amazon.py` (`auto_buy` marker write; `_solve_or_pause` WAF branch; `login()` -> bool) | plugin/controller | request-response | itself (existing `increment_checkout_attempts_sync` direct-write precedent is in orchestrator, not plugin -- first plugin->models edge) + `solve_recaptcha` branch in same file | exact (WAF, login) / role-match (marker write, new dependency edge) |
| `plugins/shopbot_plugin_bestbuy.py` (place-order marker write; `login()` -> bool) | plugin/controller | request-response | `plugins/shopbot_plugin_amazon.py` (byte-for-byte identical place-order timeout shape) | exact |
| `plugins/shopbot_plugin_{walmart,target,gamestop,newegg,squareenix}.py` (`login()` -> bool via generic signal) | plugin/controller | request-response | `plugins/shopbot_plugin_walmart.py:118-146` (representative community-plugin `login()`) | exact |
| `core/plugin_base.py` (`login()` ABC -> bool; `_verify_login_generic` helper; `relaunch()` return-check) | model/ABC | request-response | itself (`place_order_guarded`, same file, additive-concrete-method precedent) | exact |
| `core/captcha.py` | service | request-response | UNCHANGED -- `solve_amazon_waf` already implemented (:169-204); zero edits needed | n/a (no change) |
| `core/confirmation.py` | service | transform | UNCHANGED -- read for the sentinel-is-not-idempotency-key invariant only | n/a (no change) |
| `core/retry.py` | utility | request-response | UNCHANGED -- reused as-is (D-05) | n/a (no change) |
| `notifications/dispatcher.py` / `notifications/base.py` | service | pub-sub | UNCHANGED -- reused as-is via `_build_event` + `dispatcher.notify()` | n/a (no change) |
| `tests/test_cart_retry.py`, `test_models.py`, `test_captcha_plugin.py`, `test_plugin_base.py`, `test_relaunch.py`, `test_plugin_{amazon,bestbuy,walmart,...}.py` | test | request-response | themselves (existing test bodies to extend/rewrite) | exact |

## Pattern Assignments

### `models.py` (model, CRUD) -- BF-02 marker column + accessors

**Analog:** `models.py` itself -- the idempotent ALTER-TABLE idiom (lines 48-80) and the `get_item_order_state_sync`/`update_item_confirmed_sync` accessor pair (lines 133-158).

**Idempotent column-add idiom to mirror** (`models.py:72-80`):
```python
        # Phase 19: confirmation columns (BUY-03, BUY-04).
        if "order_id" not in existing:
            conn.execute("ALTER TABLE items ADD COLUMN order_id TEXT")
        if "confirmed_at" not in existing:
            conn.execute("ALTER TABLE items ADD COLUMN confirmed_at TEXT")
        if "checkout_attempts" not in existing:
            conn.execute(
                "ALTER TABLE items ADD COLUMN checkout_attempts INTEGER NOT NULL DEFAULT 0"
            )
```
New BF-02 block follows immediately after (same `existing` set already built at line 49-52): add
```python
        if "place_order_attempted_at" not in existing:
            conn.execute("ALTER TABLE items ADD COLUMN place_order_attempted_at TEXT")
```

**`_sync` read accessor to mirror** (`models.py:133-145`, `get_item_order_state_sync`):
```python
def get_item_order_state_sync(link: str) -> tuple[bool, str | None]:
    """Return (purchased as bool, order_id) for the cart-retry idempotency check (BUY-05).

    Returns (False, None) when the item row is missing (safe no-op for retry guard).
    """
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT purchased, order_id FROM items WHERE link=?",
            (link,),
        ).fetchone()
    if row is None:
        return False, None
    return bool(row[0]), row[1]
```
New `get_place_order_marker_sync(link) -> str | None` mirrors this shape (single-column SELECT, `row is None` guard, return `row[0]`).

**`_sync` write accessor to mirror** (`models.py:148-158`, `update_item_confirmed_sync`):
```python
def update_item_confirmed_sync(link: str, order_id: str, confirmed_at: str) -> None:
    """Set purchased=1, order_id, and confirmed_at together (BUY-03/BUY-04).

    The order_id column is the idempotency anchor for Phase 21 retry (BUY-05).
    Does not touch checkout_attempts (increment is Phase 21 scope).
    """
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE items SET purchased=1, order_id=?, confirmed_at=? WHERE link=?",
            (order_id, confirmed_at, link),
        )
```
New `mark_place_order_attempted_sync(link, attempted_at) -> None` mirrors this shape (single UPDATE, parameterized, no return value). `get_db_connection()`'s WAL/`busy_timeout=5000`/`synchronous=NORMAL` context manager (lines 10-30) is reused unmodified -- do not add a new connection helper.

---

### `core/orchestrator.py` (orchestrator, event-driven) -- BF-02 `_PossiblyPlaced` guard

**Analog:** same file -- `_AlreadyConfirmed` (lines 376-380) + `_pre_attempt_check` (lines 400-423) + `_try_auto_buy`'s `except _AlreadyConfirmed:` clause (lines 437-446).

**Exception sentinel to mirror** (`core/orchestrator.py:376-380`):
```python
class _AlreadyConfirmed(Exception):
    """Sentinel: raised inside on_attempt to abort retry when order already confirmed."""
    def __init__(self, order_id: str) -> None:
        self.order_id = order_id
```
New `_PossiblyPlaced(Exception)` sibling, same shape, carries `attempted_at: str`.

**`_pre_attempt_check` extension point** (`core/orchestrator.py:400-423`, exact current text):
```python
async def _pre_attempt_check(loop, link: str, platform: str) -> None:
    """Re-read DB state before each attempt; raise _AlreadyConfirmed or increment counter.
    ...
    """
    purchased, existing_order_id = await loop.run_in_executor(
        None, get_item_order_state_sync, link
    )
    if existing_order_id is not None:
        writeLog(
            f"[{platform}] prior confirmed order_id={existing_order_id} -- skipping retry",
            "INFO",
        )
        raise _AlreadyConfirmed(existing_order_id)
    if purchased:
        writeLog(
            f"[{platform}] item already purchased (legacy path) -- skipping retry",
            "INFO",
        )
        raise _AlreadyConfirmed("")
    await loop.run_in_executor(None, increment_checkout_attempts_sync, link)
```
Insert the new marker check between the `purchased` branch and the `increment_checkout_attempts_sync` fallthrough (order-of-precedence matters -- see RESEARCH.md Pitfall 6: a sentinel `order_id` already short-circuits via the FIRST branch above, so it never reaches the marker check):
```python
    attempted_at = await loop.run_in_executor(
        None, get_place_order_marker_sync, link
    )
    if attempted_at is not None:
        raise _PossiblyPlaced(attempted_at)
```

**`_try_auto_buy` except clause to mirror** (`core/orchestrator.py:437-446`, exact current text):
```python
    try:
        result = await with_retry(
            lambda: _attempt_buy(plugin, link),
            policy,
            should_retry=lambda r: not r[0],  # only retry on auto_buy failure; ...
            on_attempt=lambda _: _pre_attempt_check(loop, link, platform),
        )
    except _AlreadyConfirmed as confirmed:
        writeLog(f"[{platform}] idempotency exit: order_id={confirmed.order_id}", "INFO")
        return
```
New `except _PossiblyPlaced as pp:` clause added after this one -- unlike `_AlreadyConfirmed` (silent return), D-04 requires firing the operator alert via `_build_event` + `dispatcher.notify()`.

**`_build_event` + notify pattern to reuse verbatim** (`core/orchestrator.py:80-88`, `_park_plugin`, the closest existing "alert on a terminal per-item/per-plugin state" example):
```python
async def _park_plugin(plugin, n_budget: int, dispatcher) -> None:
    """Log and notify that a plugin has been parked after exceeding its failure budget."""
    writeLog(
        f"[{plugin.__class__.__name__}] failure budget exceeded ({n_budget} failures) -- parked",
        "ERROR",
    )
    if dispatcher is not None:
        await dispatcher.notify(_build_event("", "", plugin.__class__.__name__, "plugin_parked"))
```
And `_build_event` itself (`core/orchestrator.py:180-189`):
```python
def _build_event(name: str, link: str, plugin_name: str, action: str):
    """Construct a NotificationEvent for the given action."""
    from notifications.base import NotificationEvent
    return NotificationEvent(
        item_name=name,
        item_url=link,
        platform=plugin_name,
        timestamp=datetime.now(timezone.utc),
        action=action,
    )
```
New `except _PossiblyPlaced:` clause in `_try_auto_buy` should call `dispatcher.notify(_build_event(name, link, platform, "possibly_placed"))` -- using the real `name`/`link` already in scope in `_try_auto_buy` (unlike `_park_plugin`'s `""`/`""`, since this alert is item-specific). `NotificationDispatcher`/`SoundNotifier`/`DiscordNotifier` all degrade gracefully on unknown `action` strings (no notifier-side code change needed).

**D-15 login-failure short-circuit (Pitfall 4/Open Question 2 mechanism):** inspect `plugin._checkout_stage` (already set before each stage, `core/plugin_base.py:100`) after `_attempt_buy` returns `(False, None)` inside `_try_auto_buy`; when it equals `"login"`, skip cart-retry backoff and fire a `"login_failed"` alert via the same `_build_event`/`dispatcher.notify()` pattern above. This mirrors the existing read of `plugin._checkout_stage` at `core/orchestrator.py:449`:
```python
    success, order_id = result
    if not success:
        writeLog(f"[{platform}] cart-retry exhausted (stage={plugin._checkout_stage})", "WARNING")
        return
```

---

### `plugins/shopbot_plugin_amazon.py` (plugin, request-response) -- BF-02 marker write + BF-01 WAF wiring + BF-03 login verification

**Analog for the marker write:** the file's own place-order stage (root-cause site to fix), `plugins/shopbot_plugin_amazon.py:460-463`:
```python
            self._checkout_stage = "place-order"
            async with asyncio.timeout(step_timeout_secs):
                self._last_tab = tab  # BUY-03: expose confirmation page to orchestrator
                return await self.place_order_guarded(place_order.click)
```
This is the swallowed-`TimeoutError` root cause: the whole block is inside the outer `try:` (line 390) whose `except Exception as exc:` (line 464) returns `False`, which `should_retry=lambda r: not r[0]` reads as retryable -- re-clicking place-order on the next attempt. The marker write (new `from models import mark_place_order_attempted_sync` import, called via `await asyncio.get_running_loop().run_in_executor(None, mark_place_order_attempted_sync, url, now_iso)`) MUST land immediately before `return await self.place_order_guarded(...)`, inside the same `async with asyncio.timeout(...)` block, so it durably commits before the click even if the click itself times out.

**No existing plugin imports `models.py` today** -- this is a new dependency edge. Do NOT route through `write_queue` (async `put()` does not guarantee on-disk durability before the click fires -- defeats D-01). The existing direct-write-via-`run_in_executor` precedent for this exact idiom lives in the orchestrator (`increment_checkout_attempts_sync` calls at `core/orchestrator.py:345,423`), being extended into plugin code for the first time here.

**Analog for BF-01 WAF wiring:** the already-implemented, already-tested `solve_recaptcha` branch two sections later in the same function, `plugins/shopbot_plugin_amazon.py:168-195`:
```python
        # Solve via run_in_executor; timeout wraps ONLY the executor call (Pitfall 3).
        # WR-01: asyncio.timeout cancels the await but not the executor thread.
        # ...
        loop = asyncio.get_running_loop()
        try:
            async with asyncio.timeout(120):
                token = await loop.run_in_executor(
                    None, solver.solve_recaptcha, sitekey, pageurl
                )
        except (asyncio.TimeoutError, Exception) as exc:
            _log.warning("CAPTCHA solve failed: %s", exc.__class__.__name__)
            await self._wait_user_action(
                self.captcha_event,
                "CAPTCHA solve failed on Amazon. Solve it in the browser, then press Enter.",
            )
            return

        # V5 input validation: reject token containing quote, backslash, or newline (CR-02).
        if not token or "'" in token or "\\" in token or "\n" in token:
            _log.warning("CAPTCHA token failed validation -- falling back to manual pause")
            await self._wait_user_action(
                self.captcha_event,
                "CAPTCHA token invalid on Amazon. Solve it in the browser, then press Enter.",
            )
            return

        await self._inject_token(tab, token)
```
The WAF branch to REPLACE (`plugins/shopbot_plugin_amazon.py:147-158`, exact current text):
```python
        # WAF detection: window.gokuProps present means Amazon WAF CAPTCHA (deferred).
        try:
            waf_raw = await tab.evaluate(_WAF_PROBE_JS)
        except Exception:
            waf_raw = None
        if waf_raw:
            _log.info("Amazon WAF CAPTCHA detected -- auto-solve deferred; falling back to manual pause")
            await self._wait_user_action(
                self.captcha_event,
                "Amazon WAF CAPTCHA detected. Solve it in the browser, then press Enter.",
            )
            return
```
New branch keeps the `waf_raw` probe (`_WAF_PROBE_JS`, lines 59-63) and `_json.loads(waf_raw)` decode of `{key, iv, context}`, then calls `solver.solve_amazon_waf(key, iv, context, pageurl)` under the same `run_in_executor` + `asyncio.timeout(120)` + `except (asyncio.TimeoutError, Exception)` shape shown above, falls back to `self._wait_user_action(self.captcha_event, ...)` on ANY non-success path (D-08), and on success calls a new `_inject_waf_token(tab, solution)` method.

**Analog for the token-injection helper:** `_inject_token` (`plugins/shopbot_plugin_amazon.py:114-126`), the exact quote/backslash/newline-safe `json.dumps()` pattern to reuse for the WAF voucher/token string:
```python
    async def _inject_token(self, tab, token: str) -> None:
        """Inject a validated reCAPTCHA token into the page via JS callbacks."""
        safe = _json.dumps(token)   # produces "..." with all special chars escaped (CR-02)
        inject_js = (
            f"(function(){{"
            f"var el=document.getElementById('g-recaptcha-response');"
            f"if(el){{el.value={safe};}}"
            f"var c=window.___grecaptcha_cfg&&window.___grecaptcha_cfg.clients;"
            f"if(c){{Object.values(c).forEach(function(x){{"
            f"if(x&&x.callback){{try{{x.callback({safe});}}catch(e){{}}}}"
            f"}});}}}})();"
        )
        await tab.evaluate(inject_js)
```
Same `_json.dumps()` escaping + same rejection-before-injection invariant (quote/backslash/newline) must apply to both `captcha_voucher` and `existing_token` strings from `solve_amazon_waf`'s returned dict before any `tab.evaluate()` interpolation (V5 ASVS control, RESEARCH.md Security Domain). Injection mechanism (cookie via CDP `tab.send(cdp_storage.set_cookies(...))`, reusing `_dicts_to_cookie_params`-adjacent pattern in `core/plugin_base.py:17-61`, vs. JS-callback) is flagged LOW confidence / operator debt per RESEARCH.md Assumption A1 -- implement best-effort, document as unverified.

**Analog for BF-03 `login()` -> bool:** the file's own `login()` (`plugins/shopbot_plugin_amazon.py:299-364`), every `return` (bare, implicit-None on missing creds/fields) becomes `return False`; final success path gains the verification call before `return True`:
```python
    async def login(self) -> None:
        """Sign in to Amazon using AMZ_EMAIL / AMZ_PASSWORD env vars (SEC-01)."""
        store = get_store()
        email = store.get("AMZ_EMAIL") or ""
        password = store.get("AMZ_PASSWORD") or ""
        if not email or not password:
            writeLog("AMZ_EMAIL or AMZ_PASSWORD not set -- skipping login", "ERROR")
            return                                    # -> return False
        try:
            tab = await self.driver.get("https://www.amazon.com/ap/signin?...")
            email_field = await tab.select("#ap_email", timeout=10)
            if not email_field:
                writeLog("Email field not found on Amazon sign-in page", "ERROR")
                return                                # -> return False
            await email_field.send_keys(email)
            continue_btn = await tab.select("#continue", timeout=10)
            if continue_btn:
                await continue_btn.click()
            await self._wait_user_action(self.passkey_event, "...")
            password_field = await tab.select("#ap_password", timeout=10)
            if not password_field:
                writeLog("Password field not found on Amazon sign-in page", "ERROR")
                return                                # -> return False
            await password_field.send_keys(password)
            sign_in_btn = await tab.select("#signInSubmit", timeout=10)
            if not sign_in_btn:
                writeLog("Sign-in submit button not found", "ERROR")
                return                                # -> return False
            await sign_in_btn.click()
            mfa_form = await tab.select("#auth-mfa-form", timeout=10)
            if mfa_form:
                await self._wait_user_action(self.otp_event, "...")
            writeLog("Signed in to Amazon", "INFO")
            await self.save_session()                 # -> move AFTER verification; only save on confirmed login
        except Exception as exc:
            writeLog(f"Error during Amazon sign-in: {exc.__class__.__name__}", "ERROR")
                                                        # -> return False (was implicit None)
```
Set `self._checkout_stage = "login"` immediately before this call-site's caller (`auto_buy`, line 389: `await self.login()`) so the D-15 orchestrator-layer short-circuit (Pitfall 4/Open Question 2) can detect a login-stage failure. `auto_buy` at line 389 is the ONLY plugin where `login()` runs before any DOM interaction (navigate/quantity/buy-now) -- see RESEARCH.md Pitfall 3.

---

### `plugins/shopbot_plugin_bestbuy.py` (plugin, request-response) -- BF-02 marker write (BestBuy parity) + BF-03 login verification

**Analog:** `plugins/shopbot_plugin_amazon.py` for the marker-write pattern (byte-for-byte identical place-order shape); the file's own `login()` for the BF-03 conversion.

**BestBuy's identical swallowed-`TimeoutError` place-order site** (`plugins/shopbot_plugin_bestbuy.py:389-396`, exact current text -- CONFIRMED identical bug shape to Amazon per RESEARCH.md Pitfall 5):
```python
            self._checkout_stage = "place-order"
            async with asyncio.timeout(step_timeout_secs):
                place_order = await tab.select(".button--place-order", timeout=10)
                if not place_order:
                    writeLog("Place order button not found", "ERROR")
                    return False
                self._last_tab = tab  # BUY-03: expose confirmation page to orchestrator
                return await self.place_order_guarded(place_order.click)
        except Exception as exc:
            writeLog(
                f"Error during BestBuy auto-buy at stage {self._checkout_stage!r}: {exc.__class__.__name__}",
                "ERROR",
            )
            return False
```
Same fix shape as Amazon: `from models import mark_place_order_attempted_sync` + `run_in_executor` write immediately before `return await self.place_order_guarded(place_order.click)`, inside the same `async with asyncio.timeout(...)` block. The guard mechanism in `core/orchestrator.py` (`_PossiblyPlaced`) is platform-agnostic once built -- only the marker-write call site is plugin-local. (RESEARCH.md Open Question 1 recommends including BestBuy in this phase since the marginal cost is ~4 lines and the guard is being built platform-agnostically regardless; flag explicitly if descoped to Amazon-only.)

**BF-03 `login()` -> bool conversion** (`plugins/shopbot_plugin_bestbuy.py:224-253`, exact current text):
```python
    async def login(self) -> None:
        """Sign in to BestBuy using BB_EMAIL / BB_PASSWORD env vars (SEC-01)."""
        store = get_store()
        email = store.get("BB_EMAIL") or ""
        password = store.get("BB_PASSWORD") or ""
        if not email or not password:
            writeLog("BB_EMAIL or BB_PASSWORD not set -- skipping login", "ERROR")
            return                                     # -> return False
        try:
            tab = await self.driver.get("https://www.bestbuy.com/identity/signin")
            email_field = await tab.select("#fld-e", timeout=10)
            if email_field:
                await email_field.send_keys(email)
            pwd_field = await tab.select("#fld-p1", timeout=10)
            if pwd_field:
                await pwd_field.send_keys(password)
            submit = await tab.select(".cia-form__controls__submit", timeout=10)
            if submit:
                await submit.click()
            writeLog("Signed in to BestBuy", "INFO")
            await self.save_session()                  # -> move AFTER verification
        except Exception as exc:
            writeLog(f"Error during BestBuy sign-in: {exc.__class__.__name__}", "ERROR")
                                                         # -> return False
```
Per RESEARCH.md D-12/table: tighter signal for BestBuy = redirect off `/identity/signin` (URL-only; landing-page selector unverified). **Important ordering note (RESEARCH.md Pitfall 3):** BestBuy's `auto_buy()` calls `login()` at line 349, AFTER `add-to-cart` (302-309) and `checkout-proceed` (337-344) have already run -- D-15's "abort before add-to-cart/checkout" is only literally true for Amazon. Implement D-15 uniformly as "return `False` immediately when `login()` returns `False`, aborting all remaining stages" (do not gate acceptance on "no add-to-cart occurred" for BestBuy). Set `self._checkout_stage = "login"` immediately before the `await self.login()` call site (line 349) for the same orchestrator-layer signal purpose as Amazon.

---

### `plugins/shopbot_plugin_{walmart,target,gamestop,newegg,squareenix}.py` (plugin, request-response) -- BF-03 generic login verification

**Analog:** `plugins/shopbot_plugin_walmart.py:118-146` (representative; all 5 community plugins share this structure per RESEARCH.md -- credential read -> navigate -> best-effort selector fill -> click -> `writeLog("Signed in...")` with zero post-submit verification).

**Exact current text to convert** (`plugins/shopbot_plugin_walmart.py:118-146`):
```python
    async def login(self) -> None:
        """Sign in to Walmart using WALMART_EMAIL / WALMART_PASSWORD env vars (SEC-01)."""
        store = get_store()
        email = store.get("WALMART_EMAIL") or ""
        password = store.get("WALMART_PASSWORD") or ""
        if not email or not password:
            writeLog("WALMART_EMAIL or WALMART_PASSWORD not set -- skipping login", "ERROR")
            return                                     # -> return False

        try:
            tab = await self.driver.get("https://www.walmart.com/account/login")
            email_field = await tab.select("#email", timeout=10)
            if email_field:
                await email_field.send_keys(email)
            password_field = await tab.select("#password", timeout=10)
            if password_field:
                await password_field.send_keys(password)
            sign_in_btn = await tab.select('[data-testid="sign-in-form-submit"]', timeout=10)
            if sign_in_btn:
                await sign_in_btn.click()
            writeLog("Signed in to Walmart", "INFO")
                                                         # -> call _verify_login_generic, return True/False
        except Exception as exc:
            writeLog(f"Error during Walmart sign-in: {exc.__class__.__name__}", "ERROR")
                                                         # -> return False
```
All 5 community plugins use ONLY the generic signal from `core/plugin_base.py` (`_verify_login_generic(tab, signin_url_fragment, form_selector)`) -- no platform-specific override, per D-12. Selector/fragment table (from RESEARCH.md, Claude's-discretion values, selector tuning stays operator debt):

| Plugin | `signin_url_fragment` | `form_selector` |
|---|---|---|
| Walmart | `/account/login` | `#email` |
| Target | `/account/signin` | `[data-test="accountNav-signIn"] input[type="email"]` |
| GameStop | `/login` | `input#login-form-email` |
| NewEgg | `/identity/signin` | `#labeled-input-signEmail` |
| SquareEnix | `/account/login` | `[type="email"]` |

**Ordering note:** all 5 community plugins call `login()` mid-flow (after `add_to_cart.click()` -> cart navigate -> `checkout_btn.click()`), same as BestBuy -- same D-15 "return False immediately, abort remaining stages" implementation applies uniformly (RESEARCH.md Pitfall 3). Set `self._checkout_stage = "login"` before each plugin's `await self.login()` call site.

---

### `core/plugin_base.py` (ABC/model, request-response) -- BF-03 shared verification helper + contract change

**Analog:** the file's own `place_order_guarded` (lines 148-170) -- the precedent for an additive, non-abstract, concrete method on `RetailerPlugin` that keeps `PLUGIN_API_VERSION = 2` (line 12).

**`login()` ABC to change** (`core/plugin_base.py:172-174`, exact current text):
```python
    async def login(self) -> None:
        """Authenticate with the retail platform. No-op default."""
        return None
```
Becomes:
```python
    async def login(self) -> bool:
        """Authenticate with the retail platform. No-op default returns True
        (a login-less plugin is trivially "logged in")."""
        return True
```

**New concrete helper** (place near `place_order_guarded`, same additive-method style, lines 148-170 as the structural template):
```python
    async def place_order_guarded(self, click_fn) -> bool:
        """Invoke click_fn only when test_mode and monitor_only are both False.

        Returns True when the click fires, False when suppressed.
        Never raises. PLUGIN_API_VERSION stays 2 (additive concrete method, BUY-02).
        ...
        """
        debug = getattr(self.config, "debug", None) if self.config else None
        test_mode = getattr(debug, "test_mode", True)
        monitor_only = getattr(debug, "monitor_only", True)
        if test_mode or monitor_only:
            writeLog("place-order suppressed (monitor_only/test_mode)", "INFO")
            return False
        await click_fn()
        return True
```
New `_verify_login_generic(self, tab, signin_url_fragment, form_selector) -> bool` mirrors this "getattr-safe, never raises, explicit bool return, `writeLog` on the notable branch" shape (D-13: any exception or ambiguity -> `False`, caught internally, never propagated).

**`relaunch()` call site to change** (`core/plugin_base.py:210-216`, exact current text):
```python
        session_restored = await self.restore_session()
        if not session_restored:
            writeLog(f"[{plugin_name}] restore_session=False; re-logging in", "INFO")
            await self.login()
        else:
            writeLog(f"[{plugin_name}] relaunch: session restored; skipping login", "INFO")
```
Becomes: capture `login_ok = await self.login()`; if `not login_ok`, `writeLog(..., "ERROR")` that re-login failed / NOT authenticated (no dispatcher plumbing here -- `relaunch()` has never had orchestrator access; the plugin's `_checkout_stage`/`auto_buy()` naturally re-attempts login next cycle and surfaces the D-15 alert path via the orchestrator, per RESEARCH.md's explicit "No dispatcher plumbing needed here" guidance).

**`_checkout_stage` attribute already exists** (`core/plugin_base.py:100`, `__init__`):
```python
        self._checkout_stage: str = ""  # BUY-06: set before each DOM stage; readable on CancelledError
```
This is the existing cross-plugin signal every `login()` call site sets to `"login"` before invoking `self.login()` -- no new attribute needed.

---

## Shared Patterns

### Idempotent SQLite column migration
**Source:** `models.py:48-80` (`initialize_db`, `existing = {row[1] for row in conn.execute("PRAGMA table_info(items)")...}` then `if "<col>" not in existing: conn.execute("ALTER TABLE ...")`)
**Apply to:** `models.py` BF-02 `place_order_attempted_at` column addition — must go inside the same `existing` check block, following the Phase-19 confirmation-columns precedent exactly.

### `_sync` accessor naming + connection idiom
**Source:** `models.py:10-30` (`get_db_connection()` context manager, WAL + `busy_timeout=5000` + `synchronous=NORMAL`), `models.py:133-158` (paired read/write accessor shape)
**Apply to:** `get_place_order_marker_sync` / `mark_place_order_attempted_sync` — both single-purpose, single-statement, parameterized, no new connection logic.

### Sentinel-exception-driven retry abort
**Source:** `core/orchestrator.py:376-380` (`_AlreadyConfirmed`), `:400-423` (`_pre_attempt_check` raise sites), `:437-446` (`_try_auto_buy` catch site)
**Apply to:** `_PossiblyPlaced` — same 3-part shape (exception class -> raise in `on_attempt` hook -> catch in `_try_auto_buy`), reusing `with_retry`/`RetryPolicy` from `core/retry.py` unmodified (D-05). AST guard `tests/test_no_retry_loops.py::test_no_for_attempt_in_range_outside_retry` forbids any new `for attempt in range(...)` loop outside `core/retry.py` — do not add one.

### Blocking external calls off the event loop
**Source:** `plugins/shopbot_plugin_amazon.py:172-177` (`loop.run_in_executor(None, solver.solve_recaptcha, sitekey, pageurl)` inside `async with asyncio.timeout(120):`)
**Apply to:** `solver.solve_amazon_waf(...)` call in the new WAF branch — identical `run_in_executor` + `asyncio.timeout(120)` + `except (asyncio.TimeoutError, Exception)` wrapper; also the new `mark_place_order_attempted_sync` write via `run_in_executor` (sqlite3 is blocking).

### Token/voucher injection safety
**Source:** `plugins/shopbot_plugin_amazon.py:114-126` (`_inject_token`, `_json.dumps()` escaping) + the CR-02 quote/backslash/newline rejection at `:186-187`
**Apply to:** the new WAF voucher/token injection helper — same escaping, same rejection characters, before any `tab.evaluate()` interpolation.

### Operator alert fan-out
**Source:** `core/orchestrator.py:80-88` (`_park_plugin`) + `:180-189` (`_build_event`) + `notifications/dispatcher.py:27-46` (`NotificationDispatcher.notify`, per-channel try/except isolation)
**Apply to:** the new `_PossiblyPlaced` alert (BF-02, action=`"possibly_placed"`) and the new login-failure alert (BF-03, action=`"login_failed"`) — both fired from the orchestrator layer only (plugins have no dispatcher reference; RESEARCH.md Pitfall 4). Unknown `action` strings degrade gracefully in every existing notifier — no notifier-side changes needed.

### `getattr`-safe, never-raise, explicit-bool concrete ABC methods
**Source:** `core/plugin_base.py:148-170` (`place_order_guarded`)
**Apply to:** the new `_verify_login_generic` helper and every plugin's `login() -> bool` conversion — safe defaults on missing config, explicit `return True`/`return False` at every branch (no implicit `None`), logged via `writeLog` on the notable/failure path only.

## No Analog Found

None. Every file in scope has a direct, exact-match analog already in the codebase (either the same file's existing sibling pattern, or a byte-for-byte structurally identical file — Amazon/BestBuy place-order timeout shape, and the 5 community plugins' `login()` shape).

## Metadata

**Analog search scope:** `core/`, `plugins/`, `models.py`, `notifications/`, `tests/` (full read of every touched file — all under 2,000 lines, single-pass reads, no re-reads)
**Files scanned:** `models.py`, `core/orchestrator.py`, `core/captcha.py`, `core/plugin_base.py`, `core/confirmation.py`, `core/retry.py`, `plugins/shopbot_plugin_amazon.py`, `plugins/shopbot_plugin_bestbuy.py`, `plugins/shopbot_plugin_walmart.py`, `notifications/dispatcher.py`, `notifications/base.py`, `tests/test_cart_retry.py`, `tests/test_plugin_base.py`, `tests/test_captcha_plugin.py`
**Pattern extraction date:** 2026-07-02
