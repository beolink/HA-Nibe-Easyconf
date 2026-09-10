"""The coefficient of performance tracker, ported from the CTC integration.

These are CTC's own tracker tests, kept as they are so the port provably gives
the same answers - which is what makes the two integrations' figures
comparable in the fleet report. CTC's tests for scraping the counters off its
display are left out; here the counters are Modbus registers. The tests at the
bottom cover what is specific to this integration.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
import importlib

import pytest

from .conftest import PACKAGE

_cop = importlib.import_module(f"{PACKAGE}.cop")


@pytest.fixture
def cop():
    return _cop


class FakeStore:
    """Stands in for Home Assistant's Store, in memory."""

    def __init__(self) -> None:
        self.data = None

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.data = data


def run(coro):
    return asyncio.run(coro)


def test_lifetime_ratio_before_a_year_of_samples(cop):
    tracker = cop.CopTracker(FakeStore())
    result = tracker.result(22421, 9088, today=date(2026, 9, 9))
    assert result.basis == "lifetime"
    assert result.value == pytest.approx(2.47, abs=0.01)


def test_rolling_year_uses_the_difference(cop):
    tracker = cop.CopTracker(FakeStore())
    today = date(2026, 9, 9)
    a_year_ago = today - timedelta(days=366)
    run(tracker.async_record(18000, 7500, today=a_year_ago))
    result = tracker.result(22421, 9088, today=today)
    assert result.basis == "year"
    # 4421 kWh delivered against 1588 consumed over the year.
    assert result.value == pytest.approx(2.78, abs=0.01)
    assert result.energy_out == pytest.approx(4421, abs=1)


def test_a_sample_inside_the_window_is_not_used(cop):
    tracker = cop.CopTracker(FakeStore())
    today = date(2026, 9, 9)
    run(tracker.async_record(21000, 8600, today=today - timedelta(days=100)))
    result = tracker.result(22421, 9088, today=today)
    assert result.basis == "lifetime"


def test_counters_going_backwards_fall_back_to_lifetime(cop):
    # A replaced unit or a reset counter must not produce a negative delta.
    tracker = cop.CopTracker(FakeStore())
    today = date(2026, 9, 9)
    run(tracker.async_record(30000, 12000, today=today - timedelta(days=400)))
    result = tracker.result(22421, 9088, today=today)
    assert result.basis == "lifetime"


def test_too_little_consumption_is_not_a_measurement(cop):
    tracker = cop.CopTracker(FakeStore())
    assert tracker.result(30, 10, today=date(2026, 9, 9)).value is None


def test_missing_counters_give_nothing(cop):
    tracker = cop.CopTracker(FakeStore())
    assert tracker.result(None, 9088).value is None
    assert tracker.result(22421, None).value is None


def test_samples_older_than_the_history_are_dropped(cop):
    store = FakeStore()
    tracker = cop.CopTracker(store)
    today = date(2026, 9, 9)
    run(tracker.async_record(1000, 400, today=today - timedelta(days=500)))
    run(tracker.async_record(22421, 9088, today=today))
    assert (today - timedelta(days=500)).isoformat() not in store.data["samples"]
    assert today.isoformat() in store.data["samples"]


def test_one_sample_a_day_replaces_the_earlier_one(cop):
    store = FakeStore()
    tracker = cop.CopTracker(store)
    today = date(2026, 9, 9)
    run(tracker.async_record(22000, 9000, today=today))
    run(tracker.async_record(22421, 9088, today=today))
    assert store.data["samples"][today.isoformat()] == [22421.0, 9088.0]


def test_samples_survive_a_restart(cop):
    store = FakeStore()
    today = date(2026, 9, 9)
    run(cop.CopTracker(store).async_record(18000, 7500, today=today - timedelta(days=400)))

    revived = cop.CopTracker(store)
    run(revived.async_load())
    assert revived.result(22421, 9088, today=today).basis == "year"


def test_daily_figure_uses_a_sample_from_yesterday(cop):
    tracker = cop.CopTracker(FakeStore())
    now = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    run(tracker.async_record(22400, 9100, now=now - timedelta(hours=24)))
    result = tracker.result_day(22440, 9112, now=now)
    assert result.basis == "day"
    assert result.value == pytest.approx(40 / 12, abs=0.01)
    assert result.energy_out == pytest.approx(40, abs=0.1)


def test_a_sample_that_is_too_fresh_is_not_yesterday(cop):
    # Dividing two small integers a few hours apart swings wildly.
    tracker = cop.CopTracker(FakeStore())
    now = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    run(tracker.async_record(22400, 9100, now=now - timedelta(hours=6)))
    assert tracker.result_day(22440, 9112, now=now).value is None


def test_a_sample_that_is_too_old_is_not_yesterday_either(cop):
    tracker = cop.CopTracker(FakeStore())
    now = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    run(tracker.async_record(22400, 9100, now=now - timedelta(hours=48)))
    assert tracker.result_day(22440, 9112, now=now).value is None


def test_a_still_day_gives_no_daily_figure(cop):
    # A day the pump barely ran divides almost nothing by almost nothing.
    tracker = cop.CopTracker(FakeStore())
    now = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    run(tracker.async_record(22400, 9100, now=now - timedelta(hours=24)))
    assert tracker.result_day(22402, 9101, now=now).value is None


def test_a_counter_reset_gives_no_daily_figure(cop):
    tracker = cop.CopTracker(FakeStore())
    now = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    run(tracker.async_record(30000, 12000, now=now - timedelta(hours=24)))
    assert tracker.result_day(100, 40, now=now).value is None


def test_the_daily_run_is_pruned_but_the_yearly_map_is_not(cop):
    store = FakeStore()
    tracker = cop.CopTracker(store)
    now = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    run(tracker.async_record(20000, 8000, now=now - timedelta(days=10)))
    run(tracker.async_record(22440, 9112, now=now))
    assert len(store.data["recent"]) == 1
    assert len(store.data["samples"]) == 2


def test_the_daily_run_survives_a_restart(cop):
    store = FakeStore()
    now = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    run(cop.CopTracker(store).async_record(22400, 9100, now=now - timedelta(hours=24)))
    revived = cop.CopTracker(store)
    run(revived.async_load())
    assert revived.result_day(22440, 9112, now=now).basis == "day"
    assert revived.result_day(22440, 9112, now=now).value is not None


def test_an_old_store_without_the_daily_run_still_loads(cop):
    store = FakeStore()
    store.data = {"samples": {"2026-09-09": [22400.0, 9100.0]}}
    tracker = cop.CopTracker(store)
    run(tracker.async_load())
    assert tracker.result_day(22440, 9112).value is None
    assert tracker.result(22440, 9112).basis == "lifetime"


# --------------------------------------------- specific to this integration


def test_the_development_units_lifetime_figure():
    """Registers 33822/33824 on the S1155 this was built against."""
    daily, yearly, lifetime = _cop.cop_for_report(
        _cop.CopTracker(FakeStore()), 200468.0, 47932.6
    )
    assert lifetime == pytest.approx(4.18, abs=0.01)
    # No year of samples and no sample from yesterday: nothing under those names.
    assert yearly is None
    assert daily is None


def test_the_report_never_sends_lifetime_as_yearly():
    """The yearly sensor falls back to the lifetime figure; the report must not."""
    tracker = _cop.CopTracker(FakeStore())
    assert tracker.result(200468.0, 47932.6).basis == "lifetime"
    _daily, yearly, _lifetime = _cop.cop_for_report(tracker, 200468.0, 47932.6)
    assert yearly is None


def test_the_report_sends_a_yearly_figure_once_it_is_one():
    tracker = _cop.CopTracker(FakeStore())
    today = date.today()
    run(tracker.async_record(159264.7, 37592.7, today=today - timedelta(days=366)))
    _daily, yearly, _lifetime = _cop.cop_for_report(tracker, 200468.0, 47932.6)
    # 41 203 kWh delivered against 10 340 consumed.
    assert yearly == pytest.approx(3.98, abs=0.01)


def test_no_tracker_means_no_figures():
    assert _cop.cop_for_report(None, 200468.0, 47932.6) == (None, None, None)


def test_attributes_keep_their_keys_in_every_language():
    result = _cop.CopTracker(FakeStore()).result(200468.0, 47932.6)
    sv, en = result.as_attributes("sv"), result.as_attributes("en")
    assert set(sv) == set(en) == {"basis", "days", "energy_out_kwh", "energy_in_kwh"}
    assert sv["basis"] == "hela livslängden"
    assert en["basis"] == "whole lifetime"
