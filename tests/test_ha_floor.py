"""hacs.json promises a Home Assistant the code actually runs on (roadmap R56 in
HA-CTC-Local-Easyconf, which shares the fault this fixes).

The floor was found by trying, not by reading: every Home Assistant import the
source spells run as it is written, inside functions too, every attribute of a
Home Assistant module the source reaches for looked up, and the calls reached
that way held to their real signatures, under Home Assistant 2024.12.0,
2024.12.5, 2025.1.0, 2025.1.4, 2025.2.0, 2026.4.0, 2026.5.0, 2026.9.4 and
2026.10.1. One thing sets it: config_flow.py imports DhcpServiceInfo and
ZeroconfServiceInfo from homeassistant.helpers.service_info, whose dhcp and
zeroconf modules Home Assistant 2025.2 brought. Before it the config flow does
not import and nothing can be set up.

So the floor is 2025.2.0, the highest need in NEEDS. Each need is found by its
name in the package's syntax tree, not by a piece of text, so a rewrite that
spells it another way (imported by module, kept in a variable, moved to another
file) still finds it. Lowering hacs.json below a need fails here, and so does a
need that is no longer found: it comes out of NEEDS only once the source has
been tried under the release before it and no longer uses it, never because the
floor would then go down by itself. Code that starts using something newer than
the floor adds its line here.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re

import pytest

from .conftest import SOURCE

ROOT = Path(__file__).resolve().parents[1]

#: (the Home Assistant module or name the source uses, the first release that has it)
NEEDS = (
    ("homeassistant.helpers.service_info.dhcp", "2025.2.0"),
    ("homeassistant.helpers.service_info.zeroconf", "2025.2.0"),
)


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def _hacs() -> dict:
    return json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))


def _within(dotted: str, need: str) -> bool:
    return dotted == need or dotted.startswith(f"{need}.")


def _lines_using(source: str, need: str) -> list[int]:
    """The lines where the source reaches a Home Assistant module or name.

    Through an import of it or of something in it (from M import n, from M.n
    import x, import M.n), or through an attribute chain that starts at a name
    an import bound (service_info.dhcp.DhcpServiceInfo, also when kept in a
    variable). A comment, a string or getattr with a name in quotes is not a use.
    """
    tree = ast.parse(source)
    bound: dict[str, str] = {}
    lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            for alias in node.names:
                full = f"{node.module}.{alias.name}"
                bound[alias.asname or alias.name] = full
                if _within(full, need) or _within(node.module, need):
                    lines.append(node.lineno)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.partition(".")[0]
                bound[alias.asname or top] = alias.name if alias.asname else top
                if _within(alias.name, need):
                    lines.append(node.lineno)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        parts = []
        root: ast.expr = node
        while isinstance(root, ast.Attribute):
            parts.append(root.attr)
            root = root.value
        if (
            isinstance(root, ast.Name)
            and root.id in bound
            and _within(".".join([bound[root.id], *reversed(parts)]), need)
        ):
            lines.append(node.lineno)
    return sorted(set(lines))


def _uses(need: str) -> list[str]:
    """Where in the package the need is used, as file:line."""
    return [
        f"{path.relative_to(SOURCE).as_posix()}:{line}"
        for path in sorted(SOURCE.rglob("*.py"))
        for line in _lines_using(path.read_text(encoding="utf-8"), need)
    ]


def test_the_floor_is_a_first_release_of_a_month():
    assert re.fullmatch(r"20\d\d\.(?:[1-9]|1[0-2])\.0", _hacs()["homeassistant"])


@pytest.mark.parametrize(("need", "release"), NEEDS)
def test_every_need_is_still_used_by_the_source(need, release):
    assert _uses(need), (
        f"{need} ({release}) is no longer found in the source. Confirm under the "
        f"Home Assistant release before {release} that the need is gone, then take "
        "its line out of NEEDS."
    )


@pytest.mark.parametrize(("need", "release"), NEEDS)
def test_the_floor_is_no_lower_than_what_the_source_uses(need, release):
    floor = _hacs()["homeassistant"]
    assert _version(floor) >= _version(release), (
        f"{', '.join(_uses(need))} uses {need}, which came in {release}, "
        f"but hacs.json promises {floor}"
    )


def test_the_floor_is_the_highest_need_and_not_above_it():
    floor = _hacs()["homeassistant"]
    highest = max(NEEDS, key=lambda need: _version(need[1]))
    assert _version(floor) <= _version(highest[1]), (
        f"hacs.json promises {floor}, but the highest need in NEEDS is {highest[0]} "
        f"({highest[1]}): what raised the floor belongs in NEEDS"
    )
    assert _version(floor) == _version(highest[1]), "the floor is the highest need"


@pytest.mark.parametrize(
    ("source", "need", "used"),
    [
        (
            "from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo\n",
            "homeassistant.helpers.service_info.dhcp",
            [1],
        ),
        (
            "from homeassistant.helpers.service_info import zeroconf\n",
            "homeassistant.helpers.service_info.zeroconf",
            [1],
        ),
        (
            "from homeassistant.helpers import service_info\n"
            "info = service_info.dhcp.DhcpServiceInfo\n",
            "homeassistant.helpers.service_info.dhcp",
            [2],
        ),
        (
            "def step():\n"
            "    import homeassistant.helpers.service_info.zeroconf as zc\n",
            "homeassistant.helpers.service_info.zeroconf",
            [2],
        ),
        (
            "from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo\n"
            "# from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo\n"
            "text = 'homeassistant.helpers.service_info.dhcp'\n",
            "homeassistant.helpers.service_info.dhcp",
            [],
        ),
    ],
)
def test_a_need_is_found_by_its_name_however_it_is_spelt(source, need, used):
    assert _lines_using(source, need) == used
