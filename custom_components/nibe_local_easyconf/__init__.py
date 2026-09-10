"""Nibe Local Easyconf: NIBE S-series over Modbus TCP, configured by probing."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.loader import async_get_integration
import voluptuous as vol

from .codec import decode, word_count
from .const import (
    CONF_TRAITS,
    CONF_UNIT_ID,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIT_ID,
    DOMAIN,
    FIRMWARE_REGISTER,
    PLATFORMS,
    SERVICE_RESCAN,
)
from .coordinator import NibeCoordinator
from .discovery import (
    DiscoveryResult,
    RegisterDiscovery,
    function_code,
    modbus_address,
)
from .modbus import ModbusTransportError, NibeModbusClient
from .registry import async_union_map
from .stats import async_setup_stats
from .stats_extra import ErrorCounter, build_extra
from .storage import async_load, async_remove, async_save

_LOGGER = logging.getLogger(__name__)

type NibeConfigEntry = ConfigEntry[NibeCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: NibeConfigEntry) -> bool:
    client = NibeModbusClient(
        host=entry.data[CONF_HOST],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        unit_id=entry.data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID),
    )
    try:
        await client.connect()
    except ModbusTransportError as err:
        raise ConfigEntryNotReady(str(err)) from err

    registers = await async_union_map(hass)
    discovery = await async_load(hass, entry.entry_id)
    if discovery is None and "discovery" in entry.data:
        # First start after setup: adopt the scan the config flow already did,
        # then move it out of the config entry so it is not carried around in
        # core.config_entries on every future start.
        cached = entry.data["discovery"]
        discovery = DiscoveryResult(
            present=set(cached.get("present", [])),
            reporting=set(cached.get("reporting", [])),
            absent=set(cached.get("absent", [])),
        )
        await async_save(hass, entry.entry_id, discovery)
        remaining = {k: v for k, v in entry.data.items() if k != "discovery"}
        hass.config_entries.async_update_entry(entry, data=remaining)
    if discovery is None:
        _LOGGER.info("No cached register scan; probing %s", entry.data[CONF_HOST])
        try:
            discovery = await RegisterDiscovery(client).run(registers)
        except ModbusTransportError as err:
            await client.close()
            raise ConfigEntryNotReady(str(err)) from err
        await async_save(hass, entry.entry_id, discovery)
    _LOGGER.debug("Register discovery for %s: %s", entry.title, discovery.summary())

    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    coordinator = NibeCoordinator(
        hass, entry, client, discovery, scan_interval, registers=registers
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options))
    _register_services(hass)

    # Anonymous daily report. On unless the user switches it off in the
    # options, and it never opens a Modbus connection of its own: everything
    # in it is either a count the coordinator already has or a fixed slug.
    # See stats_extra.py for exactly what is sent.
    firmware = await _async_read_firmware(client, registers, discovery)
    integration = await async_get_integration(hass, DOMAIN)
    failures = ErrorCounter()

    def _stats_extra() -> dict:
        return build_extra(
            entry.data.get("model"),
            traits=set(entry.data.get(CONF_TRAITS) or []),
            registers_present=len(coordinator.discovery.present),
            registers_reporting=len(coordinator.discovery.reporting),
            registers_absent=len(coordinator.discovery.absent),
            entities_enabled=coordinator.subscribed_count,
            block_reads=coordinator.block_reads,
            scan_interval_s=scan_interval,
            read_failures=failures.delta(coordinator.read_failures),
            firmware=firmware,
        )

    coordinator.stats = await async_setup_stats(
        hass, entry, DOMAIN, str(integration.version), extra=_stats_extra
    )
    return True


async def _async_read_firmware(client, registers, discovery) -> int | None:
    """Read the control board's software version once, at setup.

    Read here rather than polled: it changes only when the pump is updated, and
    keeping it out of the poll plan costs one fewer request every cycle.
    """
    if FIRMWARE_REGISTER not in discovery.present:
        return None
    meta = registers.get(FIRMWARE_REGISTER)
    if meta is None:
        return None
    try:
        words = await client.probe(
            function_code(FIRMWARE_REGISTER),
            modbus_address(FIRMWARE_REGISTER),
            word_count(meta.get("size", "s16")),
        )
    except ModbusTransportError:
        return None
    return None if words is None else decode(meta, words)


async def async_unload_entry(hass: HomeAssistant, entry: NibeConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator = entry.runtime_data
        if getattr(coordinator, "stats", None):
            await coordinator.stats.async_stop()
        await coordinator.client.close()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await async_remove(hass, entry.entry_id)


async def _async_reload_on_options(hass: HomeAssistant, entry: NibeConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_RESCAN):
        return

    async def _rescan(call: ServiceCall) -> None:
        """Re-probe the pump, e.g. after fitting an accessory."""
        entry_ids = call.data.get("entry_id")
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if entry_ids:
            entries = [entry for entry in entries if entry.entry_id in entry_ids]
        for entry in entries:
            coordinator: NibeCoordinator = entry.runtime_data
            result = await coordinator.async_rescan()
            await async_save(hass, entry.entry_id, result)
            # Newly discovered registers need entities, which are created at
            # platform setup, so reload the entry to pick them up.
            hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESCAN,
        _rescan,
        schema=vol.Schema({vol.Optional("entry_id"): vol.All(cv.ensure_list, [cv.string])}),
    )
