"""The F-series path through Home Assistant itself: setup flow, set-up, polling.

Runs against a real Home Assistant core from pytest-homeassistant-custom-component
and skips where that is not installed (the CI job runs the offline suite). The
gateway is the stand-in from test_gateway.py, answering with the readings of the
F1255-16 CU this was developed against.

    pip install pytest-homeassistant-custom-component
    pytest -o asyncio_mode=auto tests/test_gateway_homeassistant.py
"""

from __future__ import annotations

from datetime import timedelta
from ipaddress import ip_address
import time
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import (
    SOURCE_DHCP,
    SOURCE_USER,
    SOURCE_ZEROCONF,
    ConfigEntryState,
)
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from nibe.exceptions import ReadTimeoutException
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.nibe_local_easyconf import fseries, gateway as gateway_module
from custom_components.nibe_local_easyconf.const import DOMAIN, platform_for

from .test_gateway import FakeNibeGW

HOST = "10.0.50.47"
#: A made-up serial with the F1255's article number: never a real machine's.
SERIAL = "06505916100001"

#: What the F1255-16 CU answered for the registers shown by default. No room
#: sensor, no cooling and no flow sensor: those three read "no value".
READINGS: dict[int, object] = {
    40004: 14.2, 40008: 30.6, 40012: 30.2, 40013: 56.6, 40014: 51.4, 40015: 8.2,
    40016: 8.1, 40017: 30.2, 40018: 38.9, 40019: 27.3, 40022: 26.5, 40033: None,
    40045: None, 40067: 13.9, 40071: 29.9, 40072: None, 43005: 100.0, 43009: 22.6,
    43081: 135.2, 43084: 0.0, 43086: "HOT WATER", 43136: 35.0, 43141: 2.31,
    43239: 36.5, 43416: 86220, 43420: 43263, 43424: 10540, 43427: "RUNNING",
    43437: 32, 43439: 91, 44298: 246.8, 44300: 650.7, 45001: 0, 45171: 0,
    47007: 0, 47011: 0, 47041: "ECONOMY", 47137: "AUTO", 47212: 0.0,
    47370: "OFF", 47371: "ON", 48043: "ACTIVE", 48132: "OFF", 48852: "ON",
}


class PumpGateway(FakeNibeGW):
    """The stand-in, answering with the development unit's readings."""

    def __init__(self, heatpump, remote_ip, **kwargs):
        super().__init__(heatpump, remote_ip, **kwargs)
        self.values.update(READINGS)

    async def write_coil(self, coil_data, timeout=5):
        await super().write_coil(coil_data, timeout)
        # The pump stores what it accepted; a read-back then returns it.
        self.values[coil_data.coil.address] = coil_data.value


class DeadGateway(PumpGateway):
    async def read_coil(self, coil, timeout=5):
        raise ReadTimeoutException("nothing answers")


def _client_factory(connection):
    """GatewayClient, but on the stand-in instead of a UDP socket."""

    class Client(gateway_module.GatewayClient):
        def __init__(self, *args, **kwargs):
            kwargs["connection_factory"] = connection
            super().__init__(*args, **kwargs)

    return Client


async def _identify(host, read_port=9999, write_port=10000, **kwargs):
    return await gateway_module.async_identify_gateway(
        host, read_port, write_port, connection_factory=PumpGateway
    )


@pytest.fixture(autouse=True)
def _integration(hass, enable_custom_integrations):
    """Everything the integration touches outside the pump, stubbed."""
    # Declared dependencies that need a browser frontend build to set up.
    hass.config.components.update({"frontend", "http", "panel_custom", "network"})
    FakeNibeGW.instances.clear()
    client = _client_factory(PumpGateway)
    with (
        patch(f"custom_components.{DOMAIN}.GatewayClient", client),
        patch(f"custom_components.{DOMAIN}.config_flow.GatewayClient", client),
        patch(f"custom_components.{DOMAIN}.config_flow.async_identify_gateway", _identify),
        patch(f"custom_components.{DOMAIN}.async_register_frontend", AsyncMock()),
        patch(f"custom_components.{DOMAIN}.async_unregister_frontend"),
        patch(f"custom_components.{DOMAIN}.async_setup_stats", AsyncMock()),
        patch(f"custom_components.{DOMAIN}.async_stop_stats", AsyncMock()),
        patch(
            f"custom_components.{DOMAIN}._async_serial_by_reverse_dns",
            AsyncMock(return_value=None),
        ),
        patch(
            f"custom_components.{DOMAIN}.config_flow.NibeConfigFlow._async_serial_by_reverse_dns",
            AsyncMock(return_value=None),
        ),
    ):
        yield


def _entry_data(**overrides):
    data = {
        "connection": "nibegw",
        "host": HOST,
        "read_port": 9999,
        "write_port": 10000,
        "model": "f1255",
        "model_label": "NIBE F1255-16 CU",
        "product": "F1255-16 CU",
        "firmware": 9721,
        "word_swap": True,
        "scan_interval": 60,
        "language": "sv",
        "traits": ["ground_source", "hot_water"],
        "serial": SERIAL,
    }
    data.update(overrides)
    return data


async def _finish_progress(hass, result):
    """Let a progress step's task run, then move the flow on.

    Against the stand-in the scan can finish inside the request that started
    it, in which case the flow is already past the progress step.
    """
    if result["type"] is not FlowResultType.SHOW_PROGRESS:
        return result
    await hass.async_block_till_done()
    return await hass.config_entries.flow.async_configure(result["flow_id"])


# ------------------------------------------------------------ the setup flow


async def test_typing_in_the_gateway_adds_the_pump(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.MENU
    assert "gateway" in result["menu_options"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "gateway"}
    )
    assert result["step_id"] == "gateway"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "read_port": 9999, "write_port": 10000}
    )
    result = await _finish_progress(hass, result)
    assert result["step_id"] == "gateway_confirm"
    placeholders = result["description_placeholders"]
    assert placeholders["product"] == "NIBE F1255-16 CU"
    assert placeholders["firmware"] == "9721"
    # 43 registers worth showing, plus every flag that says whether an accessory
    # is registered; this pump answers one of them, and has nothing fitted, so
    # nothing more is read.
    assert (placeholders["probed"], placeholders["reporting"]) == ("81", "41")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "", "scan_interval": 60}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NIBE F1255-16 CU"
    data = result["data"]
    assert data["connection"] == "nibegw" and data["model"] == "f1255"
    assert data["word_swap"] is True
    assert set(data["traits"]) == {"ground_source", "hot_water"}
    assert 40033 in data["discovery"]["probed"] and 40033 not in data["discovery"]["reporting"]
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is ConfigEntryState.LOADED


async def test_a_gateway_that_does_not_answer_keeps_the_form_open(hass):
    async def nobody(host, read_port=9999, write_port=10000, **kwargs):
        return None

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "gateway"}
    )
    with patch(f"custom_components.{DOMAIN}.config_flow.async_identify_gateway", nobody):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "10.0.50.99", "read_port": 9999, "write_port": 10000}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "gateway_no_answer"}


async def test_dhcp_finds_the_gateway_by_its_name(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(ip=HOST, hostname=f"nibe-{SERIAL}-gw", macaddress="288485569d3c"),
    )
    assert result["step_id"] == "gateway_discovery_confirm"
    assert result["description_placeholders"]["product"] == "NIBE F1255-16 CU"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await _finish_progress(hass, result)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "", "scan_interval": 60}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == f"nibe-{SERIAL}"
    assert result["data"]["serial"] == SERIAL


async def test_mdns_finds_the_gateway_too(hass):
    info = ZeroconfServiceInfo(
        ip_address=ip_address(HOST),
        ip_addresses=[ip_address(HOST)],
        port=6053,
        hostname=f"nibe-{SERIAL}-gw.local.",
        type="_esphomelib._tcp.local.",
        name=f"nibe-{SERIAL}-gw._esphomelib._tcp.local.",
        properties={},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=info
    )
    assert result["step_id"] == "gateway_discovery_confirm"


async def test_other_esphome_devices_are_ignored(hass):
    info = ZeroconfServiceInfo(
        ip_address=ip_address("10.0.50.60"),
        ip_addresses=[ip_address("10.0.50.60")],
        port=6053,
        hostname="nibe-pool-pump.local.",
        type="_esphomelib._tcp.local.",
        name="nibe-pool-pump._esphomelib._tcp.local.",
        properties={},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_nibe_gateway"


async def test_the_same_pump_is_not_added_twice(hass):
    MockConfigEntry(
        domain=DOMAIN, unique_id=f"nibe-{SERIAL}", data=_entry_data(host="10.0.50.2")
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(ip=HOST, hostname=f"nibe-{SERIAL}-gw", macaddress="288485569d3c"),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # A new address from DHCP is still taken on.
    assert hass.config_entries.async_entries(DOMAIN)[0].data["host"] == HOST


# ------------------------------------------------------------ set-up and polling


async def _advance(hass, freezer, seconds: float) -> None:
    """Move both clocks: Home Assistant's timers and the poll schedule's."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def _set_up(hass, freezer=None, **overrides) -> MockConfigEntry:
    # The entities speak Home Assistant's language, not the one set-up stored,
    # so a test that reads Swedish names has to say Home Assistant is Swedish.
    hass.config.language = overrides.pop("system_language", "sv")
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=f"nibe-{SERIAL}", title="NIBE F1255-16 CU",
        data=_entry_data(**overrides),
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    if freezer is not None and entry.state is ConfigEntryState.LOADED:
        # Entities subscribe one after another; after the first, their refresh
        # requests are debounced for ten seconds, and then everything is read.
        await _advance(hass, freezer, 11)
    return entry


def _entity_id(hass, entry, register) -> str | None:
    meta = entry.runtime_data.registers[register]
    return er.async_get(hass).async_get_entity_id(
        platform_for(meta), DOMAIN, f"{entry.entry_id}-{register}"
    )


async def test_set_up_shows_the_default_registers_that_report(hass, freezer):
    entry = await _set_up(hass, freezer)
    assert entry.state is ConfigEntryState.LOADED
    registry = er.async_get(hass)

    outdoor = _entity_id(hass, entry, 40004)
    assert hass.states.get(outdoor).state == "14.2"
    assert hass.states.get(outdoor).attributes["friendly_name"].endswith("Utetemperatur")

    room = registry.async_get(_entity_id(hass, entry, 40033))
    assert room.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # The long tail exists, switched off; dates do not exist at all.
    assert registry.async_get(_entity_id(hass, entry, 49291)).disabled_by is not None
    assert _entity_id(hass, entry, 48044) is None
    # The F-series has no electricity counter of its own, so the integration
    # builds one out of the power the pump reports; with the pump's own heat
    # meters as the other half, the coefficient of performance follows.
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len([entity for entity in entities if "cop" in entity.unique_id]) == 2
    assert entry.runtime_data.electricity is not None


async def test_value_tables_and_alarms_read_the_f_series_way(hass, freezer):
    entry = await _set_up(hass, freezer)
    compressor = hass.states.get(_entity_id(hass, entry, 43427))
    assert compressor.state == "I drift"
    alarm = hass.states.get(_entity_id(hass, entry, 45001))
    assert alarm.state == "Inget larm"
    hot_water = hass.states.get(_entity_id(hass, entry, 47041))
    assert hot_water.state == "Ekonomi"
    assert "Lyx" in hot_water.attributes["options"]


async def test_an_alarm_reads_as_its_f_series_title(hass, freezer):
    entry = await _set_up(hass, freezer)
    fake = FakeNibeGW.instances[-1]
    fake.values[45001] = 50
    await _advance(hass, freezer, 61)
    alarm = hass.states.get(_entity_id(hass, entry, 45001))
    assert alarm.state == "Högtryckslarm"
    assert alarm.attributes["alarm_code"] == 50


async def test_the_device_is_named_by_the_pump(hass, freezer):
    entry = await _set_up(hass, freezer)
    coordinator = entry.runtime_data
    assert coordinator.is_gateway
    from homeassistant.helpers import device_registry as dr

    (device,) = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert device.model == "NIBE F1255-16 CU"
    assert device.sw_version == "9721"
    assert device.serial_number == SERIAL
    assert device.configuration_url is None


async def test_a_pushed_value_reaches_the_entity_without_a_poll(hass, freezer):
    entry = await _set_up(hass, freezer)
    fake = FakeNibeGW.instances[-1]
    reads_before = len(fake.reads)
    fake.values[40004] = 99.9  # only a read would see this
    fake.push(40004, 3.3)
    await _advance(hass, freezer, 6)
    assert hass.states.get(_entity_id(hass, entry, 40004)).state == "3.3"
    assert len(fake.reads) == reads_before


async def test_measurements_are_read_again_every_cycle_and_settings_are_not(hass, freezer):
    entry = await _set_up(hass, freezer)
    fake = FakeNibeGW.instances[-1]
    fake.reads.clear()
    fake.values[40008] = 31.5
    await _advance(hass, freezer, 61)
    assert 40008 in fake.reads
    assert 47007 not in fake.reads  # a setting: every ten minutes
    assert hass.states.get(_entity_id(hass, entry, 40008)).state == "31.5"


async def test_a_quiet_gateway_is_kept_relaying(hass, freezer):
    """With everything fresh, one read still goes out so pushes keep coming."""
    entry = await _set_up(hass, freezer)
    coordinator = entry.runtime_data
    fake = FakeNibeGW.instances[-1]
    now = time.monotonic()
    for register in coordinator._subscribed:
        coordinator.schedule.seen(register, now)
    coordinator._last_request = 0.0
    fake.reads.clear()
    await coordinator.async_refresh()
    assert fake.reads == [gateway_module.ANNOUNCE_REGISTER]


async def test_a_setting_is_written_and_read_back(hass, freezer):
    entry = await _set_up(hass, freezer)
    fake = FakeNibeGW.instances[-1]
    select = _entity_id(hass, entry, 47041)
    await hass.services.async_call(
        "select", "select_option", {"entity_id": select, "option": "Normal"}, blocking=True
    )
    assert (47041, 1) in fake.writes
    assert hass.states.get(select).state == "Normal"


# ------------------------------------------------------------ heating mode


def _heating_mode(hass, entry) -> str:
    return er.async_get(hass).async_get_entity_id(
        "select", DOMAIN, f"{entry.entry_id}-heating_mode"
    )


async def _choose(hass, entity_id: str, option: str) -> None:
    await hass.services.async_call(
        "select", "select_option", {"entity_id": entity_id, "option": option}, blocking=True
    )


async def test_the_heating_mode_offers_what_ems_writes(hass, freezer):
    entry = await _set_up(hass, freezer)
    state = hass.states.get(_heating_mode(hass, entry))
    assert state.attributes["options"] == ["blocked", "eco", "normal", "boost"]
    assert state.attributes["friendly_name"].endswith("Värmeläge")
    # The offset the pump had is normal, and the modes are steps from it.
    assert state.state == "normal"
    assert state.attributes["normal_offset"] == 0
    assert state.attributes["offsets"] == {"blocked": -3, "eco": -1, "normal": 0, "boost": 1}


async def test_each_heating_mode_writes_its_offset(hass, freezer):
    entry = await _set_up(hass, freezer)
    fake = FakeNibeGW.instances[-1]
    entity_id = _heating_mode(hass, entry)
    for option, offset in (("eco", -1), ("blocked", -3), ("boost", 1), ("normal", 0)):
        await _choose(hass, entity_id, option)
        assert fake.writes[-1] == (47011, offset)
        assert fake.values[47011] == offset
        assert hass.states.get(entity_id).state == option


async def test_an_offset_changed_at_the_pump_in_normal_becomes_normal(hass, freezer):
    entry = await _set_up(hass, freezer)
    fake = FakeNibeGW.instances[-1]
    entity_id = _heating_mode(hass, entry)
    fake.values[47011] = 1  # turned up on the display
    await _advance(hass, freezer, 601)  # settings are read every ten minutes
    state = hass.states.get(entity_id)
    assert state.state == "normal"
    assert state.attributes["normal_offset"] == 1
    await _choose(hass, entity_id, "eco")
    assert fake.writes[-1] == (47011, 0)


async def test_an_offset_changed_in_another_mode_lasts_until_the_mode_changes(hass, freezer):
    entry = await _set_up(hass, freezer)
    fake = FakeNibeGW.instances[-1]
    entity_id = _heating_mode(hass, entry)
    await _choose(hass, entity_id, "blocked")
    # Too cold: someone turns it up through the offset's own entity.
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": _entity_id(hass, entry, 47011), "value": -2},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.state == "blocked"
    assert state.attributes["normal_offset"] == 0
    await _choose(hass, entity_id, "normal")
    assert fake.writes[-1] == (47011, 0)


async def test_the_heating_mode_is_remembered_across_a_restart(hass, freezer, monkeypatch):
    entry = await _set_up(hass, freezer)
    entity_id = _heating_mode(hass, entry)
    await _choose(hass, entity_id, "eco")
    monkeypatch.setitem(READINGS, 47011, -1)  # what the pump keeps meanwhile
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    await _advance(hass, freezer, 11)
    state = hass.states.get(entity_id)
    assert state.state == "eco"
    # Not learned again from the eco offset.
    assert state.attributes["normal_offset"] == 0


async def test_the_offset_is_still_read_without_its_own_entity(hass, freezer):
    entry = await _set_up(hass, freezer)
    coordinator = entry.runtime_data
    coordinator.unsubscribe(47011)  # the offset's number entity switched off
    assert 47011 in coordinator._subscribed
    coordinator.unsubscribe(47011)  # and the heating mode gone too
    assert 47011 not in coordinator._subscribed


async def test_the_steps_are_set_in_the_options(hass, freezer):
    entry = await _set_up(hass, freezer)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    choices = {
        "scan_interval": 60,
        "heating_mode_blocked": -1,
        "heating_mode_eco": -2,
        "heating_mode_boost": 2,
        "send_statistics": True,
    }
    result = await hass.config_entries.options.async_configure(result["flow_id"], choices)
    assert result["errors"] == {"base": "heating_mode_order"}

    choices["heating_mode_blocked"] = -5
    result = await hass.config_entries.options.async_configure(result["flow_id"], choices)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()  # the entry reloads with the new steps
    await _advance(hass, freezer, 11)

    entity_id = _heating_mode(hass, entry)
    assert hass.states.get(entity_id).attributes["offsets"] == {
        "blocked": -5, "eco": -2, "normal": 0, "boost": 2,
    }
    await _choose(hass, entity_id, "blocked")
    assert FakeNibeGW.instances[-1].writes[-1] == (47011, -5)


# ------------------------------------------------------------ hot water boost


def _hot_water_boost(hass, entry) -> str:
    return er.async_get(hass).async_get_entity_id(
        "switch", DOMAIN, f"{entry.entry_id}-hot_water_boost"
    )


async def test_the_hot_water_boost_is_a_one_time_increase(hass, freezer):
    entry = await _set_up(hass, freezer)
    fake = FakeNibeGW.instances[-1]
    entity_id = _hot_water_boost(hass, entry)
    assert hass.states.get(entity_id).attributes["friendly_name"].endswith("Varmvattenboost")
    assert hass.states.get(entity_id).state == "off"

    await hass.services.async_call("switch", "turn_on", {"entity_id": entity_id}, blocking=True)
    assert fake.writes[-1] == (48132, 4)
    assert hass.states.get(entity_id).state == "on"
    assert hass.states.get(_entity_id(hass, entry, 48132)).state == "Engångshöjning"

    await hass.services.async_call("switch", "turn_off", {"entity_id": entity_id}, blocking=True)
    assert fake.writes[-1] == (48132, 0)
    assert hass.states.get(entity_id).state == "off"


async def test_a_lux_started_at_the_pump_reads_as_boosting(hass, freezer):
    entry = await _set_up(hass, freezer)
    fake = FakeNibeGW.instances[-1]
    fake.values[48132] = "3H"
    await _advance(hass, freezer, 601)  # settings are read every ten minutes
    assert hass.states.get(_hot_water_boost(hass, entry)).state == "on"


async def test_a_gateway_that_is_away_at_start_up_is_retried(hass):
    with patch(f"custom_components.{DOMAIN}.GatewayClient", _client_factory(DeadGateway)):
        entry = await _set_up(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert FakeNibeGW.instances[-1].stopped


async def test_unloading_closes_the_connection(hass, freezer):
    entry = await _set_up(hass, freezer)
    fake = FakeNibeGW.instances[-1]
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert fake.stopped


async def test_diagnostics_do_not_assume_modbus(hass, freezer):
    from custom_components.nibe_local_easyconf.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    entry = await _set_up(hass, freezer)
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["connection"]["type"] == "nibegw"
    assert diagnostics["polling"]["subscribed"] > 0


async def test_every_entity_carries_an_explanation(hass, freezer):
    """The dashboard draws its blue "i" from the entity's own description. An
    entity without one is a value on the page that nothing explains - including
    the two controls this integration adds itself."""
    entry = await _set_up(hass, freezer)
    mine = [
        state
        for state in hass.states.async_all()
        if state.entity_id.startswith(("sensor.", "select.", "switch.", "number.", "button."))
        and ("modbus_register" in state.attributes or "basis" in state.attributes)
    ]
    assert len(mine) > 40
    without = [s.entity_id for s in mine if not s.attributes.get("description")]
    assert without == []
    heating_mode_state = hass.states.get(_heating_mode(hass, entry))
    assert "kurvförskjutning" in heating_mode_state.attributes["description"]


async def test_a_register_this_version_wants_is_switched_back_on(hass, freezer):
    """Home Assistant reads "enabled by default" once, when the entity is first
    registered. A version that starts showing a register - the accessory flags
    - would otherwise leave every installation that already has the entity with
    it switched off. What this integration switched off, it switches on again.
    """
    entry = await _set_up(hass, freezer)
    flag = _entity_id(hass, entry, 48852)  # Modbus40 Word Swap, which answers here
    registry = er.async_get(hass)
    assert registry.async_get(flag).disabled_by is None

    # As an older version left it, and as a user who wants it gone leaves it.
    registry.async_update_entity(flag, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
    mine = _entity_id(hass, entry, 47041)
    registry.async_update_entity(mine, disabled_by=er.RegistryEntryDisabler.USER)

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(flag).disabled_by is None
    assert registry.async_get(mine).disabled_by is er.RegistryEntryDisabler.USER


async def test_the_f_series_gets_a_coefficient_of_performance(hass, freezer):
    """It has no electricity meter, so the integration counts what the pump
    reports drawing and divides the heat its own meters have delivered."""
    entry = await _set_up(hass, freezer)
    coordinator = entry.runtime_data
    assert coordinator.electricity is not None
    # Both halves are read whether or not an entity asks for them.
    assert fseries.COMPRESSOR_POWER in coordinator._internal
    assert set(fseries.HEAT_METERS) & coordinator._internal

    watts = coordinator.watts
    assert watts is not None
    assert watts["electronics"] == fseries.ELECTRONICS_W
    # The two circulation pumps, from their speed and NIBE's figures.
    assert watts["pumps"] >= 0

    day = hass.states.get("sensor.nibe_f1255_16_cu_cop_dygn")
    assert day is not None
    counted = hass.states.get("sensor.nibe_f1255_16_cu_forbrukad_el_beraknad")
    assert counted is not None
    assert counted.attributes["unit_of_measurement"] == "kWh"
    assert "compressor_kwh" in counted.attributes
    assert counted.attributes["description"]


async def test_an_update_of_the_integration_reads_the_registers_again(hass, freezer):
    """What is worth reading is this integration's opinion as much as the
    pump's. A release that starts reading registers it did not read before -
    the accessory flags - would otherwise only show them on installations set
    up after it, so a scan made by an older version is made again."""
    from custom_components.nibe_local_easyconf import storage

    entry = await _set_up(hass, freezer)
    fake = FakeNibeGW.instances[-1]

    # A restart on the same version reads nothing at setup: the scan stands.
    fake.reads.clear()
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    settled = len(fake.reads)

    # As an installation upgraded from an older release looks.
    await storage.async_save(
        hass, entry.entry_id, entry.runtime_data.discovery, "1.0.0"
    )
    fake = FakeNibeGW.instances[-1]
    fake.reads.clear()
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert len(FakeNibeGW.instances[-1].reads) > settled + 40
    assert await storage.async_saved_version(hass, entry.entry_id) != "1.0.0"


async def test_a_pump_that_goes_quiet_during_that_scan_keeps_its_entities(hass, freezer):
    """The scan after an update must not cost an installation its entities if
    the gateway happens to be quiet: the scan from before still describes the
    pump, and the next start tries again."""
    from custom_components.nibe_local_easyconf import storage

    entry = await _set_up(hass, freezer)
    before = set(entry.runtime_data.discovery.reporting)
    await storage.async_save(hass, entry.entry_id, entry.runtime_data.discovery, "1.0.0")

    with patch(
        "custom_components.nibe_local_easyconf.probe",
        side_effect=gateway_module.GatewayError("the gateway is quiet"),
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert set(entry.runtime_data.discovery.reporting) == before
    # The version is not marked as scanned, so the next start tries again.
    assert await storage.async_saved_version(hass, entry.entry_id) == "1.0.0"
