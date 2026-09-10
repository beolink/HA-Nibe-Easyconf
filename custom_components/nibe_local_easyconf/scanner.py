"""Find NIBE pumps on the local network.

DHCP discovery handles the common case on its own, but it only fires when the
pump renews its lease, which can be hours away. This scans actively so setup
does not have to wait for that - and so it still works on networks where Home
Assistant cannot see DHCP traffic at all.

Port 502 alone proves nothing: solar inverters, energy meters and PLCs all sit
there. Every hit is therefore confirmed by reading the outdoor temperature
register, which any S-series pump answers and almost nothing else will.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
import ipaddress
import logging

from homeassistant.components import network
from homeassistant.core import HomeAssistant

from .codec import decode
from .const import DEFAULT_PORT, DEFAULT_UNIT_ID
from .discovery import function_code, modbus_address
from .modbus import NibeModbusClient
from .registry import async_union_map, union_map

_LOGGER = logging.getLogger(__name__)

#: Outdoor temperature (BT1). Present on every S-series model, and a plausible
#: reading from it is strong evidence that this really is a NIBE.
IDENTIFY_REGISTER = 30002

#: Anything outside this range is not an outdoor temperature, so whatever
#: answered is not a heat pump.
PLAUSIBLE_OUTDOOR = (-60.0, 60.0)

#: Refuse to enumerate networks larger than this; a /16 sweep is 65k probes.
MAX_HOSTS = 1024

#: Simultaneous connection attempts. The pump itself tolerates ~14 connections,
#: but most addresses scanned are not the pump, so this mainly bounds how hard
#: we hit the network.
CONCURRENCY = 64

CONNECT_TIMEOUT = 0.6


@dataclass(frozen=True)
class FoundPump:
    host: str
    outdoor_temperature: float

    @property
    def label(self) -> str:
        return f"{self.host} ({self.outdoor_temperature:.1f} °C ute)"


async def _port_open(host: str, port: int) -> bool:
    try:
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=CONNECT_TIMEOUT
        )
    except (OSError, TimeoutError):
        return False
    writer.close()
    with contextlib.suppress(OSError, TimeoutError):
        await writer.wait_closed()
    return True


async def async_identify(
    host: str,
    port: int,
    unit_id: int,
    registers: dict[int, dict] | None = None,
) -> FoundPump | None:
    """Confirm that `host` is a NIBE S-series pump, by reading a known register.

    `registers` lets the caller pass an already-loaded map so a sweep of 254
    addresses does not touch the register files at all.
    """
    client = NibeModbusClient(host, port, unit_id, timeout=4.0)
    try:
        await client.connect()
        words = await client.probe(
            function_code(IDENTIFY_REGISTER), modbus_address(IDENTIFY_REGISTER), 1
        )
    except Exception:  # a scan must not fail on one bad host
        return None
    finally:
        await client.close()

    if not words:
        return None
    if registers is None:
        registers = union_map()
    value = decode(registers[IDENTIFY_REGISTER], words)
    if value is None or not PLAUSIBLE_OUTDOOR[0] <= value <= PLAUSIBLE_OUTDOOR[1]:
        return None
    return FoundPump(host=host, outdoor_temperature=float(value))


async def async_candidate_hosts(hass: HomeAssistant) -> list[str]:
    """Addresses worth probing, taken from Home Assistant's own interfaces."""
    hosts: list[str] = []
    seen: set[str] = set()
    for adapter in await network.async_get_adapters(hass):
        if not adapter["enabled"]:
            continue
        for address in adapter["ipv4"]:
            try:
                interface = ipaddress.ip_interface(
                    f"{address['address']}/{address['network_prefix']}"
                )
            except ValueError:
                continue
            net = interface.network
            if net.is_loopback or net.num_addresses > MAX_HOSTS:
                _LOGGER.debug("Skipping %s: too large or loopback", net)
                continue
            for candidate in net.hosts():
                text = str(candidate)
                if text != str(interface.ip) and text not in seen:
                    seen.add(text)
                    hosts.append(text)
    return hosts


async def async_scan_hosts(
    hosts: list[str],
    port: int = DEFAULT_PORT,
    unit_id: int = DEFAULT_UNIT_ID,
    registers: dict[int, dict] | None = None,
) -> list[FoundPump]:
    """Probe a list of addresses and return the ones that are NIBE pumps."""
    if registers is None:
        registers = union_map()
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def check(host: str) -> FoundPump | None:
        async with semaphore:
            if not await _port_open(host, port):
                return None
        # Identification happens outside the semaphore so one slow Modbus
        # handshake does not hold up the rest of the sweep.
        return await async_identify(host, port, unit_id, registers)

    results = await asyncio.gather(*(check(host) for host in hosts))
    return [pump for pump in results if pump is not None]


async def async_find_pumps(
    hass: HomeAssistant,
    port: int = DEFAULT_PORT,
    unit_id: int = DEFAULT_UNIT_ID,
) -> list[FoundPump]:
    """Scan Home Assistant's own local networks for NIBE pumps."""
    registers = await async_union_map(hass)
    hosts = await async_candidate_hosts(hass)
    if not hosts:
        _LOGGER.warning("No suitable local network found to scan")
        return []
    _LOGGER.debug("Scanning %d addresses for Modbus on port %d", len(hosts), port)
    found = await async_scan_hosts(hosts, port, unit_id, registers)
    _LOGGER.info("Network scan found %d NIBE pump(s)", len(found))
    return found
