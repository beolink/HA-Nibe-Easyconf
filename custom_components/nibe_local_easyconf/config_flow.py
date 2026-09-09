"""Setup flow: find the pump, then let it tell us what it is.

Three ways in, in order of how little the user has to do:

1. **DHCP.** NIBE names its pumps `NIBE-<serial>` on the network, so a hostname
   pattern is enough to recognise one. Matching on MAC was considered and
   dropped: NIBE holds no IEEE OUI, so the pump's MAC belongs to whichever
   network chipset is fitted and would match unrelated hardware.
2. **A network scan**, for when the DHCP lease will not renew for hours.
3. **Typing the address in**, which always works.
"""

from __future__ import annotations

import asyncio
import logging
import re
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
import voluptuous as vol

from .const import (
    CONF_MODEL,
    CONF_UNIT_ID,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIT_ID,
    DOMAIN,
)
from .discovery import DiscoveryResult, RegisterDiscovery
from .modbus import ModbusTransportError, NibeModbusClient
from .registry import MODEL_LABELS, describe_traits, detect_traits, union_map
from .scanner import FoundPump, async_find_pumps, async_identify

_LOGGER = logging.getLogger(__name__)

#: NIBE's network hostname is "NIBE-" followed by the serial number.
_SERIAL_RE = re.compile(r"^nibe-(\w+)", re.I)


class NibeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Point it at a pump - or let it find one - then probe what it has."""

    VERSION = 1

    def __init__(self) -> None:
        self._client: NibeModbusClient | None = None
        self._input: dict[str, Any] = {}
        self._traits: set[str] = set()
        self._discovery: DiscoveryResult | None = None
        self._register_task: asyncio.Task | None = None
        self._scan_task: asyncio.Task | None = None
        self._found: list[FoundPump] = []
        self._error: str | None = None

    # -- entry points ----------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["search", "manual"])

    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo) -> ConfigFlowResult:
        """A device calling itself NIBE-<serial> appeared on the network."""
        host = discovery_info.ip
        serial = None
        if match := _SERIAL_RE.match(discovery_info.hostname or ""):
            serial = match.group(1)

        # An entry already pointing at this address needs nothing from us.
        for entry in self._async_current_entries():
            if entry.data.get(CONF_HOST) == host:
                return self.async_abort(reason="already_configured")

        if serial:
            # The serial survives a DHCP lease change, so it is the stable id.
            await self.async_set_unique_id(f"nibe-{serial.lower()}")
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        pump = await async_identify(host, DEFAULT_PORT, DEFAULT_UNIT_ID)
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
        client = NibeModbusClient(
            host=config[CONF_HOST], port=config[CONF_PORT], unit_id=config[CONF_UNIT_ID]
        )
        failure: str | None = None
        try:
            await client.connect()
            if await async_identify(
                config[CONF_HOST], config[CONF_PORT], config[CONF_UNIT_ID]
            ) is None:
                failure = "not_nibe"
            else:
                self._traits = await detect_traits(client)
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

        if self.unique_id is None:
            await self.async_set_unique_id(
                f"{config[CONF_HOST]}:{config[CONF_PORT]}:{config[CONF_UNIT_ID]}"
            )
        self._abort_if_unique_id_configured()
        self._client = client
        self._input = dict(config)
        return await self.async_step_discover()

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Probe every documented register to see which ones this pump has."""
        if self._register_task is None:
            assert self._client is not None
            self._register_task = self.hass.async_create_task(
                RegisterDiscovery(self._client).run(union_map())
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
            self._input["discovery"] = {
                "present": sorted(self._discovery.present),
                "reporting": sorted(self._discovery.reporting),
                "absent": sorted(self._discovery.absent),
            }
            return self.async_create_entry(title=title, data=self._input)

        language = self.hass.config.language or "sv"
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL, default="other"): selector.SelectSelector(
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

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return NibeOptionsFlow()


class NibeOptionsFlow(OptionsFlow):
    """Polling interval, adjustable without re-adding the pump."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])}
            )

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=current
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=15, max=600, step=5, unit_of_measurement="s", mode="slider"
                        )
                    )
                }
            ),
        )
