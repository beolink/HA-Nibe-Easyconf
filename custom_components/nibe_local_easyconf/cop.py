"""Coefficient of performance: over a day, a rolling year and the lifetime.

Ported from the CTC integration (ha-ctc, cop.py) so the figures mean the same
thing in the fleet report whichever pump sent them. The tracker is unchanged:
one sample a day of the two lifetime counters, the oldest sample inside the
window as the starting point, and the lifetime figure standing in - labelled as
such - until a year of samples exists.

What differs is where the counters come from. CTC's Modbus never reports what
the unit delivers, so that integration scrapes the display's two lifetime
counters by their printed label. A NIBE S-series pump has both on Modbus:
register 33822 "Tot. production" and 33824 "Tot. consumption", in tenths of a
kWh. On the development unit they read 200 468.0 and 47 932.6 kWh, the exact
figures myUplink's cloud reports for the same pump.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1

#: Samples are kept a little longer than the window, so the oldest one inside
#: it is still there on the day the window completes.
COP_HISTORY_DAYS = 400
COP_WINDOW_DAYS = 365

#: Below this the divisor is noise rather than a measurement. A year needs a
#: real number behind it; a single day is allowed to work with much less, since
#: a day of heating is a few tens of kilowatt hours at most.
MIN_CONSUMPTION_KWH = 50.0
MIN_CONSUMPTION_KWH_DAY = 3.0

#: A sample has to be this old before it can serve as yesterday. The counters
#: are whole kilowatt hours, so a shorter span divides two small integers and
#: the answer swings wildly.
DAY_MIN_HOURS = 20
DAY_MAX_HOURS = 30

#: How long the short run of samples behind the daily figure is kept.
RECENT_DAYS = 4


@dataclass
class CopResult:
    """A coefficient of performance and how it was arrived at."""

    value: float | None
    #: "year" once a full window is available, "lifetime" before that.
    basis: str
    days: int
    energy_out: float | None = None
    energy_in: float | None = None

    def as_attributes(self, language: str = "sv") -> dict[str, Any]:
        """Keys stay the same in every language, so automations can use them;
        only the description of the basis is translated."""
        sv = language.startswith("sv")
        basis = {
            "year": "rullande år" if sv else "rolling year",
            "day": "senaste dygnet" if sv else "last day",
            "lifetime": "hela livslängden" if sv else "whole lifetime",
        }.get(self.basis, self.basis)
        return {
            "basis": basis,
            "days": self.days,
            "energy_out_kwh": self.energy_out,
            "energy_in_kwh": self.energy_in,
        }


def _parse(stamp: str) -> datetime:
    """Read a stored timestamp, treating a naive one as UTC."""
    value = datetime.fromisoformat(stamp)
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _ratio(out: float, consumed: float) -> float | None:
    if consumed < MIN_CONSUMPTION_KWH:
        return None
    return round(out / consumed, 2)


class CopTracker:
    """Keeps one sample a day of the two lifetime counters."""

    def __init__(self, store: Any) -> None:
        self._store = store
        self._samples: dict[str, list[float]] = {}
        #: A short run of timestamped samples. The daily figure needs finer
        #: spacing than one a day, or "yesterday" could be anything from 12 to
        #: 36 hours ago depending on when the samples happened to land.
        self._recent: list[tuple[str, float, float]] = []
        #: Where earlier history was imported from, once it has been. Kept so
        #: the import runs once, and so the sensor can say what the yearly
        #: figure stands on. Not in the CTC original.
        self.history: dict[str, Any] | None = None
        self._loaded = False

    async def async_load(self) -> None:
        if self._loaded:
            return
        data = await self._store.async_load()
        if isinstance(data, dict) and isinstance(data.get("samples"), dict):
            self._samples = {
                day: [float(values[0]), float(values[1])]
                for day, values in data["samples"].items()
                if isinstance(values, (list, tuple)) and len(values) >= 2
            }
        if isinstance(data, dict) and isinstance(data.get("history"), dict):
            self.history = data["history"]
        if isinstance(data, dict) and isinstance(data.get("recent"), list):
            for row in data["recent"]:
                if isinstance(row, (list, tuple)) and len(row) >= 3:
                    try:
                        self._recent.append((str(row[0]), float(row[1]), float(row[2])))
                    except (TypeError, ValueError):
                        continue
        self._loaded = True

    async def async_record(
        self,
        energy_out: float | None,
        energy_in: float | None,
        today: date | None = None,
        now: datetime | None = None,
    ) -> None:
        """Store the counters: one per day for the year, and a timestamped run."""
        if energy_out is None or energy_in is None:
            return
        await self.async_load()
        when = now or datetime.now(UTC)
        stamp = (today or when.date()).isoformat()
        self._samples[stamp] = [float(energy_out), float(energy_in)]
        cutoff = ((today or when.date()) - timedelta(days=COP_HISTORY_DAYS)).isoformat()
        self._samples = {d: v for d, v in self._samples.items() if d >= cutoff}

        self._recent.append((when.isoformat(), float(energy_out), float(energy_in)))
        keep = when - timedelta(days=RECENT_DAYS)
        self._recent = [r for r in self._recent if _parse(r[0]) >= keep]

        await self._async_save()

    async def _async_save(self) -> None:
        data: dict[str, Any] = {"samples": self._samples, "recent": self._recent}
        if self.history is not None:
            data["history"] = self.history
        await self._store.async_save(data)

    async def async_seed(
        self,
        daily: dict[str, tuple[float, float]],
        recent: list[tuple[str, float, float]],
        energy_out: float,
        energy_in: float,
        source: dict[str, Any],
    ) -> int:
        """Add history recorded elsewhere for the same two counters.

        Days the tracker sampled itself are never overwritten: its own readings
        come straight from the pump, an import only fills in what came before.
        A value above today's counter cannot be the past of this counter - a
        mismatch or a replaced unit - so it is dropped rather than trusted.
        Returns the number of days added. Not in the CTC original.
        """
        await self.async_load()

        def plausible(out: float, consumed: float) -> bool:
            return 0 < out <= energy_out and 0 < consumed <= energy_in

        added = 0
        for day, (out, consumed) in sorted(daily.items()):
            if day in self._samples or not plausible(out, consumed):
                continue
            self._samples[day] = [float(out), float(consumed)]
            added += 1
        newest = max((date.fromisoformat(d) for d in self._samples), default=None)
        if newest is not None:
            cutoff = (newest - timedelta(days=COP_HISTORY_DAYS)).isoformat()
            self._samples = {d: v for d, v in self._samples.items() if d >= cutoff}

        have = {row[0] for row in self._recent}
        for stamp, out, consumed in recent:
            if stamp not in have and plausible(out, consumed):
                self._recent.append((stamp, float(out), float(consumed)))
        keep = datetime.now(UTC) - timedelta(days=RECENT_DAYS)
        self._recent = sorted(
            (r for r in self._recent if _parse(r[0]) >= keep), key=lambda r: _parse(r[0])
        )

        self.history = {**source, "days_added": added}
        await self._async_save()
        return added

    def result_day(
        self,
        energy_out: float | None,
        energy_in: float | None,
        now: datetime | None = None,
    ) -> CopResult:
        """The figure over the last day, from the newest sample old enough to be
        yesterday. Nothing is returned until such a sample exists."""
        if energy_out is None or energy_in is None:
            return CopResult(None, "day", 0)
        when = now or datetime.now(UTC)
        oldest_allowed = when - timedelta(hours=DAY_MAX_HOURS)
        newest_allowed = when - timedelta(hours=DAY_MIN_HOURS)
        window = [
            r for r in self._recent if oldest_allowed <= _parse(r[0]) <= newest_allowed
        ]
        if not window:
            return CopResult(None, "day", 0)
        stamp, base_out, base_in = max(window, key=lambda r: _parse(r[0]))
        delta_out = energy_out - base_out
        delta_in = energy_in - base_in
        if delta_out < 0 or delta_in < 0:
            return CopResult(None, "day", 0)
        hours = (when - _parse(stamp)).total_seconds() / 3600
        if delta_in < MIN_CONSUMPTION_KWH_DAY:
            return CopResult(
                None, "day", round(hours / 24), round(delta_out, 1), round(delta_in, 1)
            )
        return CopResult(
            round(delta_out / delta_in, 2),
            "day",
            max(1, round(hours / 24)),
            round(delta_out, 1),
            round(delta_in, 1),
        )

    def result(
        self,
        energy_out: float | None,
        energy_in: float | None,
        today: date | None = None,
    ) -> CopResult:
        """Work out the rolling figure, falling back to the lifetime one."""
        if energy_out is None or energy_in is None:
            return CopResult(None, "lifetime", 0)

        now = today or date.today()
        window_start = (now - timedelta(days=COP_WINDOW_DAYS)).isoformat()
        older = sorted(d for d in self._samples if d <= window_start)
        if older:
            base_out, base_in = self._samples[older[-1]]
            span = (now - date.fromisoformat(older[-1])).days
            delta_out = energy_out - base_out
            delta_in = energy_in - base_in
            # A counter that went backwards means the unit was replaced or reset;
            # the lifetime figure is the only honest answer then.
            if delta_out >= 0 and delta_in >= 0:
                value = _ratio(delta_out, delta_in)
                if value is not None:
                    return CopResult(value, "year", span, round(delta_out, 1), round(delta_in, 1))

        oldest = min(self._samples) if self._samples else None
        span = (now - date.fromisoformat(oldest)).days if oldest else 0
        return CopResult(
            _ratio(energy_out, energy_in),
            "lifetime",
            span,
            round(energy_out, 1),
            round(energy_in, 1),
        )


def cop_for_report(
    tracker: CopTracker | None,
    energy_out: float | None,
    energy_in: float | None,
) -> tuple[float | None, float | None, float | None]:
    """The figures over a day, a rolling year and the whole lifetime.

    As in the CTC integration, each is only returned when it stands on its own
    span. Sending the lifetime figure under the yearly name before a year of
    samples exists would be a different number wearing the wrong label.
    """
    if tracker is None:
        return None, None, None
    yearly_result = tracker.result(energy_out, energy_in)
    yearly = yearly_result.value if yearly_result.basis == "year" else None
    daily = tracker.result_day(energy_out, energy_in).value
    lifetime = None
    if energy_out is not None and energy_in is not None and energy_in >= MIN_CONSUMPTION_KWH:
        lifetime = round(energy_out / energy_in, 2)
    return daily, yearly, lifetime
