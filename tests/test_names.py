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


def _assign(registers, language="sv"):
    return names.assign_names(registers, set(registers), language, descriptions.friendly_name)


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
    assert assigned[40096] == "VB-pump, läge (ställ)"
    # Marking the setting is enough; the reading keeps its plain name rather
    # than also picking up a register number.
    assert assigned[31097] == "VB-pump, läge"


def test_the_register_number_is_the_last_resort():
    """Nothing tells these two apart - same title, both readings, no
    designation - so the number is all that is left."""
    registers = {40200: _meta("Permit"), 40201: _meta("Permit")}
    assigned = _assign(registers)
    assert assigned[40200] != assigned[40201]
    assert "40201" in assigned[40201]


def test_the_register_that_answers_in_words_is_the_status():
    """NIBE titles two S-series registers "Priority". One answers off, hot
    water, heat, pool or cooling - what the pump is doing - and is named for
    that; the other is a bare number and keeps the title's own name, with no
    register number to tell it from the first."""
    registers = {31029: _meta("Priority"), 33805: _meta("Priority")}
    assigned = _assign(registers)
    assert assigned[31029] == "Status"
    assert assigned[33805] == "Prioritering"
    assert _assign(registers, "en")[31029] == "Status"
    # And it keeps the plain name even when an accessory reports a status of
    # its own: the name was chosen for this register knowing the others, so
    # the disambiguation belongs to them.
    with_accessory = {**registers, 30341: _meta("Status (EQ1)")}
    assigned = _assign(with_accessory)
    assert assigned[31029] == "Status"
    assert assigned[30341] == "Status (EQ1)"
    # The F-series spells the same thing "Prio".
    assert _assign({43086: _meta("Prio")})[43086] == "Status"


def test_unique_names_stay_untouched():
    registers = {30002: _meta("Current outdoor temperature (BT1)")}
    assert _assign(registers)[30002] == "Utetemperatur"
