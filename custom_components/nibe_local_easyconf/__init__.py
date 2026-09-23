"""Nibe Local Easyconf: NIBE S-series over Modbus TCP, configured by probing."""

from __future__ import annotations

from datetime import timedelta
import logging
import socket

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.loader import async_get_integration
from nibe.exceptions import NibeException
import voluptuous as vol

from . import fseries
from .codec import decode, word_count
from .const import (
    CONF_CONNECTION,
    CONF_FIRMWARE,
    CONF_MODEL,
    CONF_PRODUCT,
    CONF_READ_PORT,
    CONF_SERIAL,
    CONF_TRAITS,
    CONF_UNIT_ID,
    CONF_WORD_SWAP,
    CONF_WRITE_PORT,
    CONNECTION_NIBEGW,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIT_ID,
    DOMAIN,
    ENERGY_IN_REGISTER,
    ENERGY_OUT_REGISTER,
    FIRMWARE_REGISTER,
    GATEWAY_PROBE_REGISTER,
    PLATFORMS,
    SERVICE_IMPORT_HISTORY,
    SERVICE_RESCAN,
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
from .gateway import (
    DEFAULT_READ_PORT,
    DEFAULT_WRITE_PORT,
    GatewayClient,
    GatewayError,
    probe,
)
from .gateway_coordinator import NibeGatewayCoordinator, gateway_discovery
from .history import async_import_history
from .modbus import ModbusTransportError, NibeModbusClient
from .names import assign_names
from .power import STORAGE_VERSION as POWER_STORAGE_VERSION, ElectricityCounter
from .registry import async_model_map, async_union_map
from .serial import parse_serial, serial_from_hostname
from .stats import async_setup_stats, async_stop_stats
from .stats_extra import ErrorCounter, build_extra
from .storage import async_load, async_remove, async_save, async_saved_version
from .translations_extra import entity_language

_LOGGER = logging.getLogger(__name__)

#: How often the COP tracker takes a sample of the energy counters. As in the
#: CTC integration: frequent enough that "yesterday" always has a sample 20-30
#: hours old, while the yearly figure keeps only one sample per day.
COP_SAMPLE_INTERVAL = timedelta(hours=6)

type NibeConfigEntry = ConfigEntry[NibeCoordinator]

#: Failed poll cycles already reported, per entry. Outside the coordinator,
#: which each set-up attempt creates anew.
_FAILURES: dict[str, ErrorCounter] = {}


def _scan_interval(entry: ConfigEntry) -> int:
    return entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )


def _stats_extra_for(entry: NibeConfigEntry) -> dict:
    """The integration's part of the anonymous daily report.

    Resolved when the report is built, not when it is armed. A pump that does
    not answer makes the set-up raise, and Home Assistant retries it for as
    long as that lasts; the report then has to say "installed and unreachable"
    rather than nothing at all. It never opens a Modbus connection of its own:
    everything in it is either a count the coordinator already has or a fixed
    slug. See stats_extra.py for exactly what is sent.
    """
    failures = _FAILURES.setdefault(entry.entry_id, ErrorCounter())
    coordinator: NibeCoordinator | None = getattr(entry, "runtime_data", None)
    model = entry.data.get("model")
    traits = set(entry.data.get(CONF_TRAITS) or [])
    if coordinator is None:
        # Set-up has not finished. What the config entry knows is sent, and a
        # read failure is recorded so a pump that never answers is visible
        # rather than silent.
        return build_extra(
            model,
            traits=traits,
            scan_interval_s=_scan_interval(entry),
            read_failures=1,
            serial=entry.data.get(CONF_SERIAL),
        )
    cop_day, cop_year, cop_lifetime = cop_for_report(
        coordinator.cop, coordinator.energy_out, coordinator.energy_in
    )
    return build_extra(
        model,
        traits=traits,
        registers_present=len(coordinator.discovery.present),
        registers_reporting=len(coordinator.discovery.reporting),
        registers_absent=len(coordinator.discovery.absent),
        entities_enabled=coordinator.subscribed_count,
        block_reads=coordinator.block_reads,
        scan_interval_s=_scan_interval(entry),
        read_failures=failures.delta(coordinator.read_failures),
        firmware=coordinator.firmware,
        serial=coordinator.serial.serial if coordinator.serial else None,
        cop_day=cop_day,
        cop_year=cop_year,
        cop_lifetime=cop_lifetime,
    )


async def _async_arm_statistics(hass: HomeAssistant, entry: NibeConfigEntry) -> None:
    """Arm the daily report before the first Modbus call.

    Home Assistant runs an entry's on-unload callbacks after every failed
    set-up attempt and retries for as long as the pump stays away, so a
    reporter armed at the end of a successful set-up would go quiet exactly
    then. Stopped only from async_unload_entry, which a failed attempt never
    reaches. On unless the user switches it off in the options.
    """
    try:
        integration = await async_get_integration(hass, DOMAIN)
        await async_setup_stats(
            hass, entry, DOMAIN, str(integration.version),
            extra=lambda: _stats_extra_for(entry),
        )
    except Exception:  # statistics must never break a set-up
        _LOGGER.debug("Could not arm the statistics reporter", exc_info=True)


async def _async_cached_discovery(
    hass: HomeAssistant, entry: ConfigEntry, version: str | None = None
) -> tuple[DiscoveryResult | None, bool]:
    """The register scan from an earlier start, and whether it is out of date.

    On the first start after setup the config flow's scan is adopted, then
    moved out of the config entry so it is not carried around in
    core.config_entries on every future start.

    A scan made by an older version of this integration is stale: what is worth
    reading is this integration's opinion as much as the pump's, and a release
    that starts reading registers it did not read before would otherwise only
    show them on installations set up after it. The caller scans again, and
    falls back to this one if the pump does not answer just then.
    """
    discovery = await async_load(hass, entry.entry_id)
    stale = discovery is not None and await async_saved_version(hass, entry.entry_id) != version
    if discovery is None and "discovery" in entry.data:
        cached = entry.data["discovery"]
        probed = cached.get("probed")
        discovery = DiscoveryResult(
            present=set(cached.get("present", [])),
            reporting=set(cached.get("reporting", [])),
            absent=set(cached.get("absent", [])),
            probed=None if probed is None else set(probed),
        )
        await async_save(hass, entry.entry_id, discovery, version)
        remaining = {k: v for k, v in entry.data.items() if k != "discovery"}
        hass.config_entries.async_update_entry(entry, data=remaining)
    return discovery, stale


async def async_setup_entry(hass: HomeAssistant, entry: NibeConfigEntry) -> bool:
    await _async_arm_statistics(hass, entry)

    if entry.data.get(CONF_CONNECTION) == CONNECTION_NIBEGW:
        return await _async_setup_gateway_entry(hass, entry)

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
    version = str((await async_get_integration(hass, DOMAIN)).version)
    cached, stale = await _async_cached_discovery(hass, entry, version)
    discovery = None if stale else cached
    if discovery is None:
        _LOGGER.info(
            "%s; reading the registers of %s",
            "The integration was updated" if stale else "No cached register scan",
            entry.data[CONF_HOST],
        )
        try:
            discovery = await RegisterDiscovery(client).run(registers)
        except ModbusTransportError as err:
            if cached is None:
                await client.close()
                raise ConfigEntryNotReady(str(err)) from err
            # The pump is quiet at this moment; the scan from before is still
            # true about the pump, and the next start tries again.
            _LOGGER.warning("Could not read the registers again (%s); keeping the last scan", err)
            discovery = cached
        else:
            await async_save(hass, entry.entry_id, discovery, version)
    _LOGGER.debug("Register discovery for %s: %s", entry.title, discovery.summary())

    coordinator = NibeCoordinator(
        hass, entry, client, discovery, _scan_interval(entry), registers=registers
    )
    _async_remove_moved_entities(
        hass, entry, registers, discovery.present, coordinator.default_enabled
    )

    # Everything the entities read at construction time has to be in place
    # before the platforms are forwarded: names, and the device identity.
    language = entity_language(hass.config.language, entry.data.get("language"))
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
        await _async_set_up_cop(hass, entry, coordinator, import_history=True)

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options))
    _register_services(hass)

    # The "NIBE" sidebar page and the dashboard card. Once per Home Assistant,
    # however many pumps there are; see frontend.py for why a panel rather
    # than a generated dashboard.
    integration = await async_get_integration(hass, DOMAIN)
    await async_register_frontend(hass, str(integration.version))
    return True


async def _async_setup_gateway_entry(hass: HomeAssistant, entry: NibeConfigEntry) -> bool:
    """Set up an F-series pump reached through a NibeGW gateway.

    The same shape as the Modbus TCP set-up, with three differences: the model
    comes from the pump's own product message rather than a pick list, the scan
    covers only the registers shown by default, and the software version is
    the product message's rather than a register's.
    """
    product = fseries.identify_product(entry.data.get(CONF_PRODUCT))
    model = (
        product.model
        if product is not None
        else fseries.F_SERIES_MODELS.get(str(entry.data.get(CONF_MODEL, "")).upper())
    )
    if model is None:
        raise ConfigEntryError(f"Unsupported F-series model {entry.data.get(CONF_MODEL)!r}")

    registers = await async_model_map(hass, model)
    client = GatewayClient(
        entry.data[CONF_HOST],
        model,
        entry.data.get(CONF_READ_PORT, DEFAULT_READ_PORT),
        entry.data.get(CONF_WRITE_PORT, DEFAULT_WRITE_PORT),
        word_swap=entry.data.get(CONF_WORD_SWAP),
    )
    try:
        await client.start()
        # One read proves both the gateway and the pump behind it are there.
        outdoor = await client.read(GATEWAY_PROBE_REGISTER)
    except (GatewayError, OSError, NibeException) as err:
        await client.stop()
        raise ConfigEntryNotReady(
            f"No answer through the NibeGW gateway at {client.host}: {err}"
        ) from err

    try:
        version = str((await async_get_integration(hass, DOMAIN)).version)
        cached, stale = await _async_cached_discovery(hass, entry, version)
        discovery = None if stale else cached
        if discovery is None:
            # Every register costs about a second through the gateway, so this
            # is a minute and a half - once, after an update that may have
            # widened what is worth reading.
            _LOGGER.info(
                "%s; reading the defaults through %s",
                "The integration was updated" if stale else "No cached register scan",
                client.host,
            )
            try:
                result = await probe(client, fseries.default_registers(registers))
            except (GatewayError, OSError, NibeException) as err:
                if cached is None:
                    raise
                # A gateway that goes quiet during the scan must not cost the
                # pump its entities: the scan from before still describes it,
                # and the next start tries again.
                _LOGGER.warning(
                    "Could not read the registers again (%s); keeping the last scan", err
                )
                discovery = cached
            else:
                discovery = gateway_discovery(registers, result)
                await async_save(hass, entry.entry_id, discovery, version)
        _LOGGER.debug("Register discovery for %s: %s", entry.title, discovery.summary())

        coordinator = NibeGatewayCoordinator(
            hass, entry, client, registers, discovery, _scan_interval(entry)
        )
        coordinator.seed(GATEWAY_PROBE_REGISTER, outdoor)
        coordinator.async_start_listening()
        _async_remove_moved_entities(
            hass, entry, registers, discovery.present, coordinator.default_enabled
        )
        language = entity_language(hass.config.language, entry.data.get("language"))
        coordinator.entity_names = assign_names(
            registers, discovery.present, language, friendly_name
        )
        coordinator.serial = parse_serial(
            entry.data.get(CONF_SERIAL) or await _async_serial_by_reverse_dns(hass, client.host)
        )
        coordinator.firmware = entry.data.get(CONF_FIRMWARE)
        await coordinator.async_config_entry_first_refresh()

        # The electricity meter the F-series does not have, built from the
        # power it reports, and with it the coefficient of performance. The
        # pump's own heat meters are the other half; without them, or without
        # the compressor's power, there is nothing to divide.
        heat_meters = set(fseries.HEAT_METERS) & discovery.reporting
        own_electricity = set(fseries.CONSUMED_ENERGY) & discovery.reporting
        if heat_meters and (own_electricity or fseries.COMPRESSOR_POWER in discovery.reporting):
            counter = None
            if not own_electricity:
                # The pump does not count its own electricity; the power it
                # reports is added up instead. See power.py.
                counter = ElectricityCounter(
                    Store(hass, POWER_STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.power")
                )
                await counter.async_load()
                entry.async_on_unload(
                    async_track_time_interval(hass, _save_counter(counter), POWER_SAVE_INTERVAL)
                )
            coordinator.start_counting(counter)
            if counter is not None and not counter.counting_heat:
                # The pump answers its heat meters and never moves them; see
                # power.py. Three figures that can never be worked out are
                # worse than none, so they are left out until it does.
                _LOGGER.warning(
                    "%s answers its heat meters but has not moved them through %.0f kWh of "
                    "electricity, so it is not measuring the heat it delivers and there is "
                    "nothing to divide. NIBE's energy metering needs a flow meter (EMK 300 "
                    "or EMK 500); with one fitted, restart to get the COP sensors",
                    entry.title,
                    counter.kwh,
                )
                _async_remove_cop_entities(hass, entry)
            else:
                await _async_set_up_cop(hass, entry, coordinator, import_history=False)
    except BaseException:
        await client.stop()
        raise

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options))
    _register_services(hass)
    integration = await async_get_integration(hass, DOMAIN)
    await async_register_frontend(hass, str(integration.version))
    entry.async_create_background_task(
        hass, _async_follow_software_version(hass, entry, coordinator), f"{DOMAIN} product message"
    )
    return True


#: How often the counted kilowatt hours are written down. Often enough that a
#: restart loses minutes rather than hours, seldom enough to be kind to the
#: disk; what happens in between is carried by the last reading, which is
#: stored with them.
POWER_SAVE_INTERVAL = timedelta(minutes=5)


def _save_counter(counter: ElectricityCounter):
    """A callback that writes the counted kilowatt hours down."""

    async def _save(_now=None) -> None:
        await counter.async_save()

    return _save


@callback
def _async_remove_cop_entities(hass: HomeAssistant, entry: NibeConfigEntry) -> None:
    """Take away the coefficient of performance sensors of a pump that cannot
    have one. Left behind they would sit unavailable for ever, which says less
    than nothing; they are registered again the day the pump starts counting.
    """
    registry = er.async_get(hass)
    for span in ("day", "year", "lifetime"):
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}-cop-{span}"
        )
        if entity_id is not None:
            registry.async_remove(entity_id)


async def _async_set_up_cop(
    hass: HomeAssistant, entry: NibeConfigEntry, coordinator, *, import_history: bool
) -> None:
    """Start the coefficient of performance for a pump that has both figures.

    Set up before the platforms, so the COP sensors find it. `import_history`
    is for the S-series only: its counters have been running since the pump was
    installed, and Home Assistant may have recorded them before this
    integration existed. The F-series counts from today, so there is nothing
    earlier to find.
    """
    coordinator.cop = CopTracker(
        Store(hass, COP_STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.cop")
    )
    await coordinator.cop.async_load()

    async def _record_cop(_now=None) -> None:
        await coordinator.cop.async_record(coordinator.energy_out, coordinator.energy_in)

    await _record_cop()
    entry.async_on_unload(async_track_time_interval(hass, _record_cop, COP_SAMPLE_INTERVAL))

    if import_history and coordinator.cop.history is None:
        # Earlier history of the same counters, if Home Assistant recorded any
        # (myUplink, for one, does). Once, after startup, when the recorder is
        # certain to be up; the service runs it again on request.

        async def _import(_hass: HomeAssistant) -> None:
            if await async_import_history(hass, coordinator, DOMAIN):
                coordinator.async_update_listeners()

        entry.async_on_unload(async_at_started(hass, _import))


async def _async_follow_software_version(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: NibeGatewayCoordinator
) -> None:
    """Show the software version the pump announces now, not the one at setup.

    The device registry is updated rather than the config entry: an entry
    update would trigger the reload listener.
    """
    try:
        info = await coordinator.client.product_info()
    except GatewayError:
        return
    version = info.firmware_version
    if not version or version == coordinator.firmware:
        return
    coordinator.firmware = version
    registry = dr.async_get(hass)
    # Looked up among this entry's own devices: async_get_device by identifier
    # is deprecated from Home Assistant 2026.9, and its replacement is too new
    # for the oldest release this integration supports.
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if (DOMAIN, entry.entry_id) in device.identifiers:
            registry.async_update_device(device.id, sw_version=str(version))


def _async_remove_moved_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    registers: dict,
    present: set[int],
    default_enabled,
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
        if not default_enabled(register, meta):
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
        # Only here, never from an on-unload callback: those also run when a
        # set-up attempt fails, and the report has to survive that.
        await async_stop_stats(hass, entry, DOMAIN)
        # The kilowatt hours counted since the last write, so a restart picks
        # up where the pump left off rather than five minutes behind it.
        counter = getattr(coordinator, "electricity", None)
        if counter is not None:
            await counter.async_save()
        await coordinator.async_close()
        still_loaded = [
            other
            for other in hass.config_entries.async_loaded_entries(DOMAIN)
            if other.entry_id != entry.entry_id
        ]
        if not still_loaded:
            async_unregister_frontend(hass)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    # An entry removed while its set-up was still being retried was never
    # unloaded through async_unload_entry, so its reporter may still be armed.
    await async_stop_stats(hass, entry, DOMAIN)
    _FAILURES.pop(entry.entry_id, None)
    await async_remove(hass, entry.entry_id)
    await Store(hass, COP_STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.cop").async_remove()
    await Store(hass, POWER_STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.power").async_remove()


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
            version = str((await async_get_integration(hass, DOMAIN)).version)
            await async_save(hass, entry.entry_id, result, version)
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
