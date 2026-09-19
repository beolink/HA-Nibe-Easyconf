"""The electricity meter the F-series does not have.

The pump reports power, not energy. These check that adding it up gives the
kilowatt hours a meter would have shown, that the circulation pumps are counted
from NIBE's own figures for the size of pump, and that the two things a
coefficient of performance divides start from the same moment.
"""

from __future__ import annotations

import asyncio
import importlib

import pytest

from .conftest import PACKAGE

fseries = importlib.import_module(f"{PACKAGE}.fseries")
power = importlib.import_module(f"{PACKAGE}.power")


class FakeStore:
    """A Store that keeps what it was given, in memory."""

    def __init__(self, data=None):
        self.data = data

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.data = data


def test_a_pump_that_stands_still_draws_nothing():
    brine, medium = fseries.circulation_pumps("16")
    assert fseries.pump_watts(brine, 0) == 0
    assert fseries.pump_watts(brine, None) == 0
    assert fseries.pump_watts(medium, 0) == 0


def test_the_pumps_follow_nibes_own_figures_for_the_size():
    """NIBE gives each size its own pair of watt figures, and a smaller pump
    has smaller circulation pumps: an F1255-6 draws 87 W at most on the brine
    side where the 16 kW draws 180 W."""
    small_brine, small_medium = fseries.circulation_pumps(6)
    big_brine, big_medium = fseries.circulation_pumps(16)
    assert fseries.pump_watts(small_brine, 100) == 87
    assert fseries.pump_watts(big_brine, 100) == 180
    assert fseries.pump_watts(small_medium, 100) < fseries.pump_watts(big_medium, 100)
    # Power follows the cube of the speed, so half speed is far less than half
    # the power: the 16 kW brine pump draws 40 W of its 180 at 50 %.
    assert fseries.pump_watts(big_brine, 50) == pytest.approx(40.0)


def test_the_size_is_taken_from_whatever_names_it():
    """The development unit's serial does not resolve to a size; its product
    message reads "F1255-16 CU", and that is where the 16 comes from."""
    assert fseries.pump_size(None, "F1255-16 CU") == 16
    assert fseries.pump_size(None, "NIBE F1155-6") == 6
    assert fseries.pump_size("12") == 12
    assert fseries.pump_size(None, None) is None
    assert fseries.circulation_pumps(None, "F1255-16 CU") == fseries.CIRCULATION_PUMPS[16]


def test_a_size_nothing_named_gets_the_middle_one():
    assert fseries.circulation_pumps(None) == fseries.CIRCULATION_PUMPS[12]
    assert fseries.circulation_pumps("CU") == fseries.CIRCULATION_PUMPS[12]
    # A size NIBE does not list is served by the nearest one it does.
    assert fseries.circulation_pumps(14) == fseries.CIRCULATION_PUMPS[12]


def test_an_hour_at_a_kilowatt_is_a_kilowatt_hour():
    counter = power.ElectricityCounter(FakeStore())
    counter.sample({"compressor": 1000.0}, now=0)
    counter.sample({"compressor": 1000.0}, now=600)
    assert counter.kwh == pytest.approx(1000 * 600 / 3_600_000)
    # Six ten-minute steps make the hour.
    for step in range(2, 7):
        counter.sample({"compressor": 1000.0}, now=600 * step)
    assert counter.kwh == pytest.approx(1.0)


def test_a_gap_longer_than_a_cycle_or_two_is_not_drawn_as_a_line():
    """Between readings a few minutes apart the power is a straight line. Over
    a quarter of an hour it is guesswork, and the lower reading is what the
    pump certainly drew."""
    counter = power.ElectricityCounter(FakeStore())
    counter.sample({"compressor": 0.0}, now=0)
    counter.sample({"compressor": 3000.0}, now=power.MAX_TRAPEZOID_S + 60)
    assert counter.kwh == 0


def test_power_between_two_readings_is_taken_as_a_straight_line():
    """The compressor ramps; a reading is a point on the way, not a step."""
    counter = power.ElectricityCounter(FakeStore())
    counter.sample({"compressor": 0.0}, now=0)
    counter.sample({"compressor": 2000.0}, now=600)
    # The average of nothing and two kilowatts, over ten minutes.
    assert counter.kwh == pytest.approx(1000 * 600 / 3_600_000)


def test_the_parts_are_kept_apart():
    counter = power.ElectricityCounter(FakeStore())
    watts = {"compressor": 3000.0, "addition": 1000.0, "pumps": 60.0, "electronics": 15.0}
    counter.sample(watts, now=0)
    counter.sample(watts, now=3600)
    assert counter.parts.compressor == pytest.approx(3.0)
    assert counter.parts.addition == pytest.approx(1.0)
    assert counter.parts.pumps == pytest.approx(0.06)
    assert counter.parts.electronics == pytest.approx(0.015)
    assert counter.kwh == pytest.approx(4.075)


def test_an_unwatched_gap_counts_at_the_lower_reading():
    """Home Assistant was down for half an hour. A straight line between a
    stopped pump and one at full power would invent fifteen minutes of
    compressor; what is certain is that it drew at least the lower of the two.
    """
    counter = power.ElectricityCounter(FakeStore())
    counter.sample({"compressor": 0.0, "electronics": 15.0}, now=0)
    counter.sample({"compressor": 3000.0, "electronics": 15.0}, now=1800)
    assert counter.parts.compressor == 0
    assert counter.parts.electronics == pytest.approx(15 * 1800 / 3_600_000)


def test_a_gap_nobody_watched_at_all_counts_as_nothing():
    counter = power.ElectricityCounter(FakeStore())
    counter.sample({"compressor": 3000.0}, now=0)
    counter.sample({"compressor": 3000.0}, now=power.MAX_GAP_S + 60)
    assert counter.kwh == 0


def test_a_clock_that_went_backwards_starts_a_new_line():
    counter = power.ElectricityCounter(FakeStore())
    counter.sample({"compressor": 1000.0}, now=1000)
    counter.sample({"compressor": 1000.0}, now=500)
    assert counter.kwh == 0
    counter.sample({"compressor": 1000.0}, now=3500)
    assert counter.kwh == pytest.approx(1000 * 3000 / 3_600_000)


def test_the_count_survives_a_restart():
    store = FakeStore()
    counter = power.ElectricityCounter(store)
    for minute in range(0, 61, 10):
        counter.sample({"compressor": 1000.0}, now=minute * 60)
    counter.produced(500.0)
    asyncio.run(counter.async_save())

    after = power.ElectricityCounter(store)
    asyncio.run(after.async_load())
    assert after.kwh == pytest.approx(1.0)
    assert after.heat_baseline == 500.0
    # And it keeps counting from where it stood, not from zero.
    after.sample({"compressor": 1000.0}, now=70 * 60)
    assert after.kwh == pytest.approx(1 + 1000 * 600 / 3_600_000)


def test_heat_is_counted_from_the_same_moment_as_the_electricity():
    """The pump's heat meters have run since it was installed and this counter
    starts today, so a coefficient of performance made of the two absolute
    figures would be nonsense. Both are measured from the first reading."""
    counter = power.ElectricityCounter(FakeStore())
    assert counter.produced(897.5) == 0
    assert counter.produced(900.0) == pytest.approx(2.5)
    assert counter.produced(None) is None


def test_a_heat_meter_that_was_reset_does_not_turn_the_heat_negative():
    counter = power.ElectricityCounter(FakeStore())
    counter.produced(897.5)
    assert counter.produced(12.0) == 0  # a new controller, counting afresh
    assert counter.produced(15.0) == pytest.approx(3.0)
