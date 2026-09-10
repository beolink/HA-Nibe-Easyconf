"""Writable registers with a documented set of values."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import PLATFORM_SELECT
from .entity import NibeRegisterEntity, async_add_register_entities
from .official import labels_for


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_register_entities(entry, PLATFORM_SELECT, NibeSelect, async_add_entities)


class NibeSelect(NibeRegisterEntity, SelectEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, register, meta, language="sv") -> None:
        super().__init__(coordinator, register, meta, language)
        mappings: dict[str, str] = labels_for(register, language) or meta.get("mappings") or {}
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
