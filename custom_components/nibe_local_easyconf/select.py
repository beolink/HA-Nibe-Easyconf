"""Writable registers with a documented set of values, and the heating mode."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import heating_mode
from .const import PLATFORM_SELECT
from .entity import NibeRegisterEntity, async_add_register_entities, device_info
from .explanations import explain_own
from .translations_extra import entity_language


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_register_entities(entry, PLATFORM_SELECT, NibeSelect, async_add_entities)

    coordinator = entry.runtime_data
    controller = getattr(coordinator, "heating_mode", None)
    if controller is not None:
        language = entity_language(hass.config.language, entry.data.get("language"))
        async_add_entities([NibeHeatingModeSelect(coordinator, controller, language)])


class NibeSelect(NibeRegisterEntity, SelectEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, register, meta, language="sv") -> None:
        super().__init__(coordinator, register, meta, language)
        mappings: dict[str, str] = self._labels
        # NIBE's value tables are sparse (hot water mode is 0, 1, 2 and 4), so
        # the raw value is looked up rather than treated as an index.
        self._to_label = {int(key): label for key, label in mappings.items()}
        self._to_value = {label: value for value, label in self._to_label.items()}
        self._attr_options = list(self._to_value)

    @property
    def current_option(self) -> str | None:
        value = self.native_value_raw
        return None if value is None else self._to_label.get(int(value))

    async def async_select_option(self, option: str) -> None:
        if option not in self._to_value:
            raise HomeAssistantError(f"{option} is not a valid option for this register")
        await self.coordinator.async_write(self.register, self._to_value[option])


class NibeHeatingModeSelect(CoordinatorEntity, SelectEntity):
    """Blocked, eco, normal or boost, through the heat offset of climate system 1.

    The options are the ids an energy manager writes; the translations show
    them as words. heating_mode.py has what each mode writes, how an offset
    changed by hand is taken, and the Controller this is one view of - the
    thermostat's presets are the other.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "heating_mode"
    _attr_options = list(heating_mode.MODES)
    _attr_icon = "mdi:home-thermometer-outline"

    def __init__(self, coordinator, controller: heating_mode.Controller, language: str) -> None:
        super().__init__(coordinator)
        self._controller = controller
        self._language = language
        self._attr_name = "Värmeläge" if language.startswith("sv") else "Heating mode"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-heating_mode"
        self._attr_device_info = device_info(coordinator)

    @property
    def available(self) -> bool:
        return super().available and self._controller.available

    @property
    def current_option(self) -> str | None:
        state = self._controller.state
        return None if state is None else state.mode

    @property
    def extra_state_attributes(self) -> dict | None:
        state = self._controller.state
        if state is None:
            return None
        return {
            "normal_offset": state.normal,
            "offsets": self._controller.offsets(),
            "modbus_register": self._controller.register,
            # As for every other control on the page: no explanation, no "i".
            "description": explain_own("heating_mode", self._language),
        }

    async def async_select_option(self, option: str) -> None:
        if option not in heating_mode.MODES:
            raise HomeAssistantError(f"{option} is not a heating mode")
        try:
            await self._controller.async_choose(option)
        except RuntimeError as err:
            raise HomeAssistantError(str(err)) from err
