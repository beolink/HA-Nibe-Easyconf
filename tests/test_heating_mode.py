"""The heating mode: which offset each mode writes, and how a change by hand is taken."""

from __future__ import annotations

import importlib
from importlib.resources import files
import json

import pytest

from .conftest import PACKAGE

heating_mode = importlib.import_module(f"{PACKAGE}.heating_mode")
registry = importlib.import_module(f"{PACKAGE}.registry")

F1255_MAP = {
    int(key): value
    for key, value in json.loads((files("nibe.data") / "f1155_f1255.json").read_text()).items()
}

DEFAULTS = heating_mode.steps_from({})


def test_the_options_are_the_ids_ems_writes():
    # EMS Steward's load contract: a bound select offers exactly these.
    assert heating_mode.MODES == ("blocked", "eco", "normal", "boost")


def test_the_f_series_steers_heat_offset_s1():
    assert heating_mode.offset_register(F1255_MAP, F1255_MAP) == 47011


def test_the_s_series_steers_the_offset_of_climate_system_1():
    union = registry.union_map()
    assert heating_mode.offset_register(union, union) == 40031


def test_no_offset_among_what_the_pump_answered_means_no_heating_mode():
    present = set(F1255_MAP) - {47011}
    assert heating_mode.offset_register(F1255_MAP, present) is None


def test_the_default_steps_mirror_ems_thermostat_set_backs():
    assert DEFAULTS == {"blocked": -3, "eco": -1, "normal": 0, "boost": 1}


def test_steps_come_from_the_options_where_set():
    steps = heating_mode.steps_from({"heating_mode_eco": -2.0, "scan_interval": 60})
    assert steps == {"blocked": -3, "eco": -2, "normal": 0, "boost": 1}


@pytest.mark.parametrize(
    ("mode", "normal", "offset"),
    [
        ("blocked", 0, -3),
        ("eco", 0, -1),
        ("normal", 0, 0),
        ("boost", 0, 1),
        ("eco", 2, 1),
        ("blocked", -9, -10),  # kept inside the register's range
        ("boost", 10, 10),
    ],
)
def test_a_mode_writes_steps_from_normal(mode, normal, offset):
    assert heating_mode.offset_for(mode, normal, DEFAULTS, -10, 10) == offset


def test_the_first_offset_seen_is_normal():
    assert heating_mode.learn(-2) == heating_mode.ModeState("normal", -2, -2)


def test_an_unchanged_offset_changes_nothing():
    state = heating_mode.ModeState("eco", 0, -1)
    assert heating_mode.follow(state, -1) is state


def test_a_change_by_hand_in_normal_is_the_new_normal():
    state = heating_mode.ModeState("normal", 0, 0)
    assert heating_mode.follow(state, 1) == heating_mode.ModeState("normal", 1, 1)


def test_a_change_by_hand_in_another_mode_leaves_normal_alone():
    state = heating_mode.ModeState("blocked", 0, -3)
    assert heating_mode.follow(state, -2) == heating_mode.ModeState("blocked", 0, -2)


def test_choosing_normal_takes_what_the_pump_stored_as_normal():
    state = heating_mode.ModeState("eco", 0, -1)
    assert heating_mode.chosen(state, "normal", 0) == heating_mode.ModeState("normal", 0, 0)
    assert heating_mode.chosen(state, "boost", 1) == heating_mode.ModeState("boost", 0, 1)
