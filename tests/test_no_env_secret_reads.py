"""SC1 grep guard: assert no os.environ secret reads remain in consumer code.

CRED-01 compliance test (T-08-13): after the plan 08-04 migration, the ONLY
places that may read os.environ for a SECRET_KEYS name are:

  1. core/credentials.py -- EnvVarBackend.get and migrate_from_env
     (both are the canonical single access points)
  2. core/config_schema.py -- SmsConfig.require_creds_if_enabled
     (startup presence gate; runs before init_store; deliberate exception)

All plugins and notifiers must route through get_store().get(KEY).
"""

from pathlib import Path
import re


def test_no_os_environ_secret_reads():
    """Assert no os.environ secret reads remain in plugins/, notifications/, or core/
    except the two documented exception sites.

    Algorithm:
      1. Collect all .py files under plugins/, notifications/, and core/.
      2. For each file, skip lines whose stripped form starts with '#' (comments).
      3. For each non-comment line, check whether it contains an os.environ read
         of any SECRET_KEYS name (both os.environ.get("KEY") and os.environ["KEY"]).
      4. core/credentials.py is fully exempted (EnvVarBackend.get + migrate_from_env
         are the canonical allowed sites).
      5. core/config_schema.py is allowed ONLY for TWILIO_* reads (SmsConfig validator
         deliberate exception documented in RESEARCH Pitfall 7).
    """
    from core.credentials import SECRET_KEYS

    repo_root = Path(__file__).parent.parent

    violations: list[str] = []

    dirs_to_scan = [
        repo_root / "plugins",
        repo_root / "notifications",
        repo_root / "core",
    ]

    scanned_files: list[Path] = []

    for scan_dir in dirs_to_scan:
        for py_file in sorted(scan_dir.rglob("*.py")):
            scanned_files.append(py_file)
            rel = py_file.relative_to(repo_root)

            # Exception 1: core/credentials.py is entirely exempt
            # (EnvVarBackend.get and migrate_from_env are the single allowed sites)
            if py_file.name == "credentials.py" and py_file.parent.name == "core":
                continue

            lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines()

            for lineno, line in enumerate(lines, start=1):
                # Skip comment lines (both full-line and inline comments are handled
                # by checking the stripped form; full-line comments are the risk)
                if line.lstrip().startswith("#"):
                    continue

                for key in SECRET_KEYS:
                    # Match os.environ.get("KEY") or os.environ["KEY"] (double quotes)
                    # and os.environ.get('KEY') or os.environ['KEY'] (single quotes)
                    pattern_dq_get = f'os.environ.get("{key}"'
                    pattern_dq_sub = f'os.environ["{key}"]'
                    pattern_sq_get = f"os.environ.get('{key}'"
                    pattern_sq_sub = f"os.environ['{key}']"

                    if any(p in line for p in (
                        pattern_dq_get, pattern_dq_sub,
                        pattern_sq_get, pattern_sq_sub,
                    )):
                        # Exception 2: core/config_schema.py SmsConfig validator
                        # is allowed ONLY for TWILIO_* keys (startup presence gate).
                        if (
                            py_file.name == "config_schema.py"
                            and py_file.parent.name == "core"
                            and key in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM")
                        ):
                            continue

                        violations.append(
                            f"{rel}:{lineno}: os.environ read of {key!r} -- "
                            f"use get_store().get({key!r}) instead"
                        )

    # Companion assertion: prove core/cli/ is covered (recursion guard).
    # If this fails, the scan reverted to non-recursive glob and core/cli/*.py are invisible.
    scanned_rels = {f.relative_to(repo_root) for f in scanned_files}
    assert Path("core/cli/config_cmd.py") in scanned_rels, (
        "SC1 coverage gap: core/cli/config_cmd.py not in scanned set -- "
        "rglob must recurse into core/cli/"
    )

    assert not violations, (
        "SC1 FAIL -- os.environ secret reads found in consumer code:\n"
        + "\n".join(f"  {v}" for v in violations)
    )
