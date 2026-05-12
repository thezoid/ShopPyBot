import pathlib
import re


def test_every_line_has_exact_pin():
    lines = [l for l in pathlib.Path("requirements.txt").read_text().splitlines() if l.strip()]
    pin_re = re.compile(r"^[a-zA-Z0-9_.\-]+(\[[a-zA-Z0-9_,\-]+\])?==\d+\.\d+\.\d+$")
    for line in lines:
        assert pin_re.match(line), f"unpinned or malformed: {line!r}"


def test_no_duplicate_packages():
    lines = [l for l in pathlib.Path("requirements.txt").read_text().splitlines() if l.strip()]
    names = [re.split(r"[=\[]", l)[0].lower().replace("_", "-") for l in lines]
    assert len(names) == len(set(names)), f"duplicates present: {names}"
