"""The checks that decide which of NIBE's English alarm titles can be trusted."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

pytest.importorskip("pypdf")

TOOL = Path(__file__).resolve().parents[1] / "tools" / "extract_nibe_alarms_fseries.py"
spec = importlib.util.spec_from_file_location("extract_alarms_fseries_under_test", TOOL)
tool = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tool
spec.loader.exec_module(tool)


@pytest.mark.parametrize(
    ("swedish", "english"),
    [
        ("Högtryckslarm", "High pressure alarm"),
        ("Givarfel: BT10 köldbärare in", "Sensor fault: BT10"),
        ("Komm. fel värmesystem2", "Com. error heating system 2"),
        ("Inverter fel typ III", "Inverter error type III"),
        ("Best. Komm. Rumsenhet, zon 3", "Perm. Com. room unit, zone 3"),
        ("Kall uteluft EB 101", "Cold outdoor air EB 101"),
    ],
)
def test_titles_that_name_the_same_alarm_agree(swedish, english):
    assert tool.agrees(swedish, english)


@pytest.mark.parametrize(
    ("swedish", "english"),
    [
        ("Tillfälligt HP larm", "High condensor out"),  # 150, renumbered by NIBE
        ("Givarfel EP30-BT54", "Sensor fault EP30-BT53"),  # 34
        ("Inverterlarm typ II", "Inverter alarm type III"),  # 428
        ("Komm.fel slav 5", "Com. error slave 6"),
        ("Fasspänning till Invertern har tillfälligt varit för låg.", "Inverter alarm type I"),
    ],
)
def test_titles_that_name_different_alarms_do_not(swedish, english):
    assert not tool.agrees(swedish, english)


@pytest.mark.parametrize(
    ("raw", "tidy"),
    [
        ("Short operation times for com- pressor", "Short operation times for compressor"),
        (
            "VV-start och VV-stopp har fabriksåter - ställts",
            "VV-start och VV-stopp har fabriksåterställts",
        ),
        ("Fram/ returledning", "Fram / returledning"),
        ("Givarfel BT74 kyla- / värmegivare", "Givarfel BT74 kyla-/värmegivare"),
        ("Startar/ 998", "Startar / 998"),
    ],
)
def test_what_line_breaks_leave_behind_is_tidied(raw, tidy):
    assert tool.tidy(raw) == tidy


def test_the_plain_text_decides_the_spacing():
    page = tool.Page("58 Pressostatlarm Högtrycks- eller lågtryckspressostaten\n60 Låg KB ut Temp")
    assert page.respace("L åg K B ut") == "Låg KB ut"
    assert page.respace("Nothing like it") == "Nothing like it"
