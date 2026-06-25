# Phase 20: Checkout Profile + Form-Fill - Pattern Map

**Mapped:** 2026-06-11
**Files analyzed:** 9
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `core/credentials.py` (add constant) | config | CRUD | `core/credentials.py` SECRET_KEYS lines 47-77 | exact |
| `core/checkout_profile.py` (NEW) | model | CRUD | `core/config_schema.py` CheckoutConfig + CredentialStore.get | role-match |
| `core/cli/setup.py` (add handler) | utility | request-response | `core/cli/setup.py` handle_setup + _prompt_backend | exact |
| `core/cli/__init__.py` (add subparser) | config | request-response | `core/cli/__init__.py` items sub-subparser block lines 71-110 | exact |
| `core/plugin_base.py` (add _checkout_profile load) | middleware | request-response | `core/plugin_base.py` setup() + AmazonPlugin.setup() pattern | exact |
| `core/orchestrator.py` (add amz _cvv injection) | service | event-driven | `core/orchestrator.py` lines 411-414 BestBuy _cvv block | exact |
| `core/cli/run.py` (extend needs_cvv) | utility | request-response | `core/cli/run.py` lines 29-36 needs_cvv predicate | exact |
| `plugins/shopbot_plugin_bestbuy.py` (add form-fill) | service | request-response | `plugins/shopbot_plugin_bestbuy.py` auto_buy + CVV block lines 249-319 | exact |
| `plugins/shopbot_plugin_amazon.py` (add cvv + form-fill) | service | request-response | `plugins/shopbot_plugin_amazon.py` auto_buy lines 357-425 | exact |
| `tests/test_checkout_profile.py` (NEW) | test | batch | `tests/test_no_env_secret_reads.py` AST-walk pattern | role-match |

## Pattern Assignments

### `core/credentials.py` - add CHECKOUT_PROFILE_KEYS constant

**Analog:** `core/credentials.py` lines 47-77

**Imports pattern** (lines 15-37): already present; no new imports needed.

**Core pattern** - SECRET_KEYS declaration to copy structure from (lines 47-77):
```python
SECRET_KEYS: list[str] = [
    # Notifications
    "DISCORD_WEBHOOK_URL",
    ...
    # 2captcha
    "TWOCAPTCHA_API_KEY",
]
```

Add CHECKOUT_PROFILE_KEYS immediately after SECRET_KEYS, same style, separate constant:
```python
CHECKOUT_PROFILE_KEYS: list[str] = [
    "CHECKOUT_FIRST_NAME",
    "CHECKOUT_LAST_NAME",
    "CHECKOUT_ADDRESS_LINE1",
    "CHECKOUT_ADDRESS_LINE2",   # optional: empty-string skip at setup time
    "CHECKOUT_CITY",
    "CHECKOUT_STATE",
    "CHECKOUT_ZIP",
    "CHECKOUT_COUNTRY",
    "CHECKOUT_PHONE",
]
```

**CRITICAL isolation rule:** Do NOT add any CHECKOUT_PROFILE_KEYS entry to SECRET_KEYS.
`migrate_from_env` (line 402) iterates `SECRET_KEYS`; `EnvVarBackend.list` (line 136) also
scopes to `SECRET_KEYS`; `KeyringBackend.list` (line 206) probes `SECRET_KEYS` only. None
of these must be widened.

---

### `core/checkout_profile.py` (NEW - model + loader)

**Analogs:**
- `core/config_schema.py` CheckoutConfig (lines 264-273) -- pydantic BaseModel with Field
- `core/credentials.py` get_store() / CredentialStore.get() (lines 307-317, 98-100)

**Imports pattern** (copy from config_schema.py top-of-file style):
```python
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel
from core.credentials import get_store, CHECKOUT_PROFILE_KEYS
from logger import writeLog
```

**Core pydantic model pattern** (mirrors CheckoutConfig at line 264):
```python
class CheckoutProfile(BaseModel):
    first_name: str
    last_name: str
    address_line1: str
    address_line2: Optional[str] = None   # only optional field
    city: str
    state: str
    zip_code: str
    country: str
    phone: str
```

**Loader pattern** (uses CredentialStore.get, mirrors migrate_from_env key-name-only log style):
```python
_REQUIRED_CHECKOUT_KEYS = [k for k in CHECKOUT_PROFILE_KEYS if k != "CHECKOUT_ADDRESS_LINE2"]

def load_checkout_profile() -> CheckoutProfile | None:
    store = get_store()
    values = {k: store.get(k) for k in CHECKOUT_PROFILE_KEYS}
    missing = [k for k in _REQUIRED_CHECKOUT_KEYS if not values.get(k)]
    if missing:
        writeLog(f"CheckoutProfile incomplete -- missing keys: {missing}", "WARNING")
        return None
    return CheckoutProfile(
        first_name=values["CHECKOUT_FIRST_NAME"],
        ...
    )
```

**Key name-only logging:** Never log values. `missing` list contains key NAMES only (mirrors
`core/credentials.py` line 408: `migrated.append(key)  # name only -- never the value`).

---

### `core/cli/setup.py` - add handle_setup_checkout_profile

**Analog:** `core/cli/setup.py` handle_setup (lines 51-86) + _prompt_backend (lines 28-35)

**Visible-input helper pattern** (mirrors _prompt_backend lines 28-35 exactly; uses
sys.stdin.readline not input() per ASYNC-03):
```python
def _prompt_visible(prompt: str) -> str | None:
    print(prompt, end="", flush=True)
    try:
        val = sys.stdin.readline().strip()
    except (EOFError, OSError):
        return None
    return val or None
```

**Handler loop pattern** (mirrors handle_setup lines 68-85; replace getpass with _prompt_visible;
replace SECRET_KEYS with CHECKOUT_PROFILE_KEYS):
```python
def handle_setup_checkout_profile(args, svc) -> int:
    from core.credentials import get_store
    from core.checkout_profile import CHECKOUT_PROFILE_KEYS
    store = get_store()
    stored_count = 0
    for key in CHECKOUT_PROFILE_KEYS:
        optional = "(optional, Enter to skip)" if key == "CHECKOUT_ADDRESS_LINE2" else "(Enter to skip)"
        val = _prompt_visible(f"  {key} {optional}: ")
        if val is not None:
            store.set(key, val)
            print(f"  Stored: {key}")   # key NAME only -- never value (T-09-04)
            stored_count += 1
    print(f"\nCheckout profile setup complete. {stored_count} key(s) stored.")
    return 0
```

---

### `core/cli/__init__.py` - add setup checkout-profile sub-subparser

**Analog:** `core/cli/__init__.py` items sub-subparser block (lines 71-110) and
setup_p registration (lines 51-57).

**Option B pattern** (lower risk per RESEARCH.md -- add --checkout-profile flag to existing
setup_p rather than restructuring parser; confirmed by RESEARCH.md lines 240-241):

Add to the existing `setup_p` block (after line 56, before line 57's set_defaults):
```python
setup_p.add_argument(
    "--checkout-profile",
    action="store_true",
    default=False,
    dest="checkout_profile",
    help="Configure shipping/billing address profile.",
)
```

Then in `handle_setup` (setup.py line 58), add branch before the migrate check:
```python
if getattr(args, "checkout_profile", False):
    return handle_setup_checkout_profile(args, svc)
```

**Alternative Option A** (sub-subparser, more consistent with items/config) -- if chosen,
follow the items block pattern exactly: add `setup_sub = setup_p.add_subparsers(dest="setup_command")`,
register `cp_p = setup_sub.add_parser("checkout-profile", ...)`, keep bare `setup` via
`setup_p.set_defaults(func=_require_subcommand(setup_p))`. The `_require_subcommand` helper
is already defined at lines 59-69 and reusable.

---

### `core/plugin_base.py` - add _checkout_profile load at setup()

**Analog:** `plugins/shopbot_plugin_amazon.py` setup() lines 193-215 (additive attribute
assignment in setup override); `plugins/shopbot_plugin_bestbuy.py` __init__ lines 42-46
(_cvv = None initialization pattern).

**Additive setup pattern** -- no API bump required; each plugin overrides setup() and calls
super() or just appends at end:
```python
# Add at end of each plugin's setup(), after browser is initialized:
from core.checkout_profile import load_checkout_profile
self._checkout_profile = load_checkout_profile()   # None when unconfigured; logs WARNING
```

**Base class __init__ safety pattern** (mirrors BestBuy __init__ lines 42-46):
```python
# In RetailerPlugin.__init__ or per-plugin __init__ (additive):
self._checkout_profile = None   # set by setup(); load_checkout_profile() called there
```

---

### `core/orchestrator.py` - add amz_plugin._cvv injection

**Analog:** `core/orchestrator.py` lines 411-414 (EXACT copy to extend):

Existing BestBuy block (lines 411-414):
```python
if cvv:
    bb_plugin = registry.route("https://www.bestbuy.com/")
    if bb_plugin:
        bb_plugin._cvv = cvv
```

Add immediately after (same indentation, same pattern):
```python
if cvv:
    amz_plugin = registry.route("https://www.amazon.com/")
    if amz_plugin:
        amz_plugin._cvv = cvv
```

The outer `if cvv:` can be shared or repeated -- repeating matches the existing
style and makes each block independently readable.

---

### `core/cli/run.py` - extend needs_cvv predicate

**Analog:** `core/cli/run.py` lines 29-36 (exact lines to modify):

Current (lines 29-36):
```python
needs_cvv = (
    not cfg.debug.test_mode
    and not cfg.debug.monitor_only
    and any(
        "bestbuy.com" in item.link and item.auto_buy
        for item in cfg.available.items
    )
)
```

New (add `or "amazon.com" in item.link`):
```python
needs_cvv = (
    not cfg.debug.test_mode
    and not cfg.debug.monitor_only
    and any(
        ("bestbuy.com" in item.link or "amazon.com" in item.link) and item.auto_buy
        for item in cfg.available.items
    )
)
```

---

### `plugins/shopbot_plugin_bestbuy.py` - add shipping form-fill before CVV

**Analog:** `plugins/shopbot_plugin_bestbuy.py` auto_buy lines 249-319 (insertion point
is after `await self.login()` line 303, before `cvv_field = await tab.select(...)` line 305)

**_fill_field helper pattern** (add as plugin instance method; uses existing tab.select
pattern from lines 265-296):
```python
async def _fill_field(self, tab, selector: str, value: str) -> bool:
    """Fill one required form field. Returns False + WARNING if selector absent."""
    el = await tab.select(selector, timeout=10)
    if el is None:
        writeLog(f"[BestBuyPlugin] Form field not found: {selector!r}", "WARNING")
        return False
    await el.clear_input()
    await el.send_keys(value)
    return True
```

**Existing CVV fill pattern** to preserve (lines 305-309):
```python
cvv_field = await tab.select("#credit-card-cvv", timeout=10)
if cvv_field and self._cvv:
    # SEC-02: CVV sourced from self._cvv (set by main.py via getpass).
    # Never logged or written to disk.
    await cvv_field.send_keys(self._cvv)
```

**Form-fill insertion** (between login() and CVV):
```python
# After: await self.login()
# Before: cvv_field = await tab.select(...)
if self._checkout_profile is None:
    writeLog("[BestBuyPlugin] checkout profile not configured -- skipping address fill", "WARNING")
    return False
profile = self._checkout_profile
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
if profile.address_line2:
    el = await tab.select("#street2", timeout=5)
    if el is not None:
        await el.clear_input()
        await el.send_keys(profile.address_line2)
# (continue to existing CVV block)
```

**Error handling pattern** -- mirrors existing auto_buy outer try/except (lines 264/317-319):
```python
except Exception as exc:
    writeLog(f"Error during BestBuy auto-buy: {exc.__class__.__name__}", "ERROR")
    return False
```

---

### `plugins/shopbot_plugin_amazon.py` - add _cvv init + CVV field fill

**Analog:** `plugins/shopbot_plugin_amazon.py` __init__ lines 72-81 + auto_buy lines 357-425

**__init__ addition** (add self._cvv = None mirroring BestBuy __init__ line 46):
```python
def __init__(self, config) -> None:
    super().__init__(config)
    self._cvv = None   # injected by orchestrator after setup(); never logged
    # ... existing event attrs ...
```

**CVV fill insertion** (between place_order selector found and place_order_guarded call;
after line 419, before line 421 _last_tab assignment):
```python
# After: place_order found check (line 419)
# Insert CVV fill (optional: Amazon CVV field only appears in some sessions):
if self._cvv:
    cvv_field = await tab.select("#addCreditCardCvvInput", timeout=5)
    if cvv_field:
        # SEC-02: CVV sourced from self._cvv; never logged.
        await cvv_field.send_keys(self._cvv)
    # CVV field absent is valid (payment pre-verified); do not return False
# (continue to _last_tab and place_order_guarded)
```

**Existing selector-None error pattern** to follow for form-fill (lines 388-390, 395-397):
```python
if not qty_dropdown:
    writeLog("Quantity dropdown not found", "ERROR")
    return False
```

---

### `tests/test_checkout_profile.py` (NEW)

**Analog:** `tests/test_no_env_secret_reads.py` full file (AST-walk CI assertion pattern)

**AST-walk pattern** (copy structure from test_no_env_secret_reads.py lines 18-101):
- `repo_root = Path(__file__).parent.parent`
- scan target files with `path.read_text(encoding="utf-8")`
- `tree = ast.parse(source, filename=str(path))`
- `for node in ast.walk(tree)` to find `ast.Call` nodes
- check `func.id` or `func.attr` for target function name ("writeLog")
- check `ast.unparse(arg)` for forbidden string ("_cvv")
- collect violations as `f"{path.name}:{node.lineno}: ..."` strings
- `assert not violations, "\n".join(violations)`

**Exact CVV-not-in-logs assertion** (from RESEARCH.md lines 487-519 -- already verified):
```python
def test_cvv_not_in_writelog_args():
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
                name = func.id if isinstance(func, ast.Name) else (
                    func.attr if isinstance(func, ast.Attribute) else ""
                )
                if name == "writeLog":
                    for arg in node.args:
                        arg_src = ast.unparse(arg)
                        if "_cvv" in arg_src:
                            violations.append(
                                f"{path.name}:{node.lineno}: writeLog arg contains '_cvv': {arg_src!r}"
                            )
    assert not violations, "CVV variable found in writeLog():\n" + "\n".join(violations)
```

**Round-trip test pattern** (use fake store with dict backend, mirrors how credentials
tests use monkeypatch.setenv for EnvVarBackend):
```python
def test_profile_keys_roundtrip(monkeypatch):
    from core.credentials import EnvVarBackend
    import core.credentials as creds_mod
    store = EnvVarBackend()
    monkeypatch.setattr(creds_mod, "_store", store)
    for key in CHECKOUT_PROFILE_KEYS:
        store.set(key, f"val_{key}")
    profile = load_checkout_profile()
    assert profile is not None
    assert profile.first_name == "val_CHECKOUT_FIRST_NAME"
```

---

## Shared Patterns

### Key-Name-Only Logging (T-08/T-09)
**Source:** `core/credentials.py` lines 408, 62, 80; `core/cli/setup.py` lines 62, 80
**Apply to:** handle_setup_checkout_profile, load_checkout_profile, _fill_field
```python
print(f"  Stored: {key}")       # key NAME only -- never the value (T-09-04)
migrated.append(key)            # name only -- never the value (T-08-14)
writeLog(f"missing keys: {missing}", "WARNING")   # list of key NAMES, not values
```
Never: `writeLog(f"Filling {key}: {val}")`. Always: `writeLog(f"Filling field: {selector!r}")`.

### Selector-None Guard (return False, no partial submit)
**Source:** `plugins/shopbot_plugin_bestbuy.py` lines 267-270, 297-300; `plugins/shopbot_plugin_amazon.py` lines 388-390
**Apply to:** `_fill_field` helper in both plugins, any required-selector check
```python
if not element:
    writeLog("Selector not found", "ERROR")
    return False
```
Form-fill variant uses WARNING (DOM drift is not a code error):
```python
if el is None:
    writeLog(f"[Plugin] Form field not found: {selector!r}", "WARNING")
    return False
```

### CVV Never Logged (SEC-02)
**Source:** `plugins/shopbot_plugin_bestbuy.py` lines 306-309
**Apply to:** both plugin auto_buy CVV fill blocks, test_cvv_not_in_writelog_args
```python
if cvv_field and self._cvv:
    # SEC-02: CVV sourced from self._cvv (set by main.py via getpass).
    # Never logged or written to disk.
    await cvv_field.send_keys(self._cvv)
```

### Visible Input via sys.stdin.readline (ASYNC-03)
**Source:** `core/cli/setup.py` lines 28-35 (_prompt_backend)
**Apply to:** `_prompt_visible` helper in handle_setup_checkout_profile
```python
print("\nPrompt text: ", end="", flush=True)
try:
    choice = sys.stdin.readline().strip().lower()
except (EOFError, OSError):
    choice = ""
```

### Plugin Additive Attribute Init
**Source:** `plugins/shopbot_plugin_bestbuy.py` lines 42-46
**Apply to:** AmazonPlugin.__init__ (_cvv = None), both plugin setup() (_checkout_profile = load_checkout_profile())
```python
self._cvv = None   # injected by orchestrator after setup(); never logged
```

## No Analog Found

All files have close analogs. No entries in this section.

## Metadata

**Analog search scope:** `core/`, `plugins/`, `tests/`
**Files scanned:** 10 source files read directly
**Pattern extraction date:** 2026-06-11
