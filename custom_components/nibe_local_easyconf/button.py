"""Momentary registers, and this integration's own actions, as buttons.

A register whose only use is to be written - "Reset alarm by setting value 1",
as the F-series map puts its 45171 - is nothing to read. As a number it showed
0 for ever; as a button it is the thing itself. The rescan gets a button too,
so it is on the device page for someone who never opens the developer tools.
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .actions import async_rescan
from .const import PLATFORM_BUTTON
from .entity import NibeRegisterEntity, async_add_register_entities, device_info
from .explanations import explain_own
from .translations_extra import entity_language


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_register_entities(entry, PLATFORM_BUTTON, NibeButton, async_add_entities)

    coordinator = entry.runtime_data
    language = entity_language(hass.config.language, entry.data.get("language"))
    async_add_entities([NibeRescanButton(coordinator, entry, language)])


class NibeButton(NibeRegisterEntity, ButtonEntity):
    """A register that does one thing when written 1: reset the alarm."""

    _attr_icon = "mdi:alarm-light-off-outline"

    async def async_added_to_hass(self) -> None:
        # Not subscribed to the register: there is nothing in it to read.
        # CoordinatorEntity's own hook still runs, so availability follows
        # the pump.
        await CoordinatorEntity.async_added_to_hass(self)

    async def async_will_remove_from_hass(self) -> None:
        await CoordinatorEntity.async_will_remove_from_hass(self)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    async def async_press(self) -> None:
        await self.coordinator.async_write(self.register, 1)


class NibeRescanButton(CoordinatorEntity, ButtonEntity):
    """Probe the pump again: after a firmware update, or an accessory fitted."""

    _attr_has_entity_name = True
    _attr_translation_key = "rescan"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:magnify-scan"

    def __init__(self, coordinator, entry: ConfigEntry, language: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._language = language
        self._attr_name = "Sök om register" if language.startswith("sv") else "Rescan registers"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-rescan"
        self._attr_device_info = device_info(coordinator)

    @property
    def extra_state_attributes(self) -> dict:
        return {"description": explain_own("rescan", self._language)}

    async def async_press(self) -> None:
        await async_rescan(self.hass, self._entry)
