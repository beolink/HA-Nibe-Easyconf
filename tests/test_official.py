"""Alarm texts and value labels taken from NIBE's own documentation."""

from __future__ import annotations

import importlib

from .conftest import PACKAGE

official = importlib.import_module(f"{PACKAGE}.official")
registry = importlib.import_module(f"{PACKAGE}.registry")


# ------------------------------------------------------------------ alarms


def test_the_whole_class_a_list_is_loaded():
    assert len(official.ALARMS) == 304


def test_no_alarm_reads_as_such():
    assert official.alarm_text(0, "sv") == "Inget larm"
    assert official.alarm_text(0, "en") == "No alarm"


def test_a_known_alarm_reads_as_its_text():
    # NIBE writes an en dash before the designation; kept as it is.
    assert official.alarm_text(101, "sv") == "Givarfel \u2013BT1 utegivare"
    assert official.alarm_text(163, "en") == "Incorr. phase seq. or missing phase detected."


def test_a_reused_code_carries_every_meaning():
    """NIBE lists 237 three times; the last one alone would be wrong two
    times out of three."""
    text = official.alarm_text(237, "sv")
    assert "vv/värme" in text
    assert "kompressor" in text
    assert "kyla" in text


def test_identical_variants_are_not_repeated():
    # 242's three rows differ in English but share one Swedish text.
    assert official.alarm_text(242, "sv") == "Best. komm. fel FLM"
    assert official.alarm_text(242, "en").count(" / ") == 2


def test_an_unlisted_alarm_still_says_it_is_one():
    assert official.alarm_text(9999, "sv") == "Larm 9999"
    assert official.alarm_text(9999, "en") == "Alarm 9999"


def test_no_reading_is_no_text():
    assert official.alarm_text(None) is None


def test_only_alarm_number_registers_are_translated():
    assert official.is_alarm_register("Alarm number")
    assert official.is_alarm_register("Alarm number (EB100-EP14)")
    # The inverter has its own code list, and "Class 1 alarm" is a flag.
    assert not official.is_alarm_register("Inverter alarm code")
    assert not official.is_alarm_register("Class 1 alarm")
    assert not official.is_alarm_register("Alarm action, lower room temperature")


# ------------------------------------------------------------------ labels


def test_the_diverter_valve_says_what_it_does():
    """The library calls it off/on; NIBE's table says heating/hot water."""
    assert official.labels_for(32197, "sv") == {"0": "Värme", "1": "Varmvatten"}
    assert official.labels_for(32197, "en") == {"0": "Heating", "1": "Hot water"}


def test_capitalising_keeps_designations_intact():
    labels = official.labels_for(40217, "en")
    assert labels["22"] == "EB102-QN10"  # not "Eb102-qn10"


def test_registers_without_a_table_have_no_labels():
    assert official.labels_for(30002) is None


def test_nibes_table_reaches_the_register_map():
    """A setting the library leaves as a bare number gains its value table,
    which is what turns it into a dropdown."""
    brine_pump_mode = registry.union_map()[40097]
    assert brine_pump_mode["mappings"] == {
        "10": "Intermittent", "20": "Continuous", "30": "10 days continuous",
    }


def test_nibes_table_wins_over_the_librarys():
    assert registry.union_map()[32197]["mappings"] == {"0": "Heating", "1": "Hot water"}
