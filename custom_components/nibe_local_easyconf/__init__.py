"""Nibe Local Easyconf: NIBE S-series over Modbus TCP, configured by probing."""

from __future__ import annotations

from datetime import timedelta
import logging
import socket

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.loader import async_get_integration
import voluptuous as vol

from .codec import decode, word_count
from .const import (
    CONF_SERIAL,
    CONF_TRAITS,
    CONF_UNIT_ID,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIT_ID,
    DOMAIN,
    ENERGY_IN_REGISTER,
    ENERGY_OUT_REGISTER,
    FIRMWARE_REGISTER,
    PLATFORMS,
    SERVICE_IMPORT_HISTORY,
    SERVICE_RESCAN,
    is_core_register,
    platform_for,
)
from .coordinator import NibeCoordinator
from .cop import STORAGE_VERSION as COP_STORAGE_VERSION, CopTracker, cop_for_report
from .descriptions import friendly_name
from .discovery import (
    DiscoveryResult,
    RegisterDiscovery,
    function_code,
    modbus_address,
)
from .frontend import async_register_frontend, async_unregister_frontend
from .history import async_import_history
from .modbus import ModbusTransportError, NibeModbusClient
from .names import assign_names
from .registry import async_union_map
from .serial import parse_serial, serial_from_hostname
from .stats import async_setup_stats
from .stats_extra import ErrorCounter, build_extra
from .storage import async_load, async_remove, async_save

_LOGGER = logging.getLogger(__name__)

#: How often the COP tracker takes a sample of the energy counters. As in the
#: CTC integration: frequent enough that "yesterday" always has a sample 20-30
#: hours old, while the yearly figure keeps only one sample per day.
COP_SAMPLE_INTERVAL = timedelta(hours=6)

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
    _async_remove_moved_entities(hass, entry, registers, discovery.present)

    # Everything the entities read at construction time has to be in place
    # before the platforms are forwarded: names, and the device identity.
    language = entry.data.get("language", "sv")
    coordinator.entity_names = assign_names(
        registers, discovery.present, language, friendly_name
    )
    coordinator.serial = parse_serial(
        entry.data.get(CONF_SERIAL) or await _async_serial_by_reverse_dns(hass, client.host)
    )
    coordinator.firmware = await _async_read_firmware(client, registers, discovery)

    await coordinator.async_config_entry_first_refresh()

    # The coefficient of performance, from the pump's two lifetime energy
    # counters. Set up before the platforms so the COP sensors have it.
    if {ENERGY_OUT_REGISTER, ENERGY_IN_REGISTER} <= discovery.present:
        coordinator.cop = CopTracker(
            Store(hass, COP_STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.cop")
        )
        await coordinator.cop.async_load()

        async def _record_cop(_now=None) -> None:
            await coordinator.cop.async_record(coordinator.energy_out, coordinator.energy_in)

        await _record_cop()
        entry.async_on_unload(
            async_track_time_interval(hass, _record_cop, COP_SAMPLE_INTERVAL)
        )

        # Earlier history of the same counters, if Home Assistant recorded any
        # (myUplink, for one, does). Once, after startup, when the recorder is
        # certain to be up; the service runs it again on request.
        if coordinator.cop.history is None:

            async def _import(_hass: HomeAssistant) -> None:
                if await async_import_history(hass, coordinator, DOMAIN):
                    coordinator.async_update_listeners()

            entry.async_on_unload(async_at_started(hass, _import))

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options))
    _register_services(hass)

    # Anonymous daily report. On unless the user switches it off in the
    # options, and it never opens a Modbus connection of its own: everything
    # in it is either a count the coordinator already has or a fixed slug.
    # See stats_extra.py for exactly what is sent.
    integration = await async_get_integration(hass, DOMAIN)
    failures = ErrorCounter()

    def _stats_extra() -> dict:
        cop_day, cop_year, cop_lifetime = cop_for_report(
            coordinator.cop, coordinator.energy_out, coordinator.energy_in
        )
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
            firmware=coordinator.firmware,
            serial=coordinator.serial.serial if coordinator.serial else None,
            cop_day=cop_day,
            cop_year=cop_year,
            cop_lifetime=cop_lifetime,
        )

    coordinator.stats = await async_setup_stats(
        hass, entry, DOMAIN, str(integration.version), extra=_stats_extra
    )

    # The "NIBE" sidebar page and the dashboard card. Once per Home Assistant,
    # however many pumps there are; see frontend.py for why a panel rather
    # than a generated dashboard.
    await async_register_frontend(hass, str(integration.version))
    return True


def _async_remove_moved_entities(
    hass: HomeAssistant, entry: ConfigEntry, registers: dict, present: set[int]
) -> None:
    """Keep the entity registry in step with the current register policy.

    Drops entries left behind when a register changes platform, and enables
    entities that have since joined the default set.

    A register that gains a value table moves from number to select (NIBE's own
    tables did that to five settings). The registry keys an entity on its
    platform as well as its unique id, so the old number would otherwise stay
    behind as a permanently unavailable duplicate the user has to delete.
    """
    registry = er.async_get(hass)
    for register in present:
        meta = registers.get(register)
        if meta is None:
            continue
        unique_id = f"{entry.entry_id}-{register}"
        current = platform_for(meta)
        for platform in PLATFORMS:
            if platform == current:
                continue
            if entity_id := registry.async_get_entity_id(platform, DOMAIN, unique_id):
                _LOGGER.debug("Register %s moved to %s; removing %s", register, current, entity_id)
                registry.async_remove(entity_id)

        # Home Assistant applies "enabled by default" only when an entity is
        # first created, so a register that joins the default set later - the
        # two energy counters did - would stay switched off on every existing
        # installation. Re-enable it, but only where this integration was the
        # one that disabled it: anything the user switched off stays off.
        if not is_core_register(meta.get("title", ""), meta):
            continue
        entity_id = registry.async_get_entity_id(current, DOMAIN, unique_id)
        entity = registry.async_get(entity_id) if entity_id else None
        if entity is not None and entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION:
            _LOGGER.debug("Register %s is now enabled by default; enabling %s", register, entity_id)
            registry.async_update_entity(entity_id, disabled_by=None)


async def _async_serial_by_reverse_dns(hass: HomeAssistant, host: str) -> str | None:
    """The pump's serial from its network name, for entries made by hand.

    Entries created through DHCP discovery already carry the serial; this
    covers the scan and manual paths, and entries from before it was stored.
    """
    try:
        name, _aliases, _addrs = await hass.async_add_executor_job(
            socket.gethostbyaddr, host
        )
    except (OSError, UnicodeError):
        return None
    return serial_from_hostname(name)


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
        still_loaded = [
            other
            for other in hass.config_entries.async_loaded_entries(DOMAIN)
            if other.entry_id != entry.entry_id
        ]
        if not still_loaded:
            async_unregister_frontend(hass)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await async_remove(hass, entry.entry_id)
    await Store(hass, COP_STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.cop").async_remove()


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

    async def _import_history(call: ServiceCall) -> dict:
        """Import earlier energy history into the COP tracker, again if need be."""
        entry_ids = call.data.get("entry_id")
        results = {}
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            if entry_ids and entry.entry_id not in entry_ids:
                continue
            coordinator: NibeCoordinator = entry.runtime_data
            imported = await async_import_history(hass, coordinator, DOMAIN)
            if imported:
                coordinator.async_update_listeners()
            results[entry.entry_id] = imported or {"production": None, "consumption": None}
        return results

    hass.services.async_register(
        DOMAIN,
        SERVICE_IMPORT_HISTORY,
        _import_history,
        schema=vol.Schema({vol.Optional("entry_id"): vol.All(cv.ensure_list, [cv.string])}),
        supports_response=SupportsResponse.OPTIONAL,
    )
