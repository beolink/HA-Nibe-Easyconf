"""Units, device classes and state classes from NIBE's register metadata.

Start counters have no unit in NIBE's maps. They still only ever climb, so they
are running totals, and Home Assistant keeps their long-term statistics only
when they say so.
"""

from __future__ import annotations

import importlib

import pytest

from .conftest import PACKAGE

# units.py takes its device classes from Home Assistant; the offline suite has none.
pytest.importorskip("homeassistant")

units = importlib.import_module(f"{PACKAGE}.units")


@pytest.mark.parametrize(
    "title",
    [
        "Compressor starts EB100-EP14",
        "EB101-EP14 Compressor starts",
        "Compressor, number of starts (EB101-EP14)",
        "AZ10 Number of Starts",
        "No. of starts (S135)",
    ],
)
def test_start_counters_are_running_totals(title):
    assert units.resolve({"title": title, "unit": ""}) == (None, None, units.TOTAL_INCREASING)


@pytest.mark.parametrize(
    ("title", "unit", "write"),
    [
        ("EB101-EP14 Compr. time to start", "", False),
        ("DM start heating", "", True),
        ("Temp. lux forces start of hot water demand", "", False),
        ("Compressor starter", "", False),
        ("Max number of starts per hour", "", True),
    ],
)
def test_other_unitless_registers_keep_no_state_class(title, unit, write):
    assert units.resolve({"title": title, "unit": unit, "write": write})[2] is None


def test_run_times_stay_running_totals():
    state_class = units.resolve({"title": "Compressor operating time", "unit": "h"})[2]
    assert state_class is units.TOTAL_INCREASING


@pytest.mark.parametrize(
    ("unit", "device_class"),
    [
        ("%RH", "humidity"),
        ("kPa", "pressure"),
        ("Pa", "pressure"),
        ("mA", "current"),
        ("hrs", "duration"),
        ("sec", "duration"),
    ],
)
def test_the_maps_other_spellings_of_a_unit_give_a_measurement(unit, device_class):
    """The room units' humidity, the pressure sensors BM1 and BP15/BP16, the
    compressor current in milliamperes and two timers had a unit and no state
    class, so Home Assistant kept no long-term statistics for them."""
    ha_unit, resolved_class, state_class = units.resolve({"title": "x", "unit": unit})
    assert ha_unit is not None
    assert resolved_class == device_class
    assert state_class is units.MEASUREMENT


def test_a_unit_of_one_is_no_unit():
    assert units.resolve({"title": "+Adjust AUX Port", "unit": "1"}) == (None, None, None)
