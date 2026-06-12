"""AST CI guard: no `for attempt in range(` loop exists outside core/retry.py.

REL-08 criterion: core/retry.py is the single home for exponential backoff.
Any `for attempt in range(` pattern outside that file is a policy violation
that risks unsynchronised backoff compounding with the Phase 22 supervisor.

Scan scope: all .py files under core/ and plugins/ (recursively), plus
models.py and main.py at repo root. core/retry.py is the ONE allowed location
and is explicitly excluded from the scan.

Exempt by design (no whitelist needed):
  core/captcha.py -- `for _ in range(_MAX_POLLS)` -- loop variable is `_`
  core/stealth.py -- `for _ in range(len(self._entries))` -- loop variable is `_`
These poll loops use `_` as the loop variable, so the ast.Name id=="attempt"
predicate never matches them. The exemption is structural, not whitelisted.

Non-vacuous guard: asserts core/retry.py itself exists so a path drift does not
silently produce zero scan targets and a false pass.
"""
from __future__ import annotations

import ast
from pathlib import Path


def test_no_for_attempt_in_range_outside_retry():
    """No `for attempt in range(` loop exists outside core/retry.py.

    Walks AST for ast.For nodes where:
      - node.target is ast.Name with id == "attempt"
      - node.iter is ast.Call whose function resolves to the name "range"
    Any match outside core/retry.py is a violation (REL-08).
    """
    repo_root = Path(__file__).parent.parent
    retry_module = repo_root / "core" / "retry.py"

    # Non-vacuous guard: if retry.py itself is missing the scan has no anchor.
    assert retry_module.is_file(), (
        f"core/retry.py not found at {retry_module} -- "
        "cannot enforce REL-08 without the canonical retry module"
    )

    scan_dirs = [repo_root / "core", repo_root / "plugins"]
    scan_files_direct = [repo_root / "models.py", repo_root / "main.py"]

    # Collect all .py files from scan dirs (recursive) + direct files.
    all_files: list[Path] = []
    for d in scan_dirs:
        if d.is_dir():
            all_files.extend(d.rglob("*.py"))
    for f in scan_files_direct:
        if f.is_file():
            all_files.append(f)

    # Exclude core/retry.py -- the one permitted location.
    scan_targets = [p for p in all_files if p.resolve() != retry_module.resolve()]

    violations: list[str] = []

    for path in scan_targets:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))

        for node in ast.walk(tree):
            if not isinstance(node, ast.For):
                continue
            # Target variable must be exactly "attempt" (not "_").
            if not isinstance(node.target, ast.Name):
                continue
            if node.target.id != "attempt":
                continue
            # Iter must be a call to `range`.
            if not isinstance(node.iter, ast.Call):
                continue
            func = node.iter.func
            if isinstance(func, ast.Name):
                fname = func.id
            elif isinstance(func, ast.Attribute):
                fname = func.attr
            else:
                continue
            if fname == "range":
                violations.append(f"{path.name}:{node.lineno}")

    assert not violations, (
        "`for attempt in range(` is forbidden outside core/retry.py (REL-08). "
        "Use core.retry.with_retry() instead. Violations: " + str(violations)
    )
