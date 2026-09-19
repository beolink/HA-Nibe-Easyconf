"""Polling and writing for an F-series pump behind a NibeGW gateway.

The Modbus TCP coordinator reads everything every cycle, because a block read
of a hundred registers costs one round-trip. Through the gateway every register
is a round-trip of its own, about a second, so this one reads only what is due:
measurements every cycle, counters every few minutes, settings every ten, and
nothing at all that the pump already pushes from LOG.SET. See gateway.py for
the schedule and fseries.py for what is on by default.

The entities neither know nor care which coordinator they have. Both offer the
same attributes: registers, discovery, data, subscribe/unsubscribe,
async_write, entity_names, serial, firmware, cop, and the value-label helpers.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import timedelta
import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import fseries
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .discovery import DiscoveryResult
from .gateway import (
    ANNOUNCE_REGISTER,
    KEEPALIVE_INTERVAL,
    UNREACHABLE_AFTER,
    GatewayClient,
    GatewayError,
    GatewayRejected,
    GatewayTimeout,
    PollSchedule,
    ProbeResult,
    Value,
    probe,
)
from .power import ElectricityCounter

_LOGGER = logging.getLogger(__name__)

#: Share of the update interval one cycle may spend reading. What does not fit
#: stays due, most overdue first, for the next cycle.
CYCLE_BUDGET = 0.75

#: Values the pump pushes arrive several times a minute; entities are brought
#: up to date with them at most this often.
PUSH_FLUSH_DELAY = 5.0


def gateway_discovery(registers: dict[int, dict], result: ProbeResult) -> DiscoveryResult:
    """What setup learned, in the shape the rest of the integration stores.

    Every register exists through the gateway, so all of the map is present
    and none absent, except those this integration cannot represent: dates,
    and the 32-bit degree minutes register that does not decode reliably.
    """
    present = {
        register
        for register, meta in registers.items()
        if meta.get("type") != "date" and meta.get("title") not in fseries.UNRELIABLE_TITLES
    }
    # Every flag stays, the ones that answered "no" as well: the page gathers
    # them under "accessories registered", where a module the pump does not
    # have is half the answer.
    return DiscoveryResult(
        present=present,
        reporting=result.reporting & present,
        absent=set(),
        probed=result.probed & present,
    )


class NibeGatewayCoordinator(DataUpdateCoordinator[dict[int, Value]]):
    """Reads what is due, one register at a time, and keeps what the pump pushes."""

    is_gateway = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GatewayClient,
        registers: dict[int, dict],
        discovery: DiscoveryResult,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
            config_entry=entry,
        )
        self.client = client
        self.registers = registers
        self.discovery = discovery
        self.schedule = PollSchedule(float(scan_interval), registers)
        self._subscribed: set[int] = set()
        #: Read whether or not an entity asks for them: what the electricity
        #: meter below is built from.
        self._internal: set[int] = set()
        #: How many entities read each register: the heat offset backs both its
        #: own number and the heating mode select.
        self._subscribers: Counter[int] = Counter()
        self._values: dict[int, Value] = {}
        self._reads_last_cycle = 0
        self._last_request = 0.0
        self._remove_listener: Callable[[], None] | None = None
        self._flush_unsub: CALLBACK_TYPE | None = None
        #: Cumulative failed poll cycles, for the daily report.
        self.read_failures = 0
        self.cop = None
        #: The meter the pump does not have, built from the power it reports.
        #: Set up by async_setup_entry when the pump's own heat meters answer;
        #: without one there is nothing to divide, and no COP.
        self.electricity: ElectricityCounter | None = None
        self.serial = None
        self.firmware: int | None = None
        self.entity_names: dict[int, str] = {}

    # -- the attributes the entities and the report read -------------------

    @property
    def block_reads(self) -> int:
        """Reads the last cycle cost; through the gateway, one per register."""
        return self._reads_last_cycle

    @property
    def subscribed_count(self) -> int:
        return len(self._subscribed)

    def start_counting(self, counter: ElectricityCounter) -> None:
        """Take the meter, and keep what it is made of in the poll cycle.

        The coefficient of performance cannot depend on which entities somebody
        left switched on, so these registers are read whether or not one asks.
        """
        self.electricity = counter
        self._internal = {
            fseries.COMPRESSOR_POWER,
            fseries.ADDITION_POWER,
            fseries.HEAT_MEDIUM_PUMP_SPEED,
            fseries.BRINE_PUMP_SPEED,
            *fseries.HEAT_METERS,
        } & set(self.registers)

    @property
    def heat_total(self) -> float | None:
        """What the pump's own heat meters have counted, kWh.

        Heating, hot water and the pool, added up. A meter that has not
        answered yet is left out rather than counted as zero, which would drop
        the total and look like the pump had run backwards.
        """
        readings = [
            float(self._values[register])
            for register in fseries.HEAT_METERS
            if isinstance(self._values.get(register), (int, float))
        ]
        return sum(readings) if readings else None

    @property
    def watts(self) -> dict[str, float] | None:
        """What each part of the pump is drawing right now.

        The compressor and the immersion heater say so themselves; the two
        circulation pumps are worked out from their speed and NIBE's figures
        for this size of pump; the control system is a constant.
        """
        compressor = self._values.get(fseries.COMPRESSOR_POWER)
        addition = self._values.get(fseries.ADDITION_POWER)
        if not isinstance(compressor, (int, float)):
            return None
        brine_limits, medium_limits = fseries.circulation_pumps(
            self.serial.size if self.serial else None
        )
        brine = self._values.get(fseries.BRINE_PUMP_SPEED)
        medium = self._values.get(fseries.HEAT_MEDIUM_PUMP_SPEED)
        return {
            "compressor": float(compressor) * 1000,
            "addition": float(addition) * 1000 if isinstance(addition, (int, float)) else 0.0,
            "pumps": (
                fseries.pump_watts(brine_limits, brine if isinstance(brine, (int, float)) else None)
                + fseries.pump_watts(
                    medium_limits, medium if isinstance(medium, (int, float)) else None
                )
            ),
            "electronics": fseries.ELECTRONICS_W,
        }

    @property
    def energy_out(self) -> float | None:
        """Heat delivered since this integration started counting, kWh."""
        if self.electricity is None:
            return None
        return self.electricity.produced(self.heat_total)

    @property
    def energy_in(self) -> float | None:
        """Electricity used over the same span, kWh."""
        return None if self.electricity is None else self.electricity.kwh

    def default_enabled(self, register: int, meta: dict) -> bool:
        return fseries.is_default(meta, register in self.discovery.reporting)

    def labels_for(self, register: int, meta: dict, language: str) -> dict[str, str] | None:
        return fseries.labels_for(meta, language)

    def is_alarm(self, meta: dict) -> bool:
        return fseries.is_alarm_register(meta)

    def alarm_text(self, code: float | None, language: str) -> str | None:
        return fseries.alarm_text(code, language)

    # -- lifecycle ---------------------------------------------------------

    @callback
    def async_start_listening(self) -> None:
        """Take every value the gateway delivers, pushed or answered."""
        if self._remove_listener is None:
            self._remove_listener = self.client.add_listener(self._on_value)

    async def async_close(self) -> None:
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None
        if self._flush_unsub is not None:
            self._flush_unsub()
            self._flush_unsub = None
        await self.client.stop()

    def seed(self, register: int, value: Value) -> None:
        """Keep a value read before the coordinator existed, e.g. at start-up."""
        self._values[register] = value
        now = time.monotonic()
        self.schedule.seen(register, now)
        self._last_request = now

    # -- subscriptions -----------------------------------------------------

    def subscribe(self, register: int) -> None:
        self._subscribers[register] += 1
        self._subscribed.add(register)

    def unsubscribe(self, register: int) -> None:
        """Stop reading a register once no entity reads it any more."""
        self._subscribers[register] -= 1
        if self._subscribers[register] > 0:
            return
        del self._subscribers[register]
        self._subscribed.discard(register)
        self.schedule.forget(register)

    # -- values from the gateway -------------------------------------------

    @callback
    def _on_value(self, register: int, value: Value) -> None:
        """A value arrived: an answer to a read, or a register LOG.SET pushes.

        Called from the UDP protocol, on the event loop. A value that changed
        and backs an entity is shown within PUSH_FLUSH_DELAY; the data is set
        without rescheduling the next refresh, which pushes arriving every few
        seconds would otherwise postpone for ever.
        """
        self.schedule.seen(register, time.monotonic())
        changed = register not in self._values or self._values[register] != value
        self._values[register] = value
        if changed and register in self._subscribed and self._flush_unsub is None:
            self._flush_unsub = async_call_later(self.hass, PUSH_FLUSH_DELAY, self._flush)

    @callback
    def _flush(self, _now=None) -> None:
        self._flush_unsub = None
        self.data = dict(self._values)
        self.async_update_listeners()

    # -- polling -----------------------------------------------------------

    async def _async_update_data(self) -> dict[int, Value]:
        wanted = self._subscribed | self._internal
        interval = self.update_interval.total_seconds() if self.update_interval else 60.0
        due = self.schedule.due(wanted, time.monotonic())
        if not due and time.monotonic() - self._last_request >= KEEPALIVE_INTERVAL:
            # Everything is fresh, most likely pushed from LOG.SET. One read
            # keeps the gateway relaying those pushes to Home Assistant.
            due = [ANNOUNCE_REGISTER]
        started = time.monotonic()
        reads = successes = timeouts_in_a_row = 0
        for register in due:
            if time.monotonic() - started > CYCLE_BUDGET * interval:
                break
            reads += 1
            self._last_request = time.monotonic()
            try:
                value = await self.client.read(register)
            except GatewayTimeout:
                self.schedule.failed(register, time.monotonic())
                timeouts_in_a_row += 1
                if successes == 0 and timeouts_in_a_row >= UNREACHABLE_AFTER:
                    self._reads_last_cycle = reads
                    self.read_failures += 1
                    raise UpdateFailed(
                        f"The NibeGW gateway at {self.client.host} does not answer"
                    ) from None
                continue
            except GatewayError as err:
                _LOGGER.debug("Register %s failed: %s", register, err)
                self.schedule.failed(register, time.monotonic())
                continue
            successes += 1
            timeouts_in_a_row = 0
            self._values[register] = value
            self.schedule.seen(register, time.monotonic())
        self._reads_last_cycle = reads
        self._count_electricity()
        return dict(self._values)

    def _count_electricity(self) -> None:
        """Add this cycle's power to the meter the pump does not have."""
        if self.electricity is None:
            return
        watts = self.watts
        if watts is not None:
            self.electricity.sample(watts)

    # -- writing -----------------------------------------------------------

    async def async_write(self, register: int, value: float) -> None:
        """Write a register, then read it back: the pump may clamp what it stores."""
        meta = self.registers.get(register)
        if meta is None:
            raise HomeAssistantError(f"Unknown register {register}")
        if not meta.get("write"):
            raise HomeAssistantError(f"Register {register} is read-only")
        self._last_request = time.monotonic()
        try:
            await self.client.write(register, value)
        except GatewayRejected as err:
            raise HomeAssistantError(
                f"The pump did not accept {value} for register {register}"
            ) from err
        except GatewayError as err:
            raise HomeAssistantError(f"Could not write register {register}: {err}") from err
        try:
            stored = await self.client.read(register)
        except GatewayError:
            stored = value
        self.seed(register, stored)
        self.async_set_updated_data(dict(self._values))

    # -- rediscovery ---------------------------------------------------------

    async def async_rescan(self) -> DiscoveryResult:
        """Read the default registers again, e.g. after fitting a sensor."""
        wanted = sorted(set(fseries.default_registers(self.registers)) | self._subscribed)
        try:
            result = await probe(self.client, wanted)
            # This service exists for the day an accessory is fitted, so the
            # flags just read decide what else is worth reading.
            extra = [
                register
                for register in fseries.accessory_registers(self.registers, result.values)
                if register not in result.values
            ]
            if extra:
                more = await probe(self.client, extra)
                result.values.update(more.values)
                result.failed |= more.failed
        except GatewayError as err:
            raise HomeAssistantError(f"Rescan through the gateway failed: {err}") from err
        for register, value in result.values.items():
            self.seed(register, value)
        self.discovery = gateway_discovery(self.registers, result)
        _LOGGER.info("Rescan complete: %s", self.discovery.summary())
        await self.async_request_refresh()
        return self.discovery
