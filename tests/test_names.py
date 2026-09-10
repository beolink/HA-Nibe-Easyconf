"""Entity names: short enough to read, and never two alike."""

from __future__ import annotations

import importlib

from .conftest import PACKAGE

names = importlib.import_module(f"{PACKAGE}.names")
descriptions = importlib.import_module(f"{PACKAGE}.descriptions")


def test_every_curated_name_fits_a_column():
    for title, pair in names.SHORT_NAMES.items():
        for name in pair:
            assert len(name) <= names.MAX_LENGTH, f"{title!r} -> {name!r}"


def test_the_worst_title_gets_a_short_name():
    title = "Energy log - Used energy by additional heater for hot water over the past hour"
    assert len(title) == 78
    assert names.short_name(title) == "Elpatron, VV, 1 h"
    assert names.short_name(title, "en") == "Immersion, HW, 1 h"


def test_unlisted_titles_have_no_short_name():
    assert names.short_name("Floor drying temp. 6") is None


def _meta(title, write=False):
    return {"title": title, "write": write}


def _assign(registers):
    return names.assign_names(registers, set(registers), "sv", descriptions.friendly_name)


def test_identical_titles_get_distinct_names():
    """NIBE reuses titles: 21 registers on one pump are titled just "Permit"."""
    registers = {40000 + i: _meta("Permit") for i in range(1, 22)}
    assigned = _assign(registers)
    assert len(set(assigned.values())) == 21


def test_a_distinguishing_designation_is_preferred():
    registers = {
        31692: _meta("Compressor status (EB100-EP15)"),
        31693: _meta("Compressor status (EB100-EP14)"),
        31101: _meta("Compressor status"),
    }
    assigned = _assign(registers)
    assert len(set(assigned.values())) == 3


def test_a_setting_is_told_apart_from_its_reading():
    """The pump exposes several things twice: once to read, once to set."""
    registers = {
        31097: _meta("Operating mode heating medium pump"),
        40096: _meta("Operating mode heating medium pump", write=True),
    }
    assigned = _assign(registers)
    assert assigned[40096] == "VB-pump, driftläge, inställning"
    # Marking the setting is enough; the reading keeps its plain name rather
    # than also picking up a register number.
    assert assigned[31097] == "VB-pump, driftläge"


def test_the_register_number_is_the_last_resort():
    registers = {31029: _meta("Priority"), 33805: _meta("Priority")}
    assigned = _assign(registers)
    assert assigned[31029] != assigned[33805]
    assert "33805" in assigned[33805]


def test_unique_names_stay_untouched():
    registers = {30002: _meta("Current outdoor temperature (BT1)")}
    assert _assign(registers)[30002] == "Utetemperatur"
