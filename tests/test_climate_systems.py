"""Which registers the thermostat and the water heater are made of, on each series."""

from __future__ import annotations

import importlib
from importlib.resources import files
import json

import pytest

from .conftest import PACKAGE

climate_systems = importlib.import_module(f"{PACKAGE}.climate_systems")
registry = importlib.import_module(f"{PACKAGE}.registry")


def _map(data_file: str) -> dict[int, dict]:
    raw = (files("nibe.data") / f"{data_file}.json").read_text()
    return {int(key): value for key, value in json.loads(raw).items()}


F1255 = _map("f1155_f1255")
S_SERIES = registry.union_map()


def test_the_f1255_has_four_climate_systems_at_the_librarys_addresses():
    """The same registers nibe's coil_groups.py names for the F-series."""
    systems = climate_systems.climate_systems(F1255, F1255)
    assert [system.number for system in systems] == [1, 2, 3, 4]
    first = systems[0]
    assert (first.current, first.setpoint, first.cool_setpoint) == (40033, 47398, 48785)
    assert (first.use_room_sensor, first.mixing_valve) == (47394, 43096)
    second = systems[1]
    assert (second.current, second.setpoint, second.use_room_sensor) == (40032, 47397, 47393)


def test_the_s_series_regulates_on_the_room_average():
    """The S1155 answers both the average and Roomsensor 1-1 with the same
    reading; the average is the one the pump regulates on."""
    systems = climate_systems.climate_systems(S_SERIES, S_SERIES)
    first = systems[0]
    assert (first.current, first.setpoint, first.cool_setpoint) == (30117, 40207, 40989)
    assert (first.use_room_sensor, first.mixing_valve) == (40203, 31034)


def test_the_s_series_keeps_a_setpoint_per_zone_beside_the_climate_systems():
    """Independent registers on the S1155: writing one leaves the other. The
    thermostat writes both, so either reading is what it shows."""
    systems = climate_systems.climate_systems(S_SERIES, S_SERIES)
    assert systems[0].zone_setpoint == 42506
    assert systems[1].zone_setpoint == 42508
    f_series = climate_systems.climate_systems(F1255, F1255)
    assert all(system.zone_setpoint is None for system in f_series)


def test_a_pump_that_never_answered_the_average_falls_back_to_the_first_sensor():
    present = set(S_SERIES) - {30117}
    first = climate_systems.climate_systems(S_SERIES, present)[0]
    assert first.current == 30027


def test_a_system_without_a_setpoint_is_not_a_thermostat():
    present = set(F1255) - {47398}
    numbers = [s.number for s in climate_systems.climate_systems(F1255, present)]
    assert numbers == [2, 3, 4]


def test_a_system_without_a_room_sensor_still_has_a_thermostat():
    """The F1255 at the second site: 40033 exists and answers nothing. The
    thermostat is still there, steering the heat curve."""
    present = set(F1255) - {40033}
    first = climate_systems.climate_systems(F1255, present)[0]
    assert first.current is None and first.setpoint == 47398


def test_the_unit_registers_are_the_priority_and_the_cooling_switch():
    assert climate_systems.unit(F1255, F1255) == climate_systems.Unit(43086, 47340)
    # Two S-series registers are titled "Priority"; the lower answers in words.
    assert climate_systems.unit(S_SERIES, S_SERIES) == climate_systems.Unit(31029, 40171)


def test_the_f_series_hot_water_is_the_comfort_mode_between_bt6_and_its_temperatures():
    water = climate_systems.hot_water(F1255, F1255)
    assert (water.current, water.top, water.mode) == (40014, 40013, 47041)
    assert water.words == "hot_water"
    assert [(m.key, m.value, m.start, m.stop) for m in water.modes] == [
        ("economy", 0, 47045, 47049),
        ("normal", 1, 47044, 47048),
        ("luxury", 2, 47043, 47047),
        ("smart", 4, None, None),
    ]
    assert water.boost == climate_systems.Boost(48132, 4, 0, "one_time")


def test_the_s_series_hot_water_is_the_demand_mode_with_three_hours_as_its_boost():
    water = climate_systems.hot_water(S_SERIES, S_SERIES)
    assert (water.current, water.top, water.mode) == (30010, 30009, 40057)
    assert water.words == "hot_water_demand"
    assert [(m.key, m.value, m.start, m.stop) for m in water.modes] == [
        ("small", 0, 40061, 40065),
        ("medium", 1, 40060, 40064),
        ("large", 2, 40059, 40063),
        ("smart", 4, None, None),
    ]
    # "More hot water" is hours; see hot_water_boost.py for the measurement.
    assert water.boost == climate_systems.Boost(40698, 3, 0, "hours")


def test_a_pump_without_a_cylinder_sensor_heats_no_water():
    present = set(F1255) - {40014}
    assert climate_systems.hot_water(F1255, present) is None


#: Every F-series map the installed library ships.
fseries = importlib.import_module(f"{PACKAGE}.fseries")
F_SERIES_MAPS = sorted({model.data_file for model in fseries.F_SERIES_MODELS.values()})


@pytest.mark.parametrize("data_file", F_SERIES_MAPS)
def test_every_f_series_map_has_a_first_climate_system_and_hot_water(data_file):
    registers = _map(data_file)
    systems = climate_systems.climate_systems(registers, registers)
    assert systems and systems[0].number == 1
    assert systems[0].setpoint == 47398
    water = climate_systems.hot_water(registers, registers)
    assert water is not None and water.mode == 47041
