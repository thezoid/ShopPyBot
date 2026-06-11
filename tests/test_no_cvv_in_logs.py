"""AST CI assertion: no _cvv variable appears in any writeLog() argument on checkout paths.

BUY-07 criterion 3 (T-20-07): the runtime CVV must never reach logs or disk.
Scans plugins/shopbot_plugin_bestbuy.py, plugins/shopbot_plugin_amazon.py,
core/checkout_profile.py, core/orchestrator.py, and core/cli/run.py via ast.walk;
fails with a per-violation list if any writeLog() Call node has a positional argument
or keyword argument value whose source text contains '_cvv'.

Scope: plugin checkout path + orchestration path.
Companion test test_cvv_threading.py covers writeLog/print in orchestration+CLI files
with the same keyword-complete scan.

Non-vacuous guard: asserts each target file exists before scanning so an accidental
path typo cannot silently produce zero violations and a false pass.
"""

import ast
from pathlib import Path


def test_cvv_not_in_writelog_args():
    """No writeLog() call in checkout/orchestration code has _cvv in any argument.

    Checks both positional args (node.args) and keyword arg values (node.keywords)
    so that writeLog(msg=f"{self._cvv}") is also caught (CR-02 / WR-03).
    """
    repo_root = Path(__file__).parent.parent
    checkout_files = [
        repo_root / "plugins" / "shopbot_plugin_bestbuy.py",
        repo_root / "plugins" / "shopbot_plugin_amazon.py",
        repo_root / "core" / "checkout_profile.py",
        repo_root / "core" / "orchestrator.py",
        repo_root / "core" / "cli" / "run.py",
    ]

    # Non-vacuous file-existence guard: a typo here must be a hard error, not a
    # silent empty scan (mirrors companion assertion in test_no_env_secret_reads.py).
    for path in checkout_files:
        assert path.is_file(), (
            f"CVV log scan target not found: {path} -- check for path drift"
        )

    violations: list[str] = []

    for path in checkout_files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            func = node.func
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            else:
                continue

            if name != "writeLog":
                continue

            # Positional args
            for arg in node.args:
                arg_src = ast.unparse(arg)
                if "_cvv" in arg_src:
                    violations.append(
                        f"{path.name}:{node.lineno}: writeLog arg contains '_cvv': {arg_src!r}"
                    )

            # Keyword arg values (e.g., writeLog(msg=f"{self._cvv}", type="INFO"))
            for kw in node.keywords:
                kw_src = ast.unparse(kw.value)
                if "_cvv" in kw_src and not isinstance(kw.value, ast.Constant):
                    violations.append(
                        f"{path.name}:{node.lineno}: writeLog kwarg contains '_cvv': {kw_src!r}"
                    )

    assert not violations, (
        "CVV variable found in writeLog() argument -- SEC-02 violation:\n"
        + "\n".join(violations)
    )
