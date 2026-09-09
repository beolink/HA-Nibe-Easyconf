"""Read-only registers that carry a flag rather than a measurement."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import PLATFORM_BINARY_SENSOR
from .entity import NibeRegisterEntity, async_add_register_entities


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_register_entities(entry, PLATFORM_BINARY_SENSOR, NibeBinarySensor, async_add_entities)


class NibeBinarySensor(NibeRegisterEntity, BinarySensorEntity):
    @property
    def is_on(self) -> bool | None:
        value = self.native_value_raw
        return None if value is None else bool(value)
