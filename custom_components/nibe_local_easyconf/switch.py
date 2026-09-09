"""Writable 0/1 registers."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import PLATFORM_SWITCH
from .entity import NibeRegisterEntity, async_add_register_entities


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_register_entities(entry, PLATFORM_SWITCH, NibeSwitch, async_add_entities)


class NibeSwitch(NibeRegisterEntity, SwitchEntity):
    @property
    def is_on(self) -> bool | None:
        value = self.native_value_raw
        return None if value is None else bool(value)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_write(self.register, 1)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_write(self.register, 0)
