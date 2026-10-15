"""The hot water boost: which register and values the switch writes."""

from __future__ import annotations

import importlib
from importlib.resources import files
import json

import pytest

from .conftest import PACKAGE

fseries = importlib.import_module(f"{PACKAGE}.fseries")
hot_water_boost = importlib.import_module(f"{PACKAGE}.hot_water_boost")
BOOST = hot_water_boost.Boost(48132, 4, 0, "one_time")
registry = importlib.import_module(f"{PACKAGE}.registry")


def _map(data_file: str) -> dict[int, dict]:
    raw = (files("nibe.data") / f"{data_file}.json").read_text()
    return {int(key): value for key, value in json.loads(raw).items()}


F1255_MAP = _map("f1155_f1255")


def test_the_f1255_boosts_with_a_one_time_increase():
    # What myUplink's "Tillfällig lyx" switch was seen writing on the F1255-16.
    assert hot_water_boost.boost_register(F1255_MAP, F1255_MAP) == BOOST


#: Every F-series map the installed library ships, by the name it gives it:
#: nibe 2.25 renamed f370_f470 to f370_f372_f470 when it added the F372.
F_SERIES_MAPS = sorted({model.data_file for model in fseries.F_SERIES_MODELS.values()})


def test_the_f_series_maps_are_all_there():
    assert len(F_SERIES_MAPS) >= 11
    assert "f1155_f1255" in F_SERIES_MAPS


@pytest.mark.parametrize("data_file", F_SERIES_MAPS)
def test_every_f_series_map_has_the_same_boost(data_file):
    registers = _map(data_file)
    assert hot_water_boost.boost_register(registers, registers) == BOOST


def test_the_s_series_boosts_with_three_hours_of_more_hot_water():
    """Measured on the S1155: 40698 is a number of hours (4 set the minutes
    register to 240, 1 to 60), and 0 ends it at once."""
    union = registry.union_map()
    assert hot_water_boost.boost_register(union, union) == hot_water_boost.Boost(
        40698, 3, 0, "hours"
    )


def test_the_f_series_boost_is_a_one_time_increase_by_kind():
    assert BOOST.kind == "one_time"


def test_a_pump_without_the_register_gets_no_boost_switch():
    assert hot_water_boost.boost_register(F1255_MAP, set(F1255_MAP) - {48132}) is None
