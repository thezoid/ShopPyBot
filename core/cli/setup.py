"""handle_setup: interactive credential setup handler (CLI-02)."""

import getpass
import sys

import yaml

from core.credentials import get_store, SECRET_KEYS, migrate_from_env
from core.cli.config_cmd import _atomic_yaml_write

# Backend choices for the credential store selection prompt.
_VALID_BACKENDS = frozenset({"auto", "keyring", "file", "env"})


def _prompt_secret(prompt: str) -> str | None:
    """Return secret string or None if user skips (empty input or EOF).

    Catches EOFError (closed stdin / CI), GetPassWarning (redirected stdin),
    and StopIteration (exhausted mock side_effect in tests) -- all treated as skip.
    """
    try:
        val = getpass.getpass(prompt).strip()
    except (EOFError, getpass.GetPassWarning, StopIteration):
        return None
    return val or None


def _prompt_backend() -> str:
    """Ask the user which credential backend to use; default to 'auto' on empty."""
    print("\nCredential backend (auto/keyring/file/env) [auto]: ", end="", flush=True)
    try:
        choice = sys.stdin.readline().strip().lower()
    except (EOFError, OSError):
        choice = ""
    return choice if choice in _VALID_BACKENDS else "auto"


def _write_backend(chosen: str) -> None:
    """Write credentials.backend to config.yml atomically."""
    import core.cli.config_cmd as _cmd  # access at call-time so monkeypatch works

    path = _cmd._DEFAULT_YAML_PATH
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        data = {}
    data.setdefault("credentials", {})["backend"] = chosen
    _atomic_yaml_write(path, data)


def _prompt_visible(prompt: str) -> str | None:
    """Return visible (echoed) input string or None if empty / EOF.

    Mirrors _prompt_backend but returns the value for caller use. Uses
    sys.stdin.readline() per ASYNC-03 (no input() builtin).
    """
    print(prompt, end="", flush=True)
    try:
        val = sys.stdin.readline().strip()
    except (EOFError, OSError):
        return None
    return val or None


def handle_setup_checkout_profile(args, svc) -> int:  # noqa: ARG001
    """Interactively prompt the 9 CHECKOUT_PROFILE_KEYS with VISIBLE input.

    Confirmation output contains key NAMES only -- never values (T-20-03).
    CHECKOUT_ADDRESS_LINE2 is optional; empty input skips store.set for that key.
    No card number or CVV is ever prompted or stored here.
    """
    from core.credentials import get_store
    from core.checkout_profile import CHECKOUT_PROFILE_KEYS

    store = get_store()
    stored_count = 0
    print("\nCheckout profile setup (address keys only -- no card/CVV).")
    for key in CHECKOUT_PROFILE_KEYS:
        if key == "CHECKOUT_ADDRESS_LINE2":
            label = f"  {key} (optional, Enter to skip): "
        else:
            label = f"  {key} (Enter to skip): "
        val = _prompt_visible(label)
        if val is not None:
            store.set(key, val)
            print(f"  Stored: {key}")  # key NAME only -- never the value (T-20-03)
            stored_count += 1

    print(f"\nCheckout profile setup complete. {stored_count} key(s) stored.")
    return 0


def handle_setup(args, svc) -> int:
    """Credential setup wizard.

    --migrate: import env-var secrets into the active backend (back-compat alias).
    --checkout-profile: populate the 9 shipping address keys (Option B routing).
    Interactive: prompt each SECRET_KEY via getpass (no echo); confirm by KEY NAME only.
    Writes chosen credentials.backend to config.yml via _atomic_yaml_write.
    """
    if getattr(args, "checkout_profile", False) is True:
        return handle_setup_checkout_profile(args, svc)

    if getattr(args, "migrate", False):
        store = get_store()
        migrated = migrate_from_env(store)
        for key in migrated:
            print(f"Migrated: {key}")  # key NAME only -- never the value (T-08-14)
        if not migrated:
            print("No env-var secrets found to migrate.", file=sys.stderr)
        print(f"Migrated {len(migrated)} key(s).")
        return 0

    store = get_store()
    stored_count = 0
    _current_prefix: list[str] = []

    for key in SECRET_KEYS:
        prefix = key.split("_")[0]
        if not _current_prefix or _current_prefix[0] != prefix:
            _current_prefix[:] = [prefix]
            print(f"\n[{prefix}]")
        val = _prompt_secret(f"  {key} (Enter to skip): ")
        if val is not None:
            store.set(key, val)
            print(f"  Stored: {key}")  # key NAME only -- never the value (T-09-04)
            stored_count += 1

    chosen = _prompt_backend()
    _write_backend(chosen)
    print(f"\nSetup complete. {stored_count} key(s) stored.")
    return 0
