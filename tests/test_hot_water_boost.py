"""The hot water boost: which register and values the switch writes."""

from __future__ import annotations

import importlib
from importlib.resources import files
import json

import pytest

from .conftest import PACKAGE

hot_water_boost = importlib.import_module(f"{PACKAGE}.hot_water_boost")
BOOST = hot_water_boost.Boost(48132, 4, 0)
registry = importlib.import_module(f"{PACKAGE}.registry")


def _map(data_file: str) -> dict[int, dict]:
    raw = (files("nibe.data") / f"{data_file}.json").read_text()
    return {int(key): value for key, value in json.loads(raw).items()}


F1255_MAP = _map("f1155_f1255")


def test_the_f1255_boosts_with_a_one_time_increase():
    # What myUplink's "Tillfällig lyx" switch was seen writing on the F1255-16.
    assert hot_water_boost.boost_register(F1255_MAP, F1255_MAP) == BOOST


@pytest.mark.parametrize(
    "data_file",
    ["f1145_f1245", "f1345", "f1355", "f370_f470", "f730", "f750", "smo20", "smo40",
     "vvm225_vvm320_vvm325", "vvm310_vvm500"],
)
def test_every_f_series_map_has_the_same_boost(data_file):
    registers = _map(data_file)
    assert hot_water_boost.boost_register(registers, registers) == BOOST


def test_the_s_series_gets_no_boost_switch():
    union = registry.union_map()
    assert hot_water_boost.boost_register(union, union) is None


def test_a_pump_without_the_register_gets_no_boost_switch():
    assert hot_water_boost.boost_register(F1255_MAP, set(F1255_MAP) - {48132}) is None
