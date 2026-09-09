"""Polling and writing, driven by what the pump actually implements."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .codec import decode, encode_raw, unscale, word_count
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, SLOW_POLL_WARNING
from .discovery import (
    DiscoveryResult,
    RegisterDiscovery,
    Span,
    function_code,
    modbus_address,
    plan_spans,
)
from .modbus import FC_READ_HOLDING, ModbusError, ModbusTransportError, NibeModbusClient
from .registry import union_map

_LOGGER = logging.getLogger(__name__)


class NibeCoordinator(DataUpdateCoordinator[dict[int, float | int | None]]):
    """Polls only the registers that currently back an enabled entity.

    An S-series pump implements around 900 of the registers in the published
    maps, and reading them all takes several seconds per cycle. Entities declare
    which register they need as they are added, so a normal installation polls a
    few dozen and the rest cost nothing until someone enables them.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: NibeModbusClient,
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
        self.discovery = discovery
        self.registers = union_map()
        self._subscribed: set[int] = set()
        self._spans: list[Span] = []
        self._spans_stale = True
        self._write_lock = asyncio.Lock()

    # -- entity subscriptions -------------------------------------------

    def subscribe(self, register: int) -> None:
        """Ask for a register to be included in the poll cycle."""
        if register not in self._subscribed:
            self._subscribed.add(register)
            self._spans_stale = True

    def unsubscribe(self, register: int) -> None:
        self._subscribed.discard(register)
        self._spans_stale = True

    def _ensure_spans(self) -> None:
        if not self._spans_stale:
            return
        self._spans = plan_spans(
            self.registers,
            self._subscribed & self.discovery.present,
            present=self.discovery.present,
        )
        self._spans_stale = False
        _LOGGER.debug(
            "Poll plan: %d registers -> %d block reads", len(self._subscribed), len(self._spans)
        )

    # -- polling ---------------------------------------------------------

    async def _async_update_data(self) -> dict[int, float | int | None]:
        self._ensure_spans()
        if not self._spans:
            return {}

        started = time.monotonic()
        words: dict[tuple[int, int], int] = {}
        try:
            for span in self._spans:
                values = await self.client.read_registers(span.fc, span.start, span.count)
                for offset, value in enumerate(values):
                    words[(span.fc, span.start + offset)] = value
        except ModbusTransportError as err:
            raise UpdateFailed(f"Lost connection to the heat pump: {err}") from err
        except ModbusError as err:
            # A span went stale, most likely after a firmware or accessory
            # change. Force a re-plan so the next cycle skips the bad range.
            self._spans_stale = True
            raise UpdateFailed(f"Register layout changed: {err}") from err

        elapsed = time.monotonic() - started
        if elapsed > SLOW_POLL_WARNING:
            _LOGGER.warning(
                "Poll cycle took %.1fs for %d block reads; consider a longer scan "
                "interval or fewer enabled entities",
                elapsed,
                len(self._spans),
            )

        data: dict[int, float | int | None] = {}
        for register in self._subscribed:
            meta = self.registers.get(register)
            if meta is None:
                continue
            fc = function_code(register)
            address = modbus_address(register)
            needed = word_count(meta.get("size", "s16"))
            raw = [words.get((fc, address + i)) for i in range(needed)]
            if any(value is None for value in raw):
                continue
            data[register] = decode(meta, raw)  # type: ignore[arg-type]
        return data

    # -- writing ---------------------------------------------------------

    async def async_write(self, register: int, value: float) -> None:
        """Write a scaled value back to a holding register."""
        meta = self.registers.get(register)
        if meta is None:
            raise HomeAssistantError(f"Unknown register {register}")
        if not meta.get("write"):
            raise HomeAssistantError(f"Register {register} is read-only")
        if function_code(register) != FC_READ_HOLDING:
            raise HomeAssistantError(f"Register {register} is not writable over Modbus")

        size = meta.get("size", "s16")
        raw = unscale(value, meta.get("factor", 1))
        low, high = meta.get("min"), meta.get("max")
        if low is not None and raw < low:
            raise HomeAssistantError(f"{value} is below the minimum for register {register}")
        if high is not None and raw > high:
            raise HomeAssistantError(f"{value} is above the maximum for register {register}")

        address = modbus_address(register)
        payload = encode_raw(size, raw)
        async with self._write_lock:
            try:
                if len(payload) == 1:
                    await self.client.write_register(address, payload[0])
                else:
                    await self.client.write_registers(address, payload)
            except (ModbusError, ModbusTransportError) as err:
                raise HomeAssistantError(f"Could not write register {register}: {err}") from err

        # Reflect the new value immediately rather than waiting for the next poll.
        if self.data is not None:
            self.async_set_updated_data({**self.data, register: value})

    # -- rediscovery -------------------------------------------------------

    async def async_rescan(self) -> DiscoveryResult:
        """Probe the pump again, e.g. after fitting an accessory."""
        discovery = RegisterDiscovery(self.client)
        result = await discovery.run(self.registers)
        self.discovery = result
        self._spans_stale = True
        _LOGGER.info("Rescan complete: %s", result.summary())
        await self.async_request_refresh()
        return result
