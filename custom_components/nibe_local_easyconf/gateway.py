"""Talk to an F-series pump through a NibeGW gateway.

The F-series has no Modbus TCP. It is reached through a gateway on the pump's
RS-485 accessory bus that stands in for NIBE's MODBUS 40 accessory: an ESP32
running esphome-nibe (see esphome/ in this repository), which acknowledges the
pump's telegrams on its own and relays reads and writes over UDP. The `nibe`
library speaks that protocol; this module turns it into what the rest of the
integration expects - numbers per register - and decides what to read when.

What the gateway changes compared with Modbus TCP, measured on an F1255-16
through a Waveshare ESP32-S3-RS485-CAN:

* One register per request, about a second each. There are no block reads, so
  the cost of a poll cycle is simply the number of registers in it.
* Every register answers. A sensor that is not fitted returns NIBE's "no
  reading" value rather than an error, so a timeout means the gateway or the
  bus, never the register.
* 32-bit registers of an accessory that is not fitted read as 0xFFFF8000, the
  16-bit sentinel sign-extended. The library does not take that for "no
  reading"; this module does.
* The pump pushes up to 20 registers on its own once a LOG.SET file is active,
  and announces its model and software version every 15 seconds.

No Home Assistant imports, so the tests exercise this offline and the client
runs from a terminal against a real pump just as well.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
import contextlib
from dataclasses import dataclass, field
import logging
import re

from nibe.coil import Coil, CoilData
from nibe.connection.nibegw import NibeGW
from nibe.exceptions import (
    NibeException,
    ReadIOException,
    WriteDeniedException,
    WriteIOException,
)
from nibe.heatpump import HeatPump, Model, ProductInfo

_LOGGER = logging.getLogger(__name__)

DEFAULT_READ_PORT = 9999
DEFAULT_WRITE_PORT = 10000

#: A register answers in about a second; three means the request or its answer
#: was lost on the way.
READ_TIMEOUT = 3.0
WRITE_TIMEOUT = 5.0
#: The pump sends its product message every 15 seconds.
PRODUCT_INFO_TIMEOUT = 20.0

#: Consecutive timeouts after which the gateway, not a register, is the problem.
UNREACHABLE_AFTER = 3

#: esphome-nibe relays what the pump sends on its own - LOG.SET values and the
#: product message - only to hosts that sent it a request in the last two
#: minutes. A read at least this often keeps Home Assistant on that list.
KEEPALIVE_INTERVAL = 60.0

#: Outdoor temperature (BT1): at this address in every F-series map, and read
#: to announce ourselves to the gateway before anything else.
ANNOUNCE_REGISTER = 40004

#: The factory setting for MODBUS 40's 32-bit word order (register 48852), used
#: when the pump could not be asked at start-up.
DEFAULT_WORD_SWAP = True

#: Raw 32-bit values that mean "no reading". The pump sign-extends the 16-bit
#: sentinel for accessories that are not fitted: an absent EME 20 energy meter
#: reads 0xFFFF8000.
SENTINELS_32: dict[str, frozenset[int]] = {
    "u32": frozenset({0xFFFFFFFF, 0xFFFF8000}),
    "s32": frozenset({-0x80000000, -0x8000}),
}

Value = float | int | None


class GatewayError(Exception):
    """Talking to the pump through the gateway failed."""


class GatewayTimeout(GatewayError):
    """The gateway or the pump did not answer in time."""


class GatewayRejected(GatewayError):
    """The pump refused a write, or the value is not one it can take."""


@dataclass
class _ExactCoilData(CoilData):
    """CoilData that hands the encoder a raw value computed exactly.

    The library turns a scaled value back into a raw one with int(value *
    factor), which truncates: 0.29 * 100 is 28.999999999999996 and would be
    written as 28. That never bites at factor 10, but a dozen F-series settings
    scale by 100.
    """

    raw: int = 0

    @property
    def raw_value(self) -> int:
        return self.raw


def value_from_coil_data(data: CoilData) -> Value:
    """A number for the entities, or None when the pump has no reading.

    Value tables come back from the library as upper-cased labels, while the
    entities look labels up by the raw number, so a label is turned back into
    its number here.
    """
    coil = data.coil
    value = data.value
    if value is None or coil.is_date:
        return None
    if coil.has_mappings:
        if not isinstance(value, str):
            return int(value)
        try:
            return int(coil.get_reverse_mapping_for(value))
        except (NibeException, AssertionError, ValueError):
            # A value the table does not list arrives as "UNKNOWN (5)".
            match = re.search(r"-?\d+", value)
            return int(match.group()) if match else None
    if isinstance(value, bool):
        return int(value)
    if not isinstance(value, int | float):
        return None
    sentinels = SENTINELS_32.get(coil.size)
    if sentinels and round(value * coil.factor) in sentinels:
        return None
    return value


def coil_data_for_write(coil: Coil, value: float) -> CoilData:
    """What to hand the library to write `value`: a scaled number, or a table value."""
    if not coil.is_writable:
        raise GatewayRejected(f"{coil.title} is read-only")
    if coil.is_date:
        raise GatewayRejected(f"{coil.title} is a date, which cannot be set here")
    if coil.has_mappings:
        try:
            return CoilData(coil, coil.get_mapping_for(int(value)))
        except (NibeException, ValueError) as err:
            raise GatewayRejected(f"{value} is not a value {coil.title} accepts") from err
    raw = round(float(value) * coil.factor)
    scaled = raw if coil.factor == 1 else raw / coil.factor
    return _ExactCoilData(coil, scaled, raw)


class GatewayClient:
    """One pump, reached through one NibeGW gateway."""

    def __init__(
        self,
        host: str,
        model: Model,
        read_port: int = DEFAULT_READ_PORT,
        write_port: int = DEFAULT_WRITE_PORT,
        word_swap: bool | None = None,
        *,
        connection_factory: Callable[..., NibeGW] = NibeGW,
    ) -> None:
        self.host = host
        self.model = model
        #: Named like the Modbus client's attributes, which the device page and
        #: diagnostics read without caring how the pump is reached.
        self.port = read_port
        self.write_port = write_port
        self.unit_id: int | None = None
        self._word_swap = word_swap
        self._connection_factory = connection_factory
        self._heatpump: HeatPump | None = None
        self._connection: NibeGW | None = None
        self._listeners: list[Callable[[int, Value], None]] = []

    @property
    def word_swap(self) -> bool | None:
        if self._heatpump is not None:
            return self._heatpump.word_swap
        return self._word_swap

    @property
    def started(self) -> bool:
        return self._connection is not None

    async def start(self) -> None:
        """Open the UDP socket, and learn the 32-bit word order if not known yet.

        The socket binds an ephemeral port: the gateway answers whichever port a
        request came from, so nothing on the Home Assistant host needs to be
        reserved, and a second integration listening on 9999 is no conflict.
        """
        heatpump = HeatPump(self.model)
        heatpump.word_swap = self._word_swap
        await heatpump.initialize()
        heatpump.subscribe(HeatPump.COIL_UPDATE_EVENT, self._on_coil_update)
        connection = self._connection_factory(
            heatpump=heatpump,
            remote_ip=self.host,
            remote_read_port=self.port,
            remote_write_port=self.write_port,
            listening_ip="0.0.0.0",
            listening_port=0,
            # Retrying is the poll schedule's job, not the library's: three
            # attempts of three seconds would stall every read behind it.
            read_retries=1,
            write_retries=1,
        )
        await connection.start()
        if heatpump.word_swap is None:
            _LOGGER.debug("Word order unknown after start-up; assuming the factory setting")
            heatpump.word_swap = DEFAULT_WORD_SWAP
            with contextlib.suppress(AttributeError):
                connection.coil_encoder.word_swap = DEFAULT_WORD_SWAP
        self._heatpump = heatpump
        self._connection = connection

    async def stop(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None:
            await connection.stop()

    def _require(self) -> NibeGW:
        if self._connection is None:
            raise GatewayError("The gateway connection is not started")
        return self._connection

    def coil(self, register: int) -> Coil:
        if self._heatpump is None:
            raise GatewayError("The gateway connection is not started")
        try:
            return self._heatpump.get_coil_by_address(register)
        except NibeException as err:
            raise GatewayError(f"Register {register} is not in the {self.model.name} map") from err

    async def read(self, register: int, timeout: float = READ_TIMEOUT) -> Value:
        """Read one register: a number, or None when the pump has no reading."""
        connection = self._require()
        coil = self.coil(register)
        try:
            data = await connection.read_coil(coil, timeout)
        except ReadIOException as err:
            raise GatewayTimeout(f"No answer for register {register}") from err
        except (NibeException, AssertionError) as err:
            raise GatewayError(f"Could not read register {register}: {err}") from err
        return value_from_coil_data(data)

    async def write(self, register: int, value: float) -> None:
        """Write one register. `value` is scaled, or a raw value from its table."""
        connection = self._require()
        data = coil_data_for_write(self.coil(register), value)
        try:
            await connection.write_coil(data, WRITE_TIMEOUT)
        except WriteDeniedException as err:
            raise GatewayRejected(f"The pump refused the write to register {register}") from err
        except WriteIOException as err:
            raise GatewayTimeout(f"No answer to the write to register {register}") from err
        except (NibeException, AssertionError) as err:
            raise GatewayRejected(f"Could not write register {register}: {err}") from err

    async def product_info(self, timeout: float = PRODUCT_INFO_TIMEOUT) -> ProductInfo:
        """The pump's own name for itself and its software version."""
        connection = self._require()
        try:
            return await connection.read_product_info(timeout)
        except NibeException as err:
            raise GatewayTimeout("The pump did not announce itself through the gateway") from err

    def add_listener(self, callback: Callable[[int, Value], None]) -> Callable[[], None]:
        """Call `callback(register, value)` for every value the gateway delivers.

        That is every answer to a read - including other clients' reads, which
        the gateway relays to everyone who asked recently - and every register
        the pump pushes from LOG.SET.
        """
        self._listeners.append(callback)

        def remove() -> None:
            with contextlib.suppress(ValueError):
                self._listeners.remove(callback)

        return remove

    def _on_coil_update(self, data: CoilData) -> None:
        value = value_from_coil_data(data)
        for listener in list(self._listeners):
            try:
                listener(data.coil.address, value)
            except Exception:  # one bad listener must not starve the others
                _LOGGER.exception("Listener failed for register %s", data.coil.address)


@dataclass
class PollSchedule:
    """Which registers are due, when every read costs a second.

    Measurements change on every cycle, settings rarely and counters slowly, so
    each gets its own interval. A register the pump pushes from LOG.SET stays
    fresh without ever being read. A register that fails backs off, doubling
    from one cycle up to an hour, so one bad register cannot eat the cycle.
    """

    base: float
    registers: dict[int, dict]
    last_seen: dict[int, float] = field(default_factory=dict)
    failures: dict[int, int] = field(default_factory=dict)
    retry_at: dict[int, float] = field(default_factory=dict)

    #: Settings change when someone changes them; ten cycles, and never more
    #: often than every ten minutes.
    SETTING_FACTOR = 10
    SETTING_MINIMUM = 600.0
    #: Running times, energy totals and start counts only ever creep upwards.
    COUNTER_FACTOR = 5
    COUNTER_MINIMUM = 300.0
    MAX_BACKOFF = 3600.0

    def interval(self, register: int) -> float:
        meta = self.registers.get(register, {})
        if meta.get("write"):
            return max(self.SETTING_FACTOR * self.base, self.SETTING_MINIMUM)
        unit = (meta.get("unit") or "").strip()
        title = meta.get("title", "").lower()
        if unit in ("h", "kWh", "Wh", "MWh") or "starts" in title:
            return max(self.COUNTER_FACTOR * self.base, self.COUNTER_MINIMUM)
        return self.base

    def seen(self, register: int, now: float) -> None:
        self.last_seen[register] = now
        self.failures.pop(register, None)
        self.retry_at.pop(register, None)

    def failed(self, register: int, now: float) -> None:
        count = self.failures.get(register, 0) + 1
        self.failures[register] = count
        self.retry_at[register] = now + min(self.base * 2 ** (count - 1), self.MAX_BACKOFF)

    def forget(self, register: int) -> None:
        self.last_seen.pop(register, None)
        self.failures.pop(register, None)
        self.retry_at.pop(register, None)

    def due(self, wanted: Iterable[int], now: float) -> list[int]:
        """Registers to read now, never-read first, then the most overdue.

        A quarter of a cycle of slack keeps a register read late in one cycle
        from sitting out the next one entirely.
        """
        slack = 0.25 * self.base
        ranked: list[tuple[float, int]] = []
        for register in wanted:
            retry = self.retry_at.get(register)
            if retry is not None and now < retry:
                continue
            seen = self.last_seen.get(register)
            if seen is None:
                ranked.append((float("inf"), register))
                continue
            lateness = (now - seen) - self.interval(register)
            if lateness + slack >= 0:
                ranked.append((lateness, register))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [register for _lateness, register in ranked]


@dataclass
class ProbeResult:
    """What one read of each register found."""

    values: dict[int, Value] = field(default_factory=dict)
    failed: set[int] = field(default_factory=set)

    @property
    def probed(self) -> set[int]:
        return set(self.values) | self.failed

    @property
    def reporting(self) -> set[int]:
        return {register for register, value in self.values.items() if value is not None}

    @property
    def silent(self) -> set[int]:
        """Answered with NIBE's "no reading": the hardware is not fitted."""
        return {register for register, value in self.values.items() if value is None}


async def probe(
    client: GatewayClient,
    registers: Iterable[int],
    progress: Callable[[int, int], None] | None = None,
) -> ProbeResult:
    """Read each register once, in order.

    A register that cannot be decoded is noted and skipped. A run of timeouts
    means the gateway itself is gone, and ends the probe with GatewayTimeout.
    """
    wanted = list(registers)
    result = ProbeResult()
    timeouts = 0
    for index, register in enumerate(wanted, 1):
        try:
            result.values[register] = await client.read(register)
            timeouts = 0
        except GatewayTimeout:
            result.failed.add(register)
            timeouts += 1
            if timeouts >= UNREACHABLE_AFTER:
                raise
        except GatewayError as err:
            _LOGGER.debug("Skipping register %s: %s", register, err)
            result.failed.add(register)
        if progress is not None:
            progress(index, len(wanted))
    return result


async def async_identify_gateway(
    host: str,
    read_port: int = DEFAULT_READ_PORT,
    write_port: int = DEFAULT_WRITE_PORT,
    *,
    connection_factory: Callable[..., NibeGW] = NibeGW,
    timeout: float = PRODUCT_INFO_TIMEOUT,
) -> ProductInfo | None:
    """Ask a gateway which pump sits behind it, without knowing the model yet.

    The product message needs no register map, so any F-series map will do to
    open the connection. The gateway only relays the product message to hosts
    that asked it something recently, so the outdoor temperature is read first:
    that also fails fast, in three seconds rather than twenty, when nothing is
    listening at `host`.
    """
    client = GatewayClient(
        host,
        Model.F1255,
        read_port,
        write_port,
        word_swap=DEFAULT_WORD_SWAP,
        connection_factory=connection_factory,
    )
    try:
        await client.start()
        await client.read(ANNOUNCE_REGISTER)
        return await client.product_info(timeout)
    except (GatewayError, OSError, NibeException) as err:
        _LOGGER.debug("No pump answered through %s: %s", host, err)
        return None
    finally:
        with contextlib.suppress(Exception):
            await client.stop()

