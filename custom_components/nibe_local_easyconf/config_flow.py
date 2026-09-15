"""Setup flow: find the pump, then let it tell us what it is.

Three ways in, in order of how little the user has to do:

1. **DHCP.** NIBE names its pumps `NIBE-<serial>` on the network, so a hostname
   pattern is enough to recognise one. Matching on MAC was considered and
   dropped: NIBE holds no IEEE OUI, so the pump's MAC belongs to whichever
   network chipset is fitted and would match unrelated hardware.
2. **A network scan**, for when the DHCP lease will not renew for hours.
3. **Typing the address in**, which always works.

F-series pumps have no Modbus TCP and are reached through a NibeGW gateway
instead (Nibe-F-series-ModbusAdapter builds one). The gateway announces itself as
nibe-<serial>-gw over DHCP and mDNS, and the pump behind it names its own
model, so that path asks for even less: confirm, wait a minute, done.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from nibe.exceptions import NibeException
import voluptuous as vol

from . import fseries, heating_mode
from .const import (
    CONF_CONNECTION,
    CONF_FIRMWARE,
    CONF_MODEL,
    CONF_PRODUCT,
    CONF_READ_PORT,
    CONF_SEND_STATISTICS,
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
    STATS_ENDPOINT,
    STATS_PRIVACY_URL,
)
from .discovery import DiscoveryResult, RegisterDiscovery
from .gateway import (
    DEFAULT_READ_PORT,
    DEFAULT_WRITE_PORT,
    GatewayClient,
    GatewayError,
    ProbeResult,
    async_identify_gateway,
    probe,
)
from .gateway_coordinator import gateway_discovery
from .modbus import ModbusTransportError, NibeModbusClient
from .registry import (
    MODEL_LABELS,
    async_model_map,
    async_union_map,
    describe_traits,
    detect_traits,
)
from .scanner import FoundPump, async_find_pumps, async_identify
from .serial import parse_serial, serial_from_hostname

_LOGGER = logging.getLogger(__name__)


class NibeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Point it at a pump - or let it find one - then probe what it has."""

    VERSION = 1

    def __init__(self) -> None:
        self._registers: dict[int, dict] | None = None
        self._serial: str | None = None
        self._client: NibeModbusClient | None = None
        self._input: dict[str, Any] = {}
        self._traits: set[str] = set()
        self._discovery: DiscoveryResult | None = None
        self._register_task: asyncio.Task | None = None
        self._scan_task: asyncio.Task | None = None
        self._found: list[FoundPump] = []
        self._error: str | None = None
        # The F-series path through a NibeGW gateway.
        self._gateway: dict[str, Any] = {}
        self._product: fseries.Product | None = None
        self._product_text: str | None = None
        self._firmware: int | None = None
        self._gateway_task: asyncio.Task | None = None
        self._gateway_scan: tuple[ProbeResult, dict[int, dict], bool | None] | None = None

    # -- entry points ----------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["search", "manual", "gateway"])

    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo) -> ConfigFlowResult:
        """A device calling itself NIBE-<serial> appeared on the network."""
        if fseries.is_gateway_hostname(discovery_info.hostname):
            return await self._async_gateway_discovered(discovery_info.ip, discovery_info.hostname)
        host = discovery_info.ip
        serial = serial_from_hostname(discovery_info.hostname)
        self._serial = serial

        # An entry already pointing at this address needs nothing from us.
        for entry in self._async_current_entries():
            if entry.data.get(CONF_HOST) == host:
                return self.async_abort(reason="already_configured")

        if serial:
            # The serial survives a DHCP lease change, so it is the stable id.
            await self.async_set_unique_id(f"nibe-{serial}")
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self._registers = await async_union_map(self.hass)
        pump = await async_identify(
            host, DEFAULT_PORT, DEFAULT_UNIT_ID, self._registers
        )
        if pump is None:
            # Named like a NIBE but not answering Modbus: most likely Modbus TCP
            # is still switched off in menu 7.5.9. Nothing to configure yet.
            return self.async_abort(reason="modbus_disabled")

        self._input = {
            CONF_HOST: host,
            CONF_PORT: DEFAULT_PORT,
            CONF_UNIT_ID: DEFAULT_UNIT_ID,
        }
        self.context["title_placeholders"] = {"name": discovery_info.hostname or host}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask before probing a pump we found on our own."""
        if user_input is not None:
            return await self._async_connect_and_scan(self._input)
        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"host": self._input[CONF_HOST]},
        )

    # -- searching -------------------------------------------------------

    async def async_step_search(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Sweep the local network for pumps answering Modbus."""
        if self._scan_task is None:
            self._scan_task = self.hass.async_create_task(async_find_pumps(self.hass))

        if not self._scan_task.done():
            return self.async_show_progress(
                step_id="search",
                progress_action="searching",
                progress_task=self._scan_task,
            )

        try:
            self._found = self._scan_task.result()
        except Exception:  # report as a form error, not a crash
            _LOGGER.exception("Network scan failed")
            self._found = []
        return self.async_show_progress_done(
            next_step_id="pick" if self._found else "nothing_found"
        )

    async def async_step_nothing_found(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Nothing turned up; fall through to typing the address in."""
        return await self.async_step_manual(errors={"base": "no_pumps_found"})

    async def async_step_pick(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            if user_input[CONF_HOST] == "__manual__":
                return await self.async_step_manual()
            return await self._async_connect_and_scan(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: DEFAULT_PORT,
                    CONF_UNIT_ID: DEFAULT_UNIT_ID,
                }
            )

        options = [
            selector.SelectOptionDict(value=pump.host, label=pump.label)
            for pump in self._found
        ]
        options.append(
            selector.SelectOptionDict(value="__manual__", label="Ange adress manuellt")
        )
        return self.async_show_form(
            step_id="pick",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._found[0].host): (
                        selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=options,
                                mode=selector.SelectSelectorMode.LIST,
                            )
                        )
                    )
                }
            ),
            description_placeholders={"count": str(len(self._found))},
        )

    # -- manual ----------------------------------------------------------

    async def async_step_manual(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        errors = dict(errors or {})

        if user_input is not None:
            result = await self._async_connect_and_scan(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: int(user_input[CONF_PORT]),
                    CONF_UNIT_ID: int(user_input[CONF_UNIT_ID]),
                },
                errors,
            )
            if result is not None:
                return result

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=(user_input or {}).get(CONF_HOST, "")
                    ): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1, max=65535, mode="box")
                    ),
                    vol.Required(
                        CONF_UNIT_ID, default=DEFAULT_UNIT_ID
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=255, mode="box")
                    ),
                }
            ),
            errors=errors,
            description_placeholders={"menu": "7.5.9"},
        )

    # -- shared: connect, then probe the register map --------------------

    async def _async_connect_and_scan(
        self, config: dict[str, Any], errors: dict[str, str] | None = None
    ) -> ConfigFlowResult | None:
        """Validate the connection and move on to the register scan.

        Returns None when `errors` was supplied and validation failed, so the
        caller can redisplay its own form.
        """
        if self._registers is None:
            self._registers = await async_union_map(self.hass)
        client = NibeModbusClient(
            host=config[CONF_HOST], port=config[CONF_PORT], unit_id=config[CONF_UNIT_ID]
        )
        failure: str | None = None
        try:
            await client.connect()
            identified = await async_identify(
                config[CONF_HOST], config[CONF_PORT], config[CONF_UNIT_ID], self._registers
            )
            if identified is None:
                failure = "not_nibe"
            else:
                self._traits = await detect_traits(client, self._registers)
        except ModbusTransportError:
            failure = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error while validating the connection")
            failure = "unknown"

        if failure:
            await client.close()
            if errors is not None:
                errors["base"] = failure
                return None
            self._error = failure
            return self.async_abort(reason=failure)

        if self._serial is None:
            self._serial = await self._async_serial_by_reverse_dns(config[CONF_HOST])
        if self.unique_id is None:
            # The serial is the same identity DHCP discovery uses, so a pump
            # added by hand is recognised when DHCP later sees it too.
            await self.async_set_unique_id(
                f"nibe-{self._serial}"
                if self._serial
                else f"{config[CONF_HOST]}:{config[CONF_PORT]}:{config[CONF_UNIT_ID]}"
            )
        self._abort_if_unique_id_configured()
        self._client = client
        self._input = dict(config)
        return await self.async_step_discover()

    async def _async_serial_by_reverse_dns(self, host: str) -> str | None:
        """Recover the serial from the pump's network name, if DNS knows it.

        The serial is not readable over Modbus, but the pump registers itself
        as NIBE-<serial>, and most home routers answer a reverse lookup for
        their DHCP clients. Best effort: no answer simply means no serial.
        """
        try:
            name, _aliases, _addrs = await self.hass.async_add_executor_job(
                socket.gethostbyaddr, host
            )
        except (OSError, UnicodeError):
            return None
        return serial_from_hostname(name)

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Probe every documented register to see which ones this pump has."""
        if self._register_task is None:
            assert self._client is not None
            assert self._registers is not None
            self._register_task = self.hass.async_create_task(
                RegisterDiscovery(self._client).run(self._registers)
            )

        if not self._register_task.done():
            return self.async_show_progress(
                step_id="discover",
                progress_action="discovering",
                progress_task=self._register_task,
            )

        try:
            self._discovery = self._register_task.result()
        except ModbusTransportError as err:
            _LOGGER.error("Register scan failed: %s", err)
            self._error = "cannot_connect"
            return self.async_show_progress_done(next_step_id="failed")
        return self.async_show_progress_done(next_step_id="confirm")

    async def async_step_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._client is not None:
            await self._client.close()
        return self.async_abort(reason=self._error or "unknown")

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._discovery is not None

        if user_input is not None:
            if self._client is not None:
                await self._client.close()
            model = user_input[CONF_MODEL]
            title = user_input.get(CONF_NAME) or MODEL_LABELS.get(model, "NIBE S-series")
            self._input[CONF_MODEL] = model
            self._input["model_label"] = MODEL_LABELS.get(model, "S-series")
            self._input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            self._input["language"] = self.hass.config.language or "sv"
            # Kept so the daily report can say what kind of machine this is
            # without re-probing. A closed set of slugs, never free text.
            self._input[CONF_TRAITS] = sorted(self._traits)
            if self._serial:
                self._input[CONF_SERIAL] = self._serial
            self._input["discovery"] = {
                "present": sorted(self._discovery.present),
                "reporting": sorted(self._discovery.reporting),
                "absent": sorted(self._discovery.absent),
            }
            return self.async_create_entry(title=title, data=self._input)

        language = self.hass.config.language or "sv"
        # The serial's article number names the exact model, so it becomes the
        # default. The user can still override it - the table is not complete.
        parsed = parse_serial(self._serial)
        suggested = parsed.model_key if parsed and parsed.model_key in MODEL_LABELS else "other"
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL, default=suggested): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=key, label=label)
                                for key, label in MODEL_LABELS.items()
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(CONF_NAME, default=""): str,
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=15, max=600, step=5, unit_of_measurement="s", mode="slider"
                        )
                    ),
                }
            ),
            description_placeholders={
                "host": self._input.get(CONF_HOST, ""),
                "traits": describe_traits(self._traits, language),
                "present": str(len(self._discovery.present)),
                "reporting": str(len(self._discovery.reporting)),
                "absent": str(len(self._discovery.absent)),
            },
        )

    # -- F-series through a NibeGW gateway -----------------------------------

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """An ESPHome device named like a NibeGW gateway announced itself."""
        if not fseries.is_gateway_hostname(discovery_info.name):
            return self.async_abort(reason="not_nibe_gateway")
        return await self._async_gateway_discovered(discovery_info.host, discovery_info.hostname)

    async def _async_gateway_discovered(
        self, host: str, hostname: str | None
    ) -> ConfigFlowResult:
        """DHCP or mDNS found a gateway: identify the pump, then ask to add it."""
        self._serial = serial_from_hostname(hostname)
        self._gateway = {
            CONF_HOST: host,
            CONF_READ_PORT: DEFAULT_READ_PORT,
            CONF_WRITE_PORT: DEFAULT_WRITE_PORT,
        }
        for entry in self._async_current_entries():
            if entry.data.get(CONF_HOST) == host:
                return self.async_abort(reason="already_configured")
        await self._async_set_gateway_unique_id()
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        failure = await self._async_identify_gateway()
        if failure is not None:
            return self.async_abort(reason=failure)
        assert self._product is not None
        self.context["title_placeholders"] = {"name": self._product.label}
        return await self.async_step_gateway_discovery_confirm()

    async def async_step_gateway_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return await self.async_step_gateway_scan()
        assert self._product is not None
        self._set_confirm_only()
        return self.async_show_form(
            step_id="gateway_discovery_confirm",
            description_placeholders={
                "host": self._gateway[CONF_HOST],
                "product": self._product.label,
            },
        )

    async def async_step_gateway(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Type in the gateway's address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._gateway = {
                CONF_HOST: str(user_input[CONF_HOST]).strip(),
                CONF_READ_PORT: int(user_input[CONF_READ_PORT]),
                CONF_WRITE_PORT: int(user_input[CONF_WRITE_PORT]),
            }
            failure = await self._async_identify_gateway()
            if failure is None:
                if self._serial is None:
                    self._serial = await self._async_serial_by_reverse_dns(
                        self._gateway[CONF_HOST]
                    )
                await self._async_set_gateway_unique_id()
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: self._gateway[CONF_HOST]}
                )
                return await self.async_step_gateway_scan()
            errors["base"] = failure

        defaults = user_input or {}
        port = selector.NumberSelector(
            selector.NumberSelectorConfig(min=1, max=65535, mode="box")
        )
        return self.async_show_form(
            step_id="gateway",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
                    vol.Required(
                        CONF_READ_PORT, default=defaults.get(CONF_READ_PORT, DEFAULT_READ_PORT)
                    ): port,
                    vol.Required(
                        CONF_WRITE_PORT, default=defaults.get(CONF_WRITE_PORT, DEFAULT_WRITE_PORT)
                    ): port,
                }
            ),
            errors=errors,
            description_placeholders={"menu": "5.2", "product": self._product_text or ""},
        )

    async def _async_identify_gateway(self) -> str | None:
        """Ask the pump behind the gateway what it is. An error key, or None."""
        info = await async_identify_gateway(
            self._gateway[CONF_HOST],
            self._gateway[CONF_READ_PORT],
            self._gateway[CONF_WRITE_PORT],
        )
        if info is None:
            return "gateway_no_answer"
        product = fseries.identify_product(info.model)
        if product is None:
            self._product_text = info.model
            return "unsupported_model"
        self._product = product
        self._firmware = info.firmware_version
        return None

    async def _async_set_gateway_unique_id(self) -> None:
        # The serial is the pump's identity, the same one the S-series uses.
        await self.async_set_unique_id(
            f"nibe-{self._serial}" if self._serial else f"nibegw-{self._gateway[CONF_HOST]}"
        )

    async def async_step_gateway_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Read the registers worth showing, about a second each."""
        if self._gateway_task is None:
            self._gateway_task = self.hass.async_create_task(self._async_scan_gateway())
        if not self._gateway_task.done():
            return self.async_show_progress(
                step_id="gateway_scan",
                progress_action="gateway_scanning",
                progress_task=self._gateway_task,
            )
        try:
            self._gateway_scan = self._gateway_task.result()
        except (GatewayError, NibeException, OSError) as err:
            _LOGGER.error("Register scan through the gateway failed: %s", err)
            self._error = "gateway_no_answer"
            return self.async_show_progress_done(next_step_id="failed")
        return self.async_show_progress_done(next_step_id="gateway_confirm")

    async def _async_scan_gateway(self) -> tuple[ProbeResult, dict[int, dict], bool | None]:
        assert self._product is not None
        registers = await async_model_map(self.hass, self._product.model)
        client = GatewayClient(
            self._gateway[CONF_HOST],
            self._product.model,
            self._gateway[CONF_READ_PORT],
            self._gateway[CONF_WRITE_PORT],
        )
        await client.start()
        try:
            result = await probe(client, fseries.default_registers(registers))
            return result, registers, client.word_swap
        finally:
            await client.stop()

    async def async_step_gateway_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._product is not None and self._gateway_scan is not None
        result, registers, word_swap = self._gateway_scan
        discovery = gateway_discovery(registers, result)
        language = self.hass.config.language or "sv"
        reporting_titles = {registers[r].get("title", "") for r in discovery.reporting}
        traits = fseries.traits_for(self._product, reporting_titles)

        # A scan that finishes inside the same request hands this step the
        # address form's input: Home Assistant passes it on past progress_done.
        # Only this form's own input counts as confirming.
        if user_input is not None and CONF_SCAN_INTERVAL in user_input:
            data: dict[str, Any] = {
                CONF_CONNECTION: CONNECTION_NIBEGW,
                **self._gateway,
                CONF_MODEL: self._product.key,
                "model_label": self._product.label,
                CONF_PRODUCT: self._product.text,
                CONF_FIRMWARE: self._firmware,
                CONF_WORD_SWAP: word_swap,
                CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                "language": language,
                CONF_TRAITS: sorted(traits),
                "discovery": {
                    "present": sorted(discovery.present),
                    "reporting": sorted(discovery.reporting),
                    "absent": [],
                    "probed": sorted(discovery.probed or ()),
                },
            }
            if self._serial:
                data[CONF_SERIAL] = self._serial
            return self.async_create_entry(
                title=user_input.get(CONF_NAME) or self._product.label, data=data
            )

        return self.async_show_form(
            step_id="gateway_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=""): str,
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): selector.NumberSelector(
                        # Every read takes a second through the gateway; a
                        # shorter cycle than this only means more reads late.
                        selector.NumberSelectorConfig(
                            min=30, max=600, step=5, unit_of_measurement="s", mode="slider"
                        )
                    ),
                }
            ),
            description_placeholders={
                "host": self._gateway[CONF_HOST],
                "product": self._product.label,
                "firmware": str(self._firmware or "?"),
                "traits": describe_traits(traits, language),
                "probed": str(len(discovery.probed or ())),
                "reporting": str(len(discovery.reporting)),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return NibeOptionsFlow()


class NibeOptionsFlow(OptionsFlow):
    """Polling interval, heating mode steps and the daily report, without re-adding the pump."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self.config_entry
        errors: dict[str, str] = {}

        if user_input is not None:
            steps = {
                key: int(user_input[key])
                for key in heating_mode.STEP_OPTIONS.values()
                if key in user_input
            }
            blocked = heating_mode.STEP_OPTIONS[heating_mode.BLOCKED]
            eco = heating_mode.STEP_OPTIONS[heating_mode.ECO]
            if blocked in steps and eco in steps and steps[blocked] > steps[eco]:
                errors["base"] = "heating_mode_order"
            else:
                was_on = self._statistics_enabled()
                now_on = bool(user_input.get(CONF_SEND_STATISTICS, True))
                if was_on and not now_on:
                    # Switching it off erases what has already been sent, rather
                    # than merely going quiet. Imported here rather than at the
                    # top so the module stays importable without the reporter.
                    from .stats import async_forget_install

                    await async_forget_install(self.hass, entry, DOMAIN)
                return self.async_create_entry(
                    data={
                        **entry.options,
                        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                        **steps,
                        CONF_SEND_STATISTICS: now_on,
                    }
                )

        current = entry.options.get(
            CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        fields: dict[Any, Any] = {
            vol.Required(CONF_SCAN_INTERVAL, default=current): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=15, max=600, step=5, unit_of_measurement="s", mode="slider"
                )
            ),
        }
        if self._has_heating_mode():
            steps_now = heating_mode.steps_from(entry.options)
            for mode, low, high in (
                (heating_mode.BLOCKED, -10, 0),
                (heating_mode.ECO, -10, 0),
                (heating_mode.BOOST, 0, 10),
            ):
                fields[
                    vol.Required(heating_mode.STEP_OPTIONS[mode], default=steps_now[mode])
                ] = selector.NumberSelector(
                    selector.NumberSelectorConfig(min=low, max=high, step=1, mode="box")
                )
        fields[vol.Optional(CONF_SEND_STATISTICS, default=self._statistics_enabled())] = (
            selector.BooleanSelector()
        )
        schema = vol.Schema(fields)
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "endpoint": STATS_ENDPOINT,
                "privacy_url": STATS_PRIVACY_URL,
            },
        )

    def _has_heating_mode(self) -> bool:
        """Whether the pump is loaded and has the heat offset the heating mode steers."""
        coordinator = getattr(self.config_entry, "runtime_data", None)
        return (
            coordinator is not None
            and heating_mode.offset_register(
                coordinator.registers, coordinator.discovery.present
            )
            is not None
        )

    def _statistics_enabled(self) -> bool:
        """On unless the user has turned it off. Options win over data."""
        entry = self.config_entry
        if CONF_SEND_STATISTICS in entry.options:
            return bool(entry.options[CONF_SEND_STATISTICS])
        return bool(entry.data.get(CONF_SEND_STATISTICS, True))
