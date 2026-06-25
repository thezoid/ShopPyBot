# Phase 20: Checkout Profile + Form-Fill - Research

**Researched:** 2026-06-11
**Domain:** Python async (nodriver), CredentialStore, pydantic, CLI subparsers, form-fill automation
**Confidence:** HIGH (CVV threading path fully traced; nodriver API verified locally; store patterns confirmed from source)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- 9 address keys stored in CredentialStore (off-disk), never in config.yml
- New `CHECKOUT_PROFILE_KEYS` constant separate from `SECRET_KEYS`
- Keys: CHECKOUT_FIRST_NAME, CHECKOUT_LAST_NAME, CHECKOUT_ADDRESS_LINE1, CHECKOUT_ADDRESS_LINE2, CHECKOUT_CITY, CHECKOUT_STATE, CHECKOUT_ZIP, CHECKOUT_COUNTRY, CHECKOUT_PHONE
- `shoppybot setup checkout-profile` uses VISIBLE input (not getpass) for the 9 address fields
- CHECKOUT_ADDRESS_LINE2 is optional (Enter to skip); the other 8 are required
- CheckoutProfile pydantic model in core/checkout_profile.py; loaded at plugin setup() time into self._checkout_profile
- CVV via existing getpass flow (core/cli/run.py -> BotService.run(cvv)); never stored
- Only BestBuy + Amazon form-fill; other 5 plugins unaffected
- Missing selector: log WARNING with selector name, return False (no submit of partial form)
- CI grep/AST assertion: no _cvv in any writeLog() argument on checkout paths
- Form-fill happens inside auto_buy BEFORE place_order_guarded

### Claude's Discretion

- None specified

### Deferred Ideas (OUT OF SCOPE)

- Per-step timeouts / retry -> Phase 21
- Form-fill for other 5 plugins -> future
- Card-number/PAN entry or storage -> explicitly out of scope
- Live UAT of form-fill selectors -> UAT debt
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BUY-07 | User configures shipping/billing profile; bot fills BestBuy + Amazon checkout forms; payment via retailer-saved method + CVV at runtime; no full card number persisted to disk or logs | CVV threading path traced (orchestrator.py:411-414 -> plugin._cvv); nodriver fill API verified (send_keys/clear_input); store read pattern confirmed; selector candidates gathered |
</phase_requirements>

## Summary

Phase 20 is a pure extension phase: every seam exists and every dependency is already wired. The CVV threading path is already fully implemented for BestBuy (`self._cvv` pattern) and needs only to be extended to Amazon. The `CredentialStore` `get`/`set` API is stable and sufficient; the 9 profile keys are structurally identical to `SECRET_KEYS` entries except they must be excluded from `migrate_from_env` and the `EnvVarBackend.list()` scope. The `setup checkout-profile` subcommand follows the exact same sub-subcommand pattern as `items list/add/remove` and `config show/set`.

The two highest-risk items are: (1) form-fill selectors for the shipping address pages, which are MEDIUM confidence and require live UAT before production use, and (2) ensuring CVV never appears in any `writeLog()` call -- the existing `BestBuyPlugin` already does this correctly (guarded by `if cvv_field and self._cvv`; no logging of the value).

**Primary recommendation:** Implement in five sequenced plans: (1) credentials constant + CheckoutProfile model, (2) setup checkout-profile subcommand, (3) profile load at plugin setup(), (4) form-fill in BestBuy.auto_buy + Amazon.auto_buy, (5) CI CVV-not-in-logs assertion.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Profile storage (9 address keys) | CredentialStore backend | core/credentials.py constants | Same off-disk security posture as SECRET_KEYS |
| Profile model validation | core/checkout_profile.py (pydantic) | plugin.setup() loads it | Pydantic validates required fields at load time |
| Setup wizard (visible prompts) | CLI (core/cli/setup.py) | core/cli/__init__.py subparser | Follows existing handle_setup pattern exactly |
| CVV collection | CLI (core/cli/run.py getpass) | BotService.run(cvv) | Existing path; no change needed |
| CVV threading to plugin | core/orchestrator.py async_main | plugin._cvv attribute | Already implemented for BestBuy; extend to Amazon |
| Shipping form-fill | Plugin auto_buy method | nodriver tab.select + send_keys | Must run before place_order_guarded |
| CVV field fill | Plugin auto_buy method | self._cvv (runtime only) | BestBuy already does this; Amazon needs same |
| CVV-not-in-logs assertion | tests/test_checkout_profile.py | AST/grep over auto_buy source | CI regression guard |

## Standard Stack

### Core (all already in requirements.txt)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | pinned (pydantic-settings[yaml]==2.14.0) | CheckoutProfile model with field validation | Project standard for all config models |
| nodriver | 0.50.3 | Browser automation; tab.select + send_keys for form-fill | Project standard async browser driver |
| keyring / EncryptedFileBackend | existing | Stores CHECKOUT_PROFILE_KEYS off-disk | Existing CredentialStore backends; no new packages |

**No new packages required for this phase.**

## Package Legitimacy Audit

No new packages are installed in this phase. All dependencies are already in the pinned requirements.txt.

| Package | Registry | Status |
|---------|----------|--------|
| pydantic | PyPI | Already installed, pinned |
| nodriver | PyPI | Already installed, pinned |
| keyring | PyPI | Already installed, pinned |

**Packages removed due to slopcheck:** none
**Packages flagged as suspicious:** none

## Architecture Patterns

### CVV Threading Path (FULLY TRACED - HIGH confidence)

The complete existing CVV flow:

```
core/cli/run.py:handle_run()
  needs_cvv = not test_mode and not monitor_only and any(bestbuy item with auto_buy)
  cvv = getpass.getpass("Enter CVV (input hidden): ")
  svc.run(cvv)                          # line 47

core/service.py:BotService.run(cvv)
  asyncio.run(async_main(self._cfg, cvv))   # line 203

core/orchestrator.py:async_main(cfg, cvv)
  # lines 411-414:
  if cvv:
      bb_plugin = registry.route("https://www.bestbuy.com/")
      if bb_plugin:
          bb_plugin._cvv = cvv           # attribute injection on plugin instance

plugins/shopbot_plugin_bestbuy.py:auto_buy()
  # lines 305-309:
  cvv_field = await tab.select("#credit-card-cvv", timeout=10)
  if cvv_field and self._cvv:
      await cvv_field.send_keys(self._cvv)   # never logged
```

[VERIFIED: source files read directly]

**Critical finding:** CVV threading for Amazon is NOT implemented. `orchestrator.async_main` only sets `bb_plugin._cvv = cvv`; there is no equivalent for `AmazonPlugin`. The phase must add the same pattern for Amazon:

```python
# in async_main, after the BestBuy block:
if cvv:
    amz_plugin = registry.route("https://www.amazon.com/")
    if amz_plugin:
        amz_plugin._cvv = cvv
```

[VERIFIED: orchestrator.py lines 411-414 read directly; no Amazon equivalent exists]

**Also critical:** `run.py:needs_cvv` currently only checks `bestbuy.com` items. It must be extended to also check `amazon.com` items with `auto_buy=True` so the CVV prompt fires when only Amazon items are configured.

```python
# Current (line 30-36 of run.py):
needs_cvv = (
    not cfg.debug.test_mode
    and not cfg.debug.monitor_only
    and any(
        "bestbuy.com" in item.link and item.auto_buy
        for item in cfg.available.items
    )
)
# Must become:
needs_cvv = (
    not cfg.debug.test_mode
    and not cfg.debug.monitor_only
    and any(
        ("bestbuy.com" in item.link or "amazon.com" in item.link) and item.auto_buy
        for item in cfg.available.items
    )
)
```

[VERIFIED: run.py lines 29-36 read directly]

### CredentialStore Profile Read Pattern

Exact pattern for loading all 9 keys into CheckoutProfile:

```python
# In core/checkout_profile.py (new file):
from __future__ import annotations
from pydantic import BaseModel
from typing import Optional

CHECKOUT_PROFILE_KEYS: list[str] = [
    "CHECKOUT_FIRST_NAME",
    "CHECKOUT_LAST_NAME",
    "CHECKOUT_ADDRESS_LINE1",
    "CHECKOUT_ADDRESS_LINE2",   # optional
    "CHECKOUT_CITY",
    "CHECKOUT_STATE",
    "CHECKOUT_ZIP",
    "CHECKOUT_COUNTRY",
    "CHECKOUT_PHONE",
]

_REQUIRED_CHECKOUT_KEYS = [k for k in CHECKOUT_PROFILE_KEYS if k != "CHECKOUT_ADDRESS_LINE2"]

class CheckoutProfile(BaseModel):
    first_name: str
    last_name: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    zip_code: str
    country: str
    phone: str

def load_checkout_profile() -> CheckoutProfile | None:
    """Load from CredentialStore. Returns None if any required field is missing."""
    from core.credentials import get_store
    from logger import writeLog
    store = get_store()
    values = {k: store.get(k) for k in CHECKOUT_PROFILE_KEYS}
    missing = [k for k in _REQUIRED_CHECKOUT_KEYS if not values.get(k)]
    if missing:
        writeLog(f"CheckoutProfile incomplete -- missing keys: {missing}", "WARNING")
        return None
    return CheckoutProfile(
        first_name=values["CHECKOUT_FIRST_NAME"],
        last_name=values["CHECKOUT_LAST_NAME"],
        address_line1=values["CHECKOUT_ADDRESS_LINE1"],
        address_line2=values.get("CHECKOUT_ADDRESS_LINE2"),
        city=values["CHECKOUT_CITY"],
        state=values["CHECKOUT_STATE"],
        zip_code=values["CHECKOUT_ZIP"],
        country=values["CHECKOUT_COUNTRY"],
        phone=values["CHECKOUT_PHONE"],
    )
```

[VERIFIED: CredentialStore.get() signature confirmed from core/credentials.py]

**CHECKOUT_PROFILE_KEYS isolation rule:** CHECKOUT_PROFILE_KEYS must NOT be added to SECRET_KEYS. The `migrate_from_env` function iterates `SECRET_KEYS` only; `EnvVarBackend.list()` also scopes to `SECRET_KEYS`. The `KeyringBackend.list()` probes `SECRET_KEYS` individually. None of these must be widened. Profile keys live only in `core/checkout_profile.py`. [VERIFIED: credentials.py lines 47-77, 205-206, 392-419]

### setup checkout-profile Subcommand Pattern

The existing `items` and `config` subparsers both use the sub-subcommand pattern. `setup checkout-profile` should follow the same pattern as a sub-action of the existing `setup` parser, NOT a new top-level subcommand. This preserves the existing `setup` handler and adds a branch:

```python
# In core/cli/__init__.py, extend the setup subparser:
setup_sub = setup_p.add_subparsers(dest="setup_command")

cp_p = setup_sub.add_parser("checkout-profile", help="Configure shipping/billing address profile.")
cp_p.set_defaults(func=handle_setup_checkout_profile)

# Keep existing setup_p.set_defaults(func=handle_setup) as the no-sub-command fallback
# (bare 'shoppybot setup' still runs the credential wizard).
```

However, a simpler approach that avoids changing the setup parser dispatch is to add `checkout_profile` as an `action` argument or a simple `args.checkout_profile` flag. Looking at the existing pattern, the cleanest option matching project conventions is:

**Option A (recommended):** Add a sub-subparser to `setup`, mirroring how `items` has `list/add/remove`. Bare `setup` with no sub-command falls through to existing `handle_setup` via `_require_subcommand` or by keeping `setup_p.set_defaults(func=handle_setup)`.

**Option B (simpler, less consistent):** Add `--checkout-profile` flag to `setup` parser: `shoppybot setup --checkout-profile`. Check `args.checkout_profile` at the top of `handle_setup`.

Option B requires zero parser restructuring and zero risk of breaking existing `setup` tests. Option A is more consistent with `items`/`config` but requires restructuring setup dispatch. Given the project's risk-first principle and the fact that `handle_setup` is well-tested, **Option B is lower risk**.

[VERIFIED: core/cli/__init__.py lines 51-57 and 70-133 read directly; test_cli_setup.py patterns confirmed]

### Visible Input Helper Pattern

For `setup checkout-profile`, use `sys.stdin.readline()` not `input()` per ASYNC-03 compliance. The existing pattern in `core/cli/setup.py` uses `sys.stdin.readline()` for `_prompt_backend()`. Apply the same:

```python
def _prompt_visible(prompt: str) -> str | None:
    """Return visible input string or None if user skips (empty input or EOF).

    Uses sys.stdin.readline() per ASYNC-03. Non-secret address fields: echo is intended.
    """
    print(prompt, end="", flush=True)
    try:
        val = sys.stdin.readline().strip()
    except (EOFError, OSError):
        return None
    return val or None
```

[VERIFIED: core/cli/setup.py lines 28-35 read directly]

### Plugin setup() Profile Load Pattern

```python
# In plugin base or per-plugin (additive, no API bump):
async def setup(self) -> None:
    # ... existing browser init ...
    from core.checkout_profile import load_checkout_profile
    self._checkout_profile = load_checkout_profile()   # None when unconfigured; logs WARNING
```

Loading at setup() time means the profile is read once per bot run, not on every auto_buy call. [VERIFIED: plugin_base.py setup() is a no-op `...`; both plugins override it; additive attribute assignment is the established pattern per CONTEXT.md]

### nodriver Form-Fill API (VERIFIED locally, nodriver==0.50.3)

```python
# Standard fill pattern -- confirmed from installed nodriver source:
element = await tab.select(css_selector, timeout=10)
if element is None:
    writeLog(f"Selector not found: {css_selector!r}", "WARNING")
    return False   # abort without submitting
await element.clear_input()    # sets element.value = ""
await element.send_keys(text)  # focuses then dispatches char-by-char CDP key events
```

Key API facts:
- `tab.select(selector, timeout=N)` returns `Element | None` (None on timeout/miss) [VERIFIED: existing plugin code uses this pattern throughout]
- `element.send_keys(text)` calls `element.apply("(elem) => elem.focus()")` then dispatches each char via `cdp.input_.dispatch_key_event("char", text=char)` [VERIFIED: nodriver source read directly]
- `element.clear_input()` applies `element.value = ""` via JS [VERIFIED: nodriver source read directly]
- `element.set_value(value)` uses CDP `dom.set_node_value` -- fires DOM change but may bypass React/Vue event listeners; prefer `clear_input()` + `send_keys()` for SPAs [VERIFIED: nodriver source read directly]

**Pattern for a required field:**
```python
async def _fill_field(self, tab, selector: str, value: str) -> bool:
    """Fill one form field. Returns False (with WARNING log) if selector not found."""
    el = await tab.select(selector, timeout=10)
    if el is None:
        writeLog(f"Form field selector not found: {selector!r}", "WARNING")
        return False
    await el.clear_input()
    await el.send_keys(value)
    return True
```

**Pattern for an optional field:**
```python
# ADDRESS_LINE2 is optional -- skip gracefully if selector absent or value empty:
if profile.address_line2:
    el = await tab.select(selector, timeout=5)
    if el is not None:
        await el.clear_input()
        await el.send_keys(profile.address_line2)
    # selector absent for optional field is not an error
```

### Form-Fill Placement in auto_buy

BestBuy flow (existing):
1. Navigate to item URL
2. Click add-to-cart
3. Navigate to cart
4. Click checkout
5. `await self.login()`
6. **[INSERT: fill shipping form here]** -- after login, before CVV + place_order
7. Fill CVV field (existing `#credit-card-cvv`)
8. Click place_order_guarded

Amazon flow (existing + additions):
1. `await self.login()`
2. Navigate to item URL
3. Click quantity dropdown, select qty
4. Click buy-now
5. Reach order review page (`#submitOrderButtonId`)
6. **[INSERT: fill shipping form here if address edit needed]** -- before place_order_guarded
7. **[INSERT: fill CVV field here]** -- using `self._cvv`
8. `place_order_guarded(place_order.click)` [VERIFIED: shopbot_plugin_amazon.py lines 357-425]

## Form-Fill Selectors

### BestBuy Shipping Address Selectors

BestBuy checkout uses a multi-step flow. The shipping address step appears at `/checkout/r/fulfillment`. Selectors below are MEDIUM confidence based on public BestBuy DOM inspection reports and community bot repositories.

| Field | Selector | Confidence |
|-------|----------|------------|
| First name | `#first-name` | MEDIUM [ASSUMED] |
| Last name | `#last-name` | MEDIUM [ASSUMED] |
| Address line 1 | `#street` | MEDIUM [ASSUMED] |
| Address line 2 | `#street2` | LOW [ASSUMED] |
| City | `#city` | MEDIUM [ASSUMED] |
| State (select) | `#state` | MEDIUM [ASSUMED] |
| ZIP | `#zip` | MEDIUM [ASSUMED] |
| Phone | `#phone` | MEDIUM [ASSUMED] |
| CVV (existing, used) | `#credit-card-cvv` | HIGH [VERIFIED: bestbuy plugin source] |
| Place order (existing) | `.button--place-order` | HIGH [VERIFIED: bestbuy plugin source] |

**UAT required before these selectors are trusted.** BestBuy redesigns checkout frequently. The plan must include a UAT debt task.

### Amazon Shipping Address Selectors

Amazon's order review page may already have the saved address populated (no form-fill needed). The form-fill requirement for Amazon applies when the user has multiple addresses and the bot needs to select/confirm the shipping address. The CVV field location depends on whether Amazon prompts for it on the order review page.

| Field | Selector | Confidence |
|-------|----------|------------|
| CVV field (order review) | `#addCreditCardCvvInput` | MEDIUM [ASSUMED] |
| CVV field (alternate) | `input[name="cvv"]` | LOW [ASSUMED] |
| Ship to this address (if shown) | `input[name="shipToThisAddress"]` | LOW [ASSUMED] |
| Edit address link | `a[data-feature-id="oneClickShipping"]` | LOW [ASSUMED] |

**Amazon-specific consideration:** Amazon's checkout (`/gp/buy/`) typically uses the account's default address. The most common use case for form-fill is: (1) entering CVV when prompted, (2) selecting shipping address when multiple exist. Full address form-fill is needed only when no address is saved. **Plan should implement CVV field fill for Amazon first** (highest value, most certain selector location), with address-field fill as a secondary task gated on UAT.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Field validation | Manual required-field checks | pydantic BaseModel with non-optional fields | Project standard; free error messages |
| Secure storage | Encrypted dict or env write | Existing CredentialStore.set() | Already handles keyring/encrypted-file/env |
| CVV masking | Custom log filter | Never pass `self._cvv` to writeLog() | Simple discipline; add CI assertion to enforce |
| Tab element interaction | CDP raw calls | nodriver `tab.select()` + `element.send_keys()` | Already used throughout; tested API |
| Subparser registration | New module | Existing build_parser() extension pattern | Keep parser wiring in one file |

## Common Pitfalls

### Pitfall 1: CVV Leaked to writeLog via f-string
**What goes wrong:** `writeLog(f"Filling CVV: {self._cvv}", "DEBUG")` -- value appears in log file.
**Why it happens:** Developer adds debug logging during development without checking the variable name.
**How to avoid:** Never reference `self._cvv` in any writeLog() argument. The CI assertion (BUY-07 criterion 3) catches this at test time.
**Warning signs:** Any `writeLog` call containing `_cvv` as a variable or in a format string.

### Pitfall 2: Profile Values Logged
**What goes wrong:** `writeLog(f"Filling {key}: {val}", "DEBUG")` logs address value.
**Why it happens:** Analog of T-08/T-09 -- natural to log what you're filling.
**How to avoid:** Log only field NAME, never field value. `writeLog(f"Filling field: {selector!r}", "DEBUG")` is safe.

### Pitfall 3: Selector-None Partial Submit
**What goes wrong:** A required field selector returns None (DOM drift). Code continues and calls `place_order_guarded` with an incomplete shipping address.
**Why it happens:** Missing early-return after None check.
**How to avoid:** `_fill_field()` helper returns bool; auto_buy must check each required field and `return False` immediately if any fails. Optional fields (ADDRESS_LINE2) use the skip pattern.

### Pitfall 4: Amazon CVV Field Location Varies
**What goes wrong:** Amazon's order review page does not always show a CVV input. It appears only when: (a) the payment method requires re-verification, or (b) the session is new.
**Why it happens:** Amazon's checkout is context-dependent.
**How to avoid:** Check for CVV field with `timeout=5`; if `None`, skip gracefully (CVV field absent = payment already verified). Never return False when CVV field is absent -- that is a valid state.

### Pitfall 5: CHECKOUT_PROFILE_KEYS Added to SECRET_KEYS
**What goes wrong:** Adding CHECKOUT_PROFILE_KEYS to SECRET_KEYS causes `migrate_from_env` to look for `CHECKOUT_FIRST_NAME` in os.environ (wrong), and `KeyringBackend.list()` to probe those keys (wasteful).
**Why it happens:** Appears symmetrical with SECRET_KEYS handling.
**How to avoid:** Keep CHECKOUT_PROFILE_KEYS in `core/checkout_profile.py` only. `SECRET_KEYS` in `core/credentials.py` is never modified.

### Pitfall 6: _checkout_profile Not None-Checked Before Form-Fill
**What goes wrong:** Plugin tries to access `self._checkout_profile.first_name` when profile is None (not configured), raising AttributeError mid-checkout.
**Why it happens:** Profile is optional; setup is user-driven.
**How to avoid:** Guard at start of form-fill: `if self._checkout_profile is None: writeLog("[Plugin] checkout profile not configured -- skipping address fill", "WARNING"); return False`.

### Pitfall 7: send_keys on React/SPA Input Misses onChange
**What goes wrong:** `send_keys` fills the value visually but the React component's onChange handler never fires, so form validation doesn't clear and submit is blocked.
**Why it happens:** React controls input state; CDP key events may not trigger synthetic React events.
**How to avoid:** For SPA inputs, after `send_keys`, also call `element.apply("(e) => e.dispatchEvent(new Event('input', {bubbles: true}))")`. Add this to the `_fill_field` helper as a post-fill event dispatch. UAT must confirm.

### Pitfall 8: EnvVarBackend.list() Scope Not Extended for CHECKOUT_PROFILE_KEYS
**What goes wrong:** `EnvVarBackend.list()` returns only `SECRET_KEYS` -- profile keys stored via `EnvVarBackend.set()` are set in os.environ but `list()` won't show them.
**Why it happens:** `list()` is hardcoded to `SECRET_KEYS` intersection.
**How to avoid:** This is acceptable behavior -- the profile setup wizard only calls `store.set(key, val)` (get/set work regardless of list()); `list()` is only used by `migrate_from_env` and the status display. No fix needed, but document the limitation.

## Code Examples

### Exact CVV Threading for Amazon (to add in orchestrator.py)
```python
# Source: orchestrator.py async_main -- existing BestBuy block lines 411-414
# Add immediately after the BestBuy block:
if cvv:
    amz_plugin = registry.route("https://www.amazon.com/")
    if amz_plugin:
        amz_plugin._cvv = cvv
```

### Minimal _fill_field Helper (for both plugins)
```python
# Source: nodriver Element.send_keys verified from installed nodriver==0.50.3
async def _fill_field(self, tab, selector: str, value: str) -> bool:
    """Fill one required form field. Logs WARNING and returns False if selector absent."""
    el = await tab.select(selector, timeout=10)
    if el is None:
        writeLog(f"[{self.__class__.__name__}] Form field not found: {selector!r}", "WARNING")
        return False
    await el.clear_input()
    await el.send_keys(value)
    return True
```

### BestBuy auto_buy Form-Fill Insertion Point (after login, before CVV)
```python
# After: await self.login()
# Before: cvv_field = await tab.select("#credit-card-cvv", ...)
if self._checkout_profile is None:
    writeLog("[BestBuyPlugin] checkout profile not configured -- skipping address fill", "WARNING")
    return False
profile = self._checkout_profile
# Required fields -- any None selector aborts without submitting
for selector, value in [
    ("#first-name", profile.first_name),
    ("#last-name", profile.last_name),
    ("#street", profile.address_line1),
    ("#city", profile.city),
    ("#state", profile.state),
    ("#zip", profile.zip_code),
    ("#phone", profile.phone),
]:
    if not await self._fill_field(tab, selector, value):
        return False   # WARNING already logged by _fill_field
# Optional field
if profile.address_line2:
    el = await tab.select("#street2", timeout=5)
    if el is not None:
        await el.clear_input()
        await el.send_keys(profile.address_line2)
```

### CVV-Not-In-Logs CI Test Pattern (analogous to test_no_env_secret_reads.py)
```python
# tests/test_checkout_profile.py -- CVV safety assertion
import ast
from pathlib import Path

def test_cvv_not_in_writelog_args():
    """No writeLog() call in checkout code paths has _cvv in its argument expression.

    AST walk of auto_buy methods in both plugins; fail if any Call to writeLog
    has an argument whose source text contains '_cvv'.
    """
    repo_root = Path(__file__).parent.parent
    checkout_files = [
        repo_root / "plugins" / "shopbot_plugin_bestbuy.py",
        repo_root / "plugins" / "shopbot_plugin_amazon.py",
        repo_root / "core" / "checkout_profile.py",
    ]
    violations = []
    for path in checkout_files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name == "writeLog":
                    for arg in node.args:
                        arg_src = ast.unparse(arg)
                        if "_cvv" in arg_src:
                            violations.append(
                                f"{path.name}:{node.lineno}: writeLog argument contains '_cvv': {arg_src!r}"
                            )
    assert not violations, "CVV variable found in writeLog() argument:\n" + "\n".join(violations)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Global driver in main.py (Selenium) | Per-plugin nodriver Browser in setup() | Phase 2 | Form-fill must use `self.driver` tab, not a global |
| os.environ secret reads | get_store().get(KEY) | Phase 8 | Profile keys also use get_store().get() |
| input() for prompts | sys.stdin.readline() | Phase 9 (ASYNC-03) | Visible prompts use readline, not input() |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | BestBuy shipping form selectors: #first-name, #last-name, #street, #street2, #city, #state, #zip, #phone | Form-Fill Selectors | Form-fill silently does nothing; UAT required |
| A2 | Amazon CVV field selector: #addCreditCardCvvInput | Form-Fill Selectors | Amazon CVV fill fails; UAT required |
| A3 | BestBuy shipping form appears after login at /checkout/r/fulfillment before CVV step | Form-Fill Selectors | Form-fill placement in auto_buy may need adjustment |
| A4 | send_keys fires React onChange on BestBuy (SPA); may need synthetic event dispatch | Form-Fill API | Fields filled visually but validation blocked |

## Open Questions

1. **Does Amazon's order review page ever show a shipping address form that needs filling?**
   - What we know: Amazon's order summary (`/gp/buy/spc/handlers/display.html`) shows address, but it's typically pre-populated from the account default.
   - What's unclear: Whether form-fill is needed at all for Amazon shipping, or only CVV.
   - Recommendation: Implement Amazon CVV fill only in Phase 20. Address form-fill for Amazon is UAT-gated (A3). Plan should note this as a conditional task.

2. **BestBuy login() placement relative to shipping form**
   - What we know: Current BestBuy auto_buy calls `await self.login()` AFTER clicking checkout (line 303). Shipping form appears post-login.
   - What's unclear: Whether the shipping form is always shown or only when address is missing.
   - Recommendation: Load and fill shipping form after `self.login()` but before the CVV field. If all selectors return None (address already filled), the `_fill_field` helper returns False and aborts. Consider making address fill a "best effort" (log WARNING but continue) vs. hard abort. CONTEXT.md says hard abort (return False) for any missing required selector -- implement that.

3. **Amazon _cvv attribute initialization**
   - What we know: `BestBuyPlugin.__init__` explicitly sets `self._cvv = None`. `AmazonPlugin.__init__` does NOT have this.
   - What's unclear: Whether not setting `self._cvv = None` in AmazonPlugin's `__init__` causes an AttributeError if orchestrator sets it post-setup.
   - Recommendation: Add `self._cvv = None` to `AmazonPlugin.__init__` for symmetry and safety. The orchestrator sets it via `amz_plugin._cvv = cvv` after setup, which works regardless, but explicit init is cleaner.

## Environment Availability

Step 2.6: No new external dependencies identified. All tools (nodriver, pydantic, keyring) are already installed.

## Validation Architecture

> workflow.nyquist_validation is not explicitly false; section included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest with pytest-asyncio (asyncio_mode=auto) |
| Config file | pytest.ini or pyproject.toml (existing) |
| Quick run command | `pytest tests/test_checkout_profile.py -x` |
| Full suite command | `pytest` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BUY-07-1 | CHECKOUT_PROFILE_KEYS round-trip via fake store | unit | `pytest tests/test_checkout_profile.py::test_profile_keys_roundtrip -x` | No -- Wave 0 |
| BUY-07-1 | CheckoutProfile incomplete detection (missing required key) | unit | `pytest tests/test_checkout_profile.py::test_incomplete_profile_returns_none -x` | No -- Wave 0 |
| BUY-07-1 | setup checkout-profile stores 9 keys NAME-only in stdout | unit | `pytest tests/test_checkout_profile.py::test_setup_checkout_profile_stores_keys -x` | No -- Wave 0 |
| BUY-07-1 | setup checkout-profile skips optional ADDRESS_LINE2 on empty input | unit | `pytest tests/test_checkout_profile.py::test_setup_address_line2_optional -x` | No -- Wave 0 |
| BUY-07-2 | BestBuy _fill_field with fake tab fills mapped fields | async unit | `pytest tests/test_checkout_profile.py::test_bestbuy_fill_field -x` | No -- Wave 0 |
| BUY-07-2 | Missing required selector returns False + logs WARNING | async unit | `pytest tests/test_checkout_profile.py::test_missing_selector_warns_and_returns_false -x` | No -- Wave 0 |
| BUY-07-2 | Profile None guard: auto_buy returns False when no profile | async unit | `pytest tests/test_checkout_profile.py::test_autobuy_returns_false_no_profile -x` | No -- Wave 0 |
| BUY-07-3 | CVV variable not in any writeLog() arg (AST scan) | static | `pytest tests/test_checkout_profile.py::test_cvv_not_in_writelog_args -x` | No -- Wave 0 |
| BUY-07-4 | CHECKOUT_PROFILE_KEYS excluded from SECRET_KEYS | unit | `pytest tests/test_checkout_profile.py::test_checkout_keys_not_in_secret_keys -x` | No -- Wave 0 |
| BUY-07 (live) | BestBuy/Amazon shipping form-fill + CVV entry | manual UAT | n/a -- UAT debt | n/a |

### Sampling Rate
- **Per task commit:** `pytest tests/test_checkout_profile.py -x`
- **Per wave merge:** `pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_checkout_profile.py` -- covers all BUY-07 automated criteria
- [ ] `core/checkout_profile.py` -- CheckoutProfile model + load_checkout_profile() + CHECKOUT_PROFILE_KEYS

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | n/a (auth already handled) |
| V3 Session Management | no | n/a |
| V4 Access Control | no | n/a |
| V5 Input Validation | yes | pydantic BaseModel required fields; selector-None abort |
| V6 Cryptography | yes | CredentialStore backends (existing Fernet/keyring) |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| CVV logged in writeLog() | Information Disclosure | Never pass `self._cvv` to writeLog; CI AST assertion enforces |
| Profile values logged during fill | Information Disclosure | Log selector name only, never field value |
| Profile keys added to SECRET_KEYS | Tampering | Keep CHECKOUT_PROFILE_KEYS in checkout_profile.py only |
| Partial order submit on DOM drift | Tampering | Selector-None check with return False before place_order_guarded |
| CVV persisted (e.g., stored in profile) | Information Disclosure | CHECKOUT_PROFILE_KEYS explicitly excludes CVV; validated in test |

## Sources

### Primary (HIGH confidence)
- `core/credentials.py` (read directly) -- CredentialStore ABC, SECRET_KEYS, get_store(), migrate_from_env
- `core/orchestrator.py` (read directly) -- async_main CVV threading (lines 411-414)
- `core/cli/run.py` (read directly) -- needs_cvv gate, getpass flow, svc.run(cvv)
- `core/service.py` (read directly) -- BotService.run(cvv) -> asyncio.run(async_main(cfg, cvv))
- `core/plugin_base.py` (read directly) -- RetailerPlugin ABC, setup(), auto_buy signature
- `core/cli/__init__.py` (read directly) -- subparser registration pattern
- `core/cli/setup.py` (read directly) -- handle_setup structure, _prompt_backend, _prompt_secret
- `plugins/shopbot_plugin_bestbuy.py` (read directly) -- _cvv attribute, CVV fill, auto_buy flow
- `plugins/shopbot_plugin_amazon.py` (read directly) -- auto_buy flow, login, no _cvv attribute
- nodriver==0.50.3 source (read directly via python inspect) -- send_keys, clear_input, set_value signatures
- `tests/test_no_env_secret_reads.py` (read directly) -- AST/grep test pattern for CI assertions
- `tests/test_cli_setup.py` (read directly) -- setup subcommand test patterns

### Secondary (MEDIUM confidence)
- BestBuy checkout DOM selectors: community bot repositories and public BestBuy DOM reports (not verified live; UAT required)
- Amazon CVV field selector: public Amazon checkout DOM reports (not verified live; UAT required)

### Tertiary (LOW confidence)
- Amazon shipping address form selectors: training knowledge only; Amazon redesigns checkout flow regularly

## Metadata

**Confidence breakdown:**
- CVV threading path: HIGH -- read directly from source
- nodriver fill API: HIGH -- verified from installed package source
- CredentialStore patterns: HIGH -- read directly from source
- subparser wiring: HIGH -- read directly from source
- BestBuy/Amazon form selectors: MEDIUM/LOW -- assumed; UAT required
- pydantic model pattern: HIGH -- project standard, existing config_schema.py examples

**Research date:** 2026-06-11
**Valid until:** 2026-07-11 (nodriver selectors may drift sooner)
