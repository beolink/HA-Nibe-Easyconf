"""The electricity meter an F-series pump does not have.

The S-series counts its own kilowatt hours in two registers, which is what the
coefficient of performance divides. The F-series counts neither, and that is
why it had no COP at all: the heat was there, the electricity was not.

It does report the two things that use the electricity - what the compressor
draws and what the immersion heater draws, both in kilowatts - and how fast its
two circulation pumps are running. NIBE publishes what those pumps draw at
their lowest and their highest speed, per size of pump, so the speed gives the
watts. What is left is the control system itself, a handful of watts that runs
whatever else happens.

Adding that power up over time is what a meter does. Between two readings the
power is taken as a straight line, which is the same Riemann sum Home
Assistant's own integration sensor makes, and the total is kept here rather
than in a helper so it survives a restart and so the parts stay visible: a
figure nobody can take apart is a figure nobody can check.

What this is not: a measurement. The compressor's own figure is the inverter's,
which is good; the pumps are a model; the control system is an estimate. The
whole thing lands within a few percent, which is what a coefficient of
performance is read to a tenth of anyway. Someone who wants it exact puts a
meter on the pump's circuit and uses that instead.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
import time

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1

#: Between two readings the power is taken as a straight line. Over a longer
#: gap than this - Home Assistant restarted, the gateway went quiet - that line
#: would be a guess about time nobody watched, so the lower of the two readings
#: is counted instead: the pump certainly drew at least that much.
MAX_TRAPEZOID_S = 900.0

#: A gap longer than this counts as nothing at all. A pump that has been away
#: for a month tells us nothing about that month, and inventing a floor for it
#: would quietly bend the yearly figure.
MAX_GAP_S = 6 * 3600.0


@dataclass
class Parts:
    """Kilowatt hours by where they went, so the assumptions stay visible."""

    compressor: float = 0.0
    addition: float = 0.0
    pumps: float = 0.0
    electronics: float = 0.0

    @property
    def total(self) -> float:
        return self.compressor + self.addition + self.pumps + self.electronics

    def add(self, name: str, kwh: float) -> None:
        setattr(self, name, getattr(self, name) + kwh)


class ElectricityCounter:
    """What the pump has used since this integration started counting.

    Also holds where its heat meters stood at that moment. The pump's meters
    have been counting since it was installed, this one starts at zero today,
    and a coefficient of performance made of the two absolute figures would be
    nonsense. Both are therefore counted from the same moment.
    """

    def __init__(self, store) -> None:
        self._store = store
        self.parts = Parts()
        #: The heat meters' sum when counting began, kWh.
        self.heat_baseline: float | None = None
        self._last: tuple[float, dict[str, float]] | None = None

    # -- persistence --------------------------------------------------------

    async def async_load(self) -> None:
        data = await self._store.async_load()
        if not data:
            return
        parts = data.get("parts") or {}
        self.parts = Parts(
            compressor=float(parts.get("compressor", 0.0)),
            addition=float(parts.get("addition", 0.0)),
            pumps=float(parts.get("pumps", 0.0)),
            electronics=float(parts.get("electronics", 0.0)),
        )
        baseline = data.get("heat_baseline")
        self.heat_baseline = None if baseline is None else float(baseline)
        stamp, watts = data.get("last_stamp"), data.get("last_watts")
        if stamp is not None and isinstance(watts, dict):
            # Counting continues across the restart: the pump kept running.
            self._last = (float(stamp), {k: float(v) for k, v in watts.items()})

    async def async_save(self) -> None:
        await self._store.async_save(
            {
                "parts": asdict(self.parts),
                "heat_baseline": self.heat_baseline,
                "last_stamp": None if self._last is None else self._last[0],
                "last_watts": None if self._last is None else self._last[1],
            }
        )

    # -- counting -----------------------------------------------------------

    def sample(self, watts: dict[str, float], now: float | None = None) -> None:
        """Take a reading of what each part is drawing, in watts."""
        now = time.time() if now is None else now
        previous, self._last = self._last, (now, dict(watts))
        if previous is None:
            return
        last_stamp, last_watts = previous
        seconds = now - last_stamp
        if seconds <= 0:
            # The clock went backwards; this reading starts a new line.
            return
        if seconds > MAX_GAP_S:
            _LOGGER.debug("Skipping a gap of %.0f s in the electricity count", seconds)
            return
        for name in ("compressor", "addition", "pumps", "electronics"):
            before, after = last_watts.get(name, 0.0), watts.get(name, 0.0)
            average = (before + after) / 2 if seconds <= MAX_TRAPEZOID_S else min(before, after)
            self.parts.add(name, average * seconds / 3_600_000)

    @property
    def kwh(self) -> float:
        """Electricity used since counting began."""
        return self.parts.total

    def produced(self, heat_total: float | None) -> float | None:
        """Heat delivered since counting began, from the pump's own meters.

        The first reading sets the mark the rest are measured from. A pump
        whose meters have been reset - a service visit, a new controller -
        reads lower than its mark, and the mark moves with it rather than
        turning the delivered heat negative.
        """
        if heat_total is None:
            return None
        if self.heat_baseline is None or heat_total < self.heat_baseline:
            self.heat_baseline = heat_total
        return heat_total - self.heat_baseline
