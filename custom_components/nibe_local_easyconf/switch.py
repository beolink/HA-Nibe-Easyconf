"""Writable 0/1 registers, and the hot water boost."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import hot_water_boost
from .const import PLATFORM_SWITCH
from .entity import NibeRegisterEntity, async_add_register_entities, device_info
from .explanations import explain_own


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_register_entities(entry, PLATFORM_SWITCH, NibeSwitch, async_add_entities)

    coordinator = entry.runtime_data
    boost = hot_water_boost.boost_register(coordinator.registers, coordinator.discovery.present)
    if boost is not None:
        async_add_entities(
            [NibeHotWaterBoostSwitch(coordinator, boost, entry.data.get("language", "sv"))]
        )


class NibeSwitch(NibeRegisterEntity, SwitchEntity):
    @property
    def is_on(self) -> bool | None:
        value = self.native_value_raw
        return None if value is None else bool(value)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_write(self.register, 1)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_write(self.register, 0)


class NibeHotWaterBoostSwitch(CoordinatorEntity, SwitchEntity):
    """On writes temporary lux "One time increase", off writes Off.

    hot_water_boost.py has why those two values, and why any other lux
    setting reads as on.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "hot_water_boost"
    _attr_icon = "mdi:water-boiler"

    def __init__(self, coordinator, boost: hot_water_boost.Boost, language: str) -> None:
        super().__init__(coordinator)
        self._boost = boost
        self._language = language
        self._attr_name = "Varmvattenboost" if language.startswith("sv") else "Hot water boost"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-hot_water_boost"
        self._attr_device_info = device_info(coordinator)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.coordinator.subscribe(self._boost.register)
        await self.coordinator.async_request_refresh()

    async def async_will_remove_from_hass(self) -> None:
        self.coordinator.unsubscribe(self._boost.register)
        await super().async_will_remove_from_hass()

    def _value(self) -> int | None:
        data = self.coordinator.data
        value = None if data is None else data.get(self._boost.register)
        return None if value is None else int(value)

    @property
    def available(self) -> bool:
        return super().available and self._value() is not None

    @property
    def is_on(self) -> bool | None:
        value = self._value()
        return None if value is None else value != self._boost.off

    @property
    def extra_state_attributes(self) -> dict:
        # The dashboard reads the explanation off the entity, the same way it
        # does for a register entity: a control without one gets no "i".
        return {
            "modbus_register": self._boost.register,
            "description": explain_own("hot_water_boost", self._language),
        }

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_write(self._boost.register, self._boost.on)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_write(self._boost.register, self._boost.off)
