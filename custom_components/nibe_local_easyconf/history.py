"""Give the COP a past, from history Home Assistant already recorded.

A yearly coefficient of performance needs the two energy counters as they stood
a year ago, and the tracker only starts sampling when this integration is
installed. But the same counters are often already in Home Assistant's
long-term statistics: myUplink reports them as "Tot. produktion" / "Tot.
konsumtion", and core nibe_heatpump can expose them too. On the development
unit myUplink's history reached back 312 days, which brings the first real
yearly figure forward from a year after installation to seven weeks.

Nothing is configured. The series are found by value: a statistic whose latest
value is within a percent of the pump's own production counter, paired with
one within a percent of its consumption counter. The two have to come from the
same device, which is what rules out coincidence - a household electricity
meter can sit near the pump's consumption by chance, but not alongside a
second series from the same device that also matches its production.

This module's matching and reshaping are plain functions, tested without Home
Assistant; only `async_import_history` talks to the recorder.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

#: How close another series' latest value must be to the pump's own counter.
#: Relative, because the other series can lag by an hour or two, and a pump
#: delivering 16 kW moves its production counter that much every hour.
MATCH_TOLERANCE = 0.01

#: A series whose newest value is older than this is not a live copy.
MAX_STALENESS = timedelta(days=2)


@dataclass(frozen=True)
class Candidate:
    """One recorded energy series, as far as matching needs to know it."""

    statistic_id: str
    latest: float
    latest_at: datetime
    device_id: str | None


def _close(value: float, target: float) -> bool:
    return target > 0 and abs(value - target) <= target * MATCH_TOLERANCE


def match_counters(
    candidates: list[Candidate],
    energy_out: float,
    energy_in: float,
    now: datetime,
) -> tuple[str, str] | None:
    """The series recording this pump's production and consumption counters."""
    fresh = [c for c in candidates if now - c.latest_at <= MAX_STALENESS]
    producing = [c for c in fresh if _close(c.latest, energy_out)]
    consuming = [c for c in fresh if _close(c.latest, energy_in)]
    pairs = [
        (out, used)
        for out in producing
        for used in consuming
        if out.statistic_id != used.statistic_id
        and out.device_id is not None
        and out.device_id == used.device_id
    ]
    if not pairs:
        return None
    out, used = min(
        pairs,
        key=lambda pair: abs(pair[0].latest - energy_out) / energy_out
        + abs(pair[1].latest - energy_in) / energy_in,
    )
    return out.statistic_id, used.statistic_id


def _paired(out_rows: list[dict], in_rows: list[dict]):
    """Rows of the two series that cover the same period, as (row, out, in)."""
    consumed = {row["start"]: row.get("state") for row in in_rows}
    for row in out_rows:
        out, used = row.get("state"), consumed.get(row["start"])
        if out is not None and used is not None:
            yield row, float(out), float(used)


def daily_samples(out_rows: list[dict], in_rows: list[dict]) -> dict[str, tuple[float, float]]:
    """One (out, in) pair per day, keyed the way the COP tracker keys its own.

    Each day's value is the counters at the end of that day, dated by the UTC
    day the period ends in, matching the tracker's own UTC-dated samples.
    """
    daily: dict[str, tuple[float, float]] = {}
    for row, out, used in _paired(out_rows, in_rows):
        day = datetime.fromtimestamp(row["end"] - 1, UTC).date().isoformat()
        daily[day] = (out, used)
    return daily


def recent_samples(out_rows: list[dict], in_rows: list[dict]) -> list[tuple[str, float, float]]:
    """Hourly (timestamp, out, in) samples for the tracker's day window.

    These are what let the daily figure appear at once rather than a day after
    installation: the tracker needs a sample 20-30 hours old.
    """
    return [
        (datetime.fromtimestamp(row["end"], UTC).isoformat(), out, used)
        for row, out, used in _paired(out_rows, in_rows)
    ]


async def async_import_history(hass, coordinator, domain: str) -> dict[str, Any] | None:
    """Find the recorded copies of the two counters and seed the COP tracker.

    Returns what was imported, or None when nothing suitable was recorded.
    Never raises: history is a bonus, and its absence must not affect setup.
    """
    from homeassistant.components.recorder import get_instance
    from homeassistant.components.recorder.statistics import (
        async_list_statistic_ids,
        statistics_during_period,
    )
    from homeassistant.helpers import entity_registry as er
    from homeassistant.util import dt as dt_util

    from .cop import COP_HISTORY_DAYS, RECENT_DAYS

    tracker = coordinator.cop
    energy_out, energy_in = coordinator.energy_out, coordinator.energy_in
    if tracker is None or energy_out is None or energy_in is None:
        return None

    try:
        registry = er.async_get(hass)

        def ours(statistic_id: str) -> bool:
            entity = registry.async_get(statistic_id)
            return entity is not None and entity.platform == domain

        listed = await async_list_statistic_ids(hass, statistic_type="sum")
        energy_ids = {
            item["statistic_id"]
            for item in listed
            if item.get("unit_class") == "energy" and not ours(item["statistic_id"])
        }
        if not energy_ids:
            return None

        now = dt_util.utcnow()
        recorder = get_instance(hass)
        units = {"energy": "kWh"}
        latest = await recorder.async_add_executor_job(
            statistics_during_period,
            hass, now - MAX_STALENESS, None, energy_ids, "hour", units, {"state"},
        )
        candidates = []
        for statistic_id, rows in latest.items():
            rows = [row for row in rows if row.get("state") is not None]
            if not rows:
                continue
            entity = registry.async_get(statistic_id)
            candidates.append(
                Candidate(
                    statistic_id,
                    float(rows[-1]["state"]),
                    datetime.fromtimestamp(rows[-1]["end"], UTC),
                    entity.device_id if entity else None,
                )
            )

        match = match_counters(candidates, energy_out, energy_in, now)
        if match is None:
            _LOGGER.debug("No recorded copy of the energy counters found")
            return None
        out_id, in_id = match

        daily_rows = await recorder.async_add_executor_job(
            statistics_during_period,
            hass, now - timedelta(days=COP_HISTORY_DAYS), None, {out_id, in_id}, "day",
            units, {"state"},
        )
        hourly_rows = await recorder.async_add_executor_job(
            statistics_during_period,
            hass, now - timedelta(days=RECENT_DAYS), None, {out_id, in_id}, "hour",
            units, {"state"},
        )
        daily = daily_samples(daily_rows.get(out_id, []), daily_rows.get(in_id, []))
        recent = recent_samples(hourly_rows.get(out_id, []), hourly_rows.get(in_id, []))

        added = await tracker.async_seed(
            daily,
            recent,
            energy_out,
            energy_in,
            {
                "production": out_id,
                "consumption": in_id,
                "from": min(daily) if daily else None,
                "imported_at": now.isoformat(),
            },
        )
        _LOGGER.info(
            "Imported %d days of energy history from %s and %s, back to %s",
            added, out_id, in_id, tracker.history.get("from"),
        )
        return tracker.history
    except Exception:  # history is a bonus; never let it break setup
        _LOGGER.debug("Energy history import skipped", exc_info=True)
        return None
