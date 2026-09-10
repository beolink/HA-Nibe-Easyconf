"""Importing earlier energy history into the COP tracker.

The figures are the development unit's: the pump's counters stood at 200 468.0
and 47 932.6 kWh on 2026-09-10, and myUplink had recorded the same counters
since 2025-11-02, when they read 159 264.7 and 37 592.7.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
import importlib

import pytest

from .conftest import PACKAGE

history = importlib.import_module(f"{PACKAGE}.history")
cop = importlib.import_module(f"{PACKAGE}.cop")

NOW = datetime(2026, 9, 10, 10, 0, tzinfo=UTC)
OUT, IN = 200468.0, 47932.6


def _candidate(sid, latest, device="pump", age=timedelta(hours=1)):
    return history.Candidate(sid, latest, NOW - age, device)


# ------------------------------------------------------------ matching


def test_the_same_counters_on_the_same_device_are_found():
    found = history.match_counters(
        [
            _candidate("sensor.tot_produktion", 200468.0),
            _candidate("sensor.tot_konsumtion", 47933.0),
            _candidate("sensor.grid_import", 81234.0, device="meter"),
        ],
        OUT, IN, NOW,
    )
    assert found == ("sensor.tot_produktion", "sensor.tot_konsumtion")


def test_a_lagging_copy_still_matches():
    """A cloud copy an hour or two behind is still the same counter."""
    found = history.match_counters(
        [_candidate("p", OUT - 30), _candidate("c", IN - 7)], OUT, IN, NOW
    )
    assert found == ("p", "c")


def test_a_coincidental_match_on_another_device_is_refused():
    """A household meter near the pump's consumption is not the pump's counter."""
    found = history.match_counters(
        [
            _candidate("sensor.tot_produktion", 200468.0, device="pump"),
            _candidate("sensor.house_meter", 47900.0, device="meter"),
        ],
        OUT, IN, NOW,
    )
    assert found is None


def test_one_matching_counter_is_not_enough():
    found = history.match_counters([_candidate("p", OUT)], OUT, IN, NOW)
    assert found is None


def test_series_without_a_device_are_refused():
    found = history.match_counters(
        [_candidate("p", OUT, device=None), _candidate("c", IN, device=None)], OUT, IN, NOW
    )
    assert found is None


def test_a_stale_series_is_not_a_live_copy():
    found = history.match_counters(
        [_candidate("p", OUT, age=timedelta(days=5)), _candidate("c", IN, age=timedelta(days=5))],
        OUT, IN, NOW,
    )
    assert found is None


def test_values_too_far_off_are_different_counters():
    found = history.match_counters(
        [_candidate("p", OUT * 1.05), _candidate("c", IN)], OUT, IN, NOW
    )
    assert found is None


# ------------------------------------------------------------ reshaping


def _row(start: datetime, hours: int, state):
    return {
        "start": start.timestamp(),
        "end": (start + timedelta(hours=hours)).timestamp(),
        "state": state,
    }


def test_days_are_dated_like_the_trackers_own():
    # Home Assistant's days run from local midnight: 22:00 UTC in summer.
    start = datetime(2026, 9, 8, 22, 0, tzinfo=UTC)
    daily = history.daily_samples([_row(start, 24, 200000.0)], [_row(start, 24, 47800.0)])
    assert daily == {"2026-09-09": (200000.0, 47800.0)}


def test_rows_only_pair_up_when_both_series_have_them():
    start = datetime(2026, 9, 8, 22, 0, tzinfo=UTC)
    later = start + timedelta(days=1)
    daily = history.daily_samples(
        [_row(start, 24, 1.0), _row(later, 24, 2.0)],
        [_row(start, 24, 0.5)],
    )
    assert list(daily) == ["2026-09-09"]


def test_rows_without_a_value_are_skipped():
    start = datetime(2026, 9, 8, 22, 0, tzinfo=UTC)
    assert history.daily_samples([_row(start, 24, None)], [_row(start, 24, 1.0)]) == {}


def test_hourly_samples_carry_their_end_time():
    start = datetime(2026, 9, 9, 9, 0, tzinfo=UTC)
    recent = history.recent_samples([_row(start, 1, 200440.0)], [_row(start, 1, 47925.0)])
    assert recent == [("2026-09-09T10:00:00+00:00", 200440.0, 47925.0)]


# ------------------------------------------------------------ seeding


class FakeStore:
    def __init__(self) -> None:
        self.data = None

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.data = data


def run(coro):
    return asyncio.run(coro)


SOURCE = {"production": "sensor.p", "consumption": "sensor.c", "from": "2025-11-02"}


def test_imported_days_fill_in_but_never_overwrite():
    tracker = cop.CopTracker(FakeStore())
    run(tracker.async_record(OUT, IN, today=date(2026, 9, 10)))
    added = run(
        tracker.async_seed(
            {"2025-11-02": (159264.7, 37592.7), "2026-09-10": (1.0, 1.0)}, [], OUT, IN, SOURCE
        )
    )
    assert added == 1
    # The tracker's own reading from the pump stays.
    assert tracker._samples["2026-09-10"] == [OUT, IN]


def test_a_value_above_todays_counter_is_not_its_past():
    tracker = cop.CopTracker(FakeStore())
    added = run(tracker.async_seed({"2025-11-02": (OUT + 100, IN)}, [], OUT, IN, SOURCE))
    assert added == 0


def test_312_days_of_history_is_not_yet_a_year():
    """The development unit: the yearly figure still stands on the lifetime."""
    tracker = cop.CopTracker(FakeStore())
    run(tracker.async_seed({"2025-11-02": (159264.7, 37592.7)}, [], OUT, IN, SOURCE))
    assert tracker.result(OUT, IN, today=date(2026, 9, 10)).basis == "lifetime"


def test_the_first_real_yearly_figure_arrives_on_the_anniversary():
    tracker = cop.CopTracker(FakeStore())
    run(tracker.async_seed({"2025-11-02": (159264.7, 37592.7)}, [], OUT, IN, SOURCE))
    result = tracker.result(OUT, IN, today=date(2026, 11, 2))
    assert result.basis == "year"
    assert result.value == pytest.approx(3.98, abs=0.01)


def test_hourly_history_gives_a_daily_figure_at_once():
    """Without it the daily figure would wait a day after installation."""
    tracker = cop.CopTracker(FakeStore())
    yesterday = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
    run(tracker.async_seed({}, [(yesterday, OUT - 40.0, IN - 10.0)], OUT, IN, SOURCE))
    result = tracker.result_day(OUT, IN)
    assert result.value == pytest.approx(4.0, abs=0.01)


def test_the_import_is_remembered_across_a_restart():
    store = FakeStore()
    run(cop.CopTracker(store).async_seed({"2025-11-02": (159264.7, 37592.7)}, [], OUT, IN, SOURCE))
    reloaded = cop.CopTracker(store)
    run(reloaded.async_load())
    assert reloaded.history["from"] == "2025-11-02"
    assert reloaded.history["days_added"] == 1


def test_a_later_sample_does_not_forget_the_import():
    """The CTC original saved only its two keys; the import record must survive."""
    store = FakeStore()
    tracker = cop.CopTracker(store)
    run(tracker.async_seed({"2025-11-02": (159264.7, 37592.7)}, [], OUT, IN, SOURCE))
    run(tracker.async_record(OUT + 5, IN + 1))
    assert store.data["history"]["production"] == "sensor.p"
