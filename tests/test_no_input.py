"""Static check: no input() call exists in plugins/, core/, or main.py (ASYNC-03).

Parses each Python source file via the AST and fails if any Call node invokes
the builtin `input` function. This correctly excludes occurrences inside string
literals, docstrings, and comments -- only actual call-expression nodes are counted.

This test proves the input() removal requirement is maintained going forward.
"""

import ast
from pathlib import Path


_REPO_ROOT = Path(__file__).parent.parent


def _find_input_calls(path: Path) -> list[tuple[int, str]]:
    """Return (lineno, source_line) for every bare input(...) call in the file."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError):
        return []

    lines = source.splitlines()
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Match bare `input(...)` or `builtins.input(...)`.
        is_bare = isinstance(func, ast.Name) and func.id == "input"
        is_builtin = (
            isinstance(func, ast.Attribute)
            and func.attr == "input"
            and isinstance(func.value, ast.Name)
            and func.value.id == "builtins"
        )
        if is_bare or is_builtin:
            lineno = node.lineno
            line_text = lines[lineno - 1].rstrip() if lineno <= len(lines) else ""
            hits.append((lineno, line_text))
    return hits


def _collect_violations(search_dirs: list[Path], extra_files: list[Path]) -> list[str]:
    """Return list of 'file:line: text' strings for every input() call found."""
    violations = []
    candidates = list(extra_files)
    for d in search_dirs:
        candidates.extend(d.rglob("*.py"))

    for path in candidates:
        for lineno, text in _find_input_calls(path):
            violations.append(f"{path}:{lineno}: {text}")

    return violations


def test_no_input_in_async_paths():
    """Fail if any input() call exists in plugins/, core/, or main.py (ASYNC-03)."""
    search_dirs = [
        _REPO_ROOT / "plugins",
        _REPO_ROOT / "core",
    ]
    extra_files = [_REPO_ROOT / "main.py"]

    violations = _collect_violations(search_dirs, extra_files)

    assert not violations, (
        "Found input() calls in async paths (ASYNC-03 violation):\n"
        + "\n".join(f"  {v}" for v in violations)
    )
