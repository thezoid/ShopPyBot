# Phase 20: Checkout Profile + Form-Fill - Context

**Gathered:** 2026-06-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can configure a shipping/billing profile that the bot fills during BestBuy and Amazon checkout. Payment uses the retailer-saved method plus a CVV entered at runtime; no full card number is persisted to disk or logs (BUY-07).

Deliverables:
1. A `shoppybot setup checkout-profile` subcommand storing 9 address keys in the CredentialStore.
2. A `CheckoutProfile` model loaded from the store at plugin setup time.
3. BestBuy + Amazon form-fill of shipping fields from the profile; CVV via getpass at runtime only.
4. A CI assertion that no `_cvv` value appears in any `writeLog()` argument on checkout paths; missing-selector WARNING + safe abort.

Out of scope: retry/timeout (Phase 21), the other 5 plugins, any storage of a card number/PAN.
</domain>

<decisions>
## Implementation Decisions

### Profile Storage & Keys
- The 9 address keys are stored in the `CredentialStore` (off-disk: keyring or encrypted file) — never in config.yml or plaintext, matching the v2.0 security posture.
- A new `CHECKOUT_PROFILE_KEYS` constant (separate from `SECRET_KEYS`) holds the 9 keys: `CHECKOUT_FIRST_NAME`, `CHECKOUT_LAST_NAME`, `CHECKOUT_ADDRESS_LINE1`, `CHECKOUT_ADDRESS_LINE2`, `CHECKOUT_CITY`, `CHECKOUT_STATE`, `CHECKOUT_ZIP`, `CHECKOUT_COUNTRY`, `CHECKOUT_PHONE`. They are PII address fields, semantically distinct from secrets.
- A new `shoppybot setup checkout-profile` subcommand prompts the 9 keys with VISIBLE input (echo aids verification; these are non-secret address fields) — NOT getpass. The store backend still keeps them off plaintext disk.
- `CHECKOUT_ADDRESS_LINE2` is optional (Enter to skip); the other 8 are required for a complete profile. If a required field is missing, the plugin warns and treats the profile as incomplete.

### CheckoutProfile Model & CVV
- A `CheckoutProfile` pydantic model in `core/checkout_profile.py`, loaded from the CredentialStore (reads the 9 keys).
- Loaded at plugin `setup()` time (once) into `self._checkout_profile` (None when unconfigured).
- CVV is provided via the existing runtime `getpass` flow (`core/cli/run.py` → `BotService.run(cvv)`); the CVV value is threaded to the plugins and entered into the CVV field at runtime only. It is NEVER stored.
- No card number / PAN is ever stored or entered by the bot — payment uses the retailer-saved payment method on the user's account; the bot supplies only the CVV (BUY-07, PCI posture).

### Form-Fill Behavior & Safety
- Only the BestBuy and Amazon plugins fill checkout forms; the other 5 plugins are unaffected.
- Missing-selector (DOM drift): if a shipping form field selector returns None, log a WARNING naming the selector and return False WITHOUT submitting an incomplete form (BUY-07 criterion 4).
- A CI grep/AST assertion confirms no `_cvv` (or the runtime cvv variable) appears in any `writeLog()` call argument on checkout code paths (BUY-07 criterion 3); profile values are never logged either.
- Form-fill happens inside `auto_buy` BEFORE `place_order_guarded` (fill shipping/billing + CVV, then the guarded final click). Consistent with Phase 18: monitor_only skips auto_buy at the orchestrator; test_mode lets form-fill run but suppresses the final click.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/credentials.py` — `CredentialStore` ABC (`get`/`set`/`delete`/`list`); `SECRET_KEYS` (20 keys) at lines 47-77; `get_store()` factory; keyring/encrypted-file/env backends. Add `CHECKOUT_PROFILE_KEYS` here and a profile read helper.
- `core/cli/setup.py` — `handle_setup` prompts each `SECRET_KEY` via `_prompt_secret` (getpass). The new `setup checkout-profile` follows this structure but uses a VISIBLE prompt helper for the 9 address fields, then `store.set(key, val)`. Key NAMES only in confirmation output (never values).
- `core/cli/__init__.py` — line ~51 `setup` subparser; add a `checkout-profile` sub-action (or a sibling subcommand) here.
- `core/cli/run.py` — existing CVV `getpass` flow (lines 8, 17, 29-47): `needs_cvv` guard, `getpass.getpass`, `svc.run(cvv)`. The CVV thread to plugins reuses this.
- `core/plugin_base.py` — `setup()` is where `self._checkout_profile` is loaded; additive, no API bump.
- `plugins/shopbot_plugin_amazon.py`, `plugins/shopbot_plugin_bestbuy.py` — `auto_buy` is where form-fill is inserted before `place_order_guarded`.

### Established Patterns
- Secrets/PII off config.yml; CredentialStore is the single source. Key NAME-only logging (never values) — T-08/T-09 threat IDs.
- getpass for hidden input; visible `sys.stdin.readline` for non-secret choices (see `_prompt_backend`).
- Additive ABC hooks; plugins load their config/profile at `setup()`.
- pydantic models for structured config (see config_schema.py).

### Integration Points
- `core/credentials.py` (CHECKOUT_PROFILE_KEYS + profile loader).
- `core/checkout_profile.py` (NEW — CheckoutProfile model).
- `core/cli/setup.py` + `core/cli/__init__.py` (`setup checkout-profile` subcommand).
- `core/plugin_base.py` (`setup()` loads `self._checkout_profile`; CVV threading to `auto_buy`).
- `plugins/shopbot_plugin_amazon.py` + `plugins/shopbot_plugin_bestbuy.py` (form-fill before `place_order_guarded`).
- CVV thread: `core/cli/run.py` → `BotService.run(cvv)` → plugin auto_buy.

</code_context>

<specifics>
## Specific Ideas

- The CVV-in-logs CI assertion (BUY-07 criterion 3) is the security regression guard for this phase — must be a plan task, scanning checkout-path `writeLog()` arguments for the cvv variable.
- The exact BestBuy/Amazon shipping-form field selectors are MEDIUM confidence and require live UAT before being trusted; plan-phase research should gather best-confidence selectors. Live form-fill verification is UAT debt.
- CVV threading: how the runtime `cvv` reaches `plugin.auto_buy` needs to be confirmed in plan-phase research (BotService.run signature → orchestrator → plugin). It may require passing cvv to the plugin instance or through the buy call.

</specifics>

<deferred>
## Deferred Ideas

- Per-step timeouts / retry around form-fill → Phase 21.
- Form-fill for the other 5 plugins → future (only BestBuy + Amazon in v4.0 scope).
- Any card-number/PAN entry or storage → explicitly out of scope (PCI; retailer-saved method only).
- Live UAT of form-fill selectors → UAT debt (tracked, not blocking).

</deferred>
