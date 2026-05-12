import pathlib


def test_requires_python_declared():
    text = pathlib.Path("pyproject.toml").read_text()
    assert 'requires-python = ">=3.11"' in text, "pyproject.toml must declare requires-python >= 3.11"
