"""Setup flow: point it at the pump and let it work the rest out."""

from __future__ import annotations

import asyncio
import logging
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
import voluptuous as vol

from .const import (
    CONF_MODEL,
    CONF_UNIT_ID,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIT_ID,
    DOMAIN,
)
from .discovery import DiscoveryResult, RegisterDiscovery, function_code, modbus_address
from .modbus import ModbusTransportError, NibeModbusClient
from .registry import MODEL_LABELS, describe_traits, detect_traits, union_map

_LOGGER = logging.getLogger(__name__)

#: Read during validation to prove we are talking to a NIBE S-series pump.
#: 30002 is the outdoor temperature (BT1), present on every S-series model.
PROBE_REGISTER = 30002


class NibeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for an address, then find out what the pump is by asking it."""

    VERSION = 1

    def __init__(self) -> None:
        self._client: NibeModbusClient | None = None
        self._input: dict[str, Any] = {}
        self._traits: set[str] = set()
        self._discovery: DiscoveryResult | None = None
        self._task: asyncio.Task | None = None
        self._error: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            client = NibeModbusClient(
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                unit_id=user_input[CONF_UNIT_ID],
            )
            try:
                await client.connect()
                words = await client.probe(
                    function_code(PROBE_REGISTER), modbus_address(PROBE_REGISTER), 1
                )
                if words is None:
                    errors["base"] = "not_nibe"
                else:
                    self._traits = await detect_traits(client)
            except ModbusTransportError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error while validating the connection")
                errors["base"] = "unknown"

            if errors:
                await client.close()
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}:{user_input[CONF_UNIT_ID]}"
                )
                self._abort_if_unique_id_configured()
                self._client = client
                self._input = dict(user_input)
                return await self.async_step_discover()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=(user_input or {}).get(CONF_HOST, "")): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1, max=65535, mode="box")
                    ),
                    vol.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=255, mode="box")
                    ),
                }
            ),
            errors=errors,
            description_placeholders={"menu": "7.5.9"},
        )

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Probe every documented register to see which ones this pump has."""
        if self._task is None:
            assert self._client is not None
            self._task = self.hass.async_create_task(
                RegisterDiscovery(self._client).run(union_map())
            )

        if not self._task.done():
            return self.async_show_progress(
                step_id="discover",
                progress_action="discovering",
                progress_task=self._task,
            )

        try:
            self._discovery = self._task.result()
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
