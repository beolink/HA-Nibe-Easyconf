"""Writable numeric registers."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import PLATFORM_NUMBER
from .entity import NibeRegisterEntity, async_add_register_entities
from .units import resolve


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_register_entities(entry, PLATFORM_NUMBER, NibeNumber, async_add_entities)


class NibeNumber(NibeRegisterEntity, NumberEntity):
    """A setting the pump exposes as a number."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, register, meta, language="sv") -> None:
        super().__init__(coordinator, register, meta, language)
        unit, device_class, _state_class = resolve(meta)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class

        factor = meta.get("factor", 1) or 1
        low, high = meta.get("min"), meta.get("max")
        if low is not None:
            self._attr_native_min_value = low / factor if factor != 1 else low
        if high is not None:
            self._attr_native_max_value = high / factor if factor != 1 else high
        # One raw count is the smallest change the pump can store.
        self._attr_native_step = 1 / factor if factor != 1 else 1

    @property
    def native_value(self) -> float | None:
        return self.native_value_raw

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_write(self.register, value)
