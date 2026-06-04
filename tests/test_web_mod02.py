"""MOD-02 test: no web/ module may directly import forbidden model/orchestrator names.

All UI actions must route through BotService — never models.py/orchestrator/registry
directly (GUI-01 contract). Uses rglob to cover web/routes/ subdirectory.
"""
import pytest
pytest.importorskip("fastapi")

import ast
from pathlib import Path


def test_web_no_direct_model_imports():
    """No web/ module may import orchestrator/registry/models or low-level sync functions.

    Extends the AST-scan pattern from test_cli_mod02.py to cover the web/ package
    including all subdirectories (rglob covers web/routes/).
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
    web_dir = Path(__file__).parent.parent / "web"
    violations: list[str] = []
    for py_file in sorted(web_dir.rglob("*.py")):
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
