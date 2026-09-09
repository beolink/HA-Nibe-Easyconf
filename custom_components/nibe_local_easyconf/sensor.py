"""Read-only registers."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import PLATFORM_SENSOR
from .entity import NibeRegisterEntity, async_add_register_entities
from .units import resolve


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_register_entities(entry, PLATFORM_SENSOR, NibeSensor, async_add_entities)


class NibeSensor(NibeRegisterEntity, SensorEntity):
    """A measured value, or an enumerated state."""

    def __init__(self, coordinator, register, meta, language="sv") -> None:
        super().__init__(coordinator, register, meta, language)
        unit, device_class, state_class = resolve(meta)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class

        self._mappings = meta.get("mappings") or {}
        if self._mappings:
            # An enumerated register reports a label, not a number.
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_state_class = None
            self._attr_native_unit_of_measurement = None
            self._attr_options = list(dict.fromkeys(self._mappings.values()))

    @property
    def native_value(self):
        value = self.native_value_raw
        if value is None:
            return None
        if self._mappings:
            return self._mappings.get(str(int(value)))
        return value
