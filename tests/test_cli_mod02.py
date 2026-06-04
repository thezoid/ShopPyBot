"""MOD-02 test: no core/cli/ module may directly import forbidden model/orchestrator names.

This test is active (not skip-marked) -- the stub modules created in plan 09-01
must not import forbidden names, so this guard passes immediately and stays green.
"""

import ast
from pathlib import Path


def test_cli_no_direct_model_imports():
    """No cli/ module may import orchestrator/registry/models or low-level sync functions.

    Follows the AST-scan pattern from test_no_env_secret_reads.py.
    Forbidden names: orchestrator, registry, models, add_items_sync,
    get_items_sync, remove_item_sync, add_items.
    """
    forbidden_names = {
        "orchestrator",
        "registry",
        "models",
        "add_items_sync",
        "get_items_sync",
        "remove_item_sync",
        "add_items",
    }
    cli_dir = Path(__file__).parent.parent / "core" / "cli"
    violations: list[str] = []
    for py_file in sorted(cli_dir.glob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden_names:
                        violations.append(
                            f"{py_file.name}: imports {alias.name!r}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module in forbidden_names or (
                    node.names
                    and any(a.name in forbidden_names for a in node.names)
                ):
                    violations.append(
                        f"{py_file.name}: from-imports forbidden name "
                        f"(module={node.module!r})"
                    )
    assert not violations, "\n".join(violations)
