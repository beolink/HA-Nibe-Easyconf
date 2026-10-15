"""The water heater: the hot water mode, its temperatures and the boost, as one.

The pump has a hot water mode - economy, normal and luxury on the F-series,
small, medium and large demand on the S-series - and each mode is a pair of
temperatures: it charges the cylinder when the charging sensor (BT6) falls
below the start temperature and stops when it reaches the stop temperature.
That is what a water heater entity shows: the mode as the operation, the pair
as the range, and BT6 as the current temperature, since it is the figure the
pair is about. The top of the cylinder (BT7), where fitted, is an attribute.

The boost is an operation mode too: the one-time increase on the F-series,
three hours of more hot water on the S-series (hot_water_boost.py has the
measurement). Choosing it heats the cylinder; the pump then returns to the
mode it was in, and so does this entity.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import climate_systems
from .entity import device_info
from .explanations import explain_own
from .translations_extra import entity_language


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    water = climate_systems.hot_water(coordinator.registers, coordinator.discovery.present)
    if water is None:
        return
    language = entity_language(hass.config.language, entry.data.get("language"))
    async_add_entities([NibeWaterHeater(coordinator, water, language)])


class NibeWaterHeater(CoordinatorEntity, WaterHeaterEntity):
    """The hot water as Home Assistant's water heater."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = WaterHeaterEntityFeature.OPERATION_MODE
    _attr_icon = "mdi:water-boiler"

    def __init__(self, coordinator, water: climate_systems.HotWater, language: str) -> None:
        super().__init__(coordinator)
        self._water = water
        self._language = language
        self._attr_translation_key = water.words
        self._attr_name = "Varmvatten" if language.startswith("sv") else "Hot water"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-water-heater"
        self._attr_device_info = device_info(coordinator)
        # A pump whose charging sensor answers nothing heats no water that
        # this could show; the entity exists for the day it does.
        self._attr_entity_registry_enabled_default = (
            water.current in coordinator.discovery.reporting
        )
        self._attr_operation_list = [mode.key for mode in water.modes]
        if water.boost is not None:
            self._attr_operation_list.append(climate_systems.BOOST)

        # The range a mode can be set within, from the stop temperatures.
        limits = [
            coordinator.registers[mode.stop] for mode in water.modes if mode.stop is not None
        ]
        if limits:
            factor = limits[0].get("factor", 1) or 1
            self._attr_min_temp = min((meta.get("min") or 50) for meta in limits) / factor
            self._attr_max_temp = max((meta.get("max") or 700) for meta in limits) / factor

    # -- the registers this reads --------------------------------------------

    def _registers(self) -> list[int]:
        water = self._water
        wanted = [water.current, water.mode]
        if water.top is not None and water.top not in self.coordinator.discovery.unavailable:
            wanted.append(water.top)
        for mode in water.modes:
            wanted += [mode.start, mode.stop]
        if water.boost is not None:
            wanted.append(water.boost.register)
        return [register for register in wanted if register is not None]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        for register in self._registers():
            self.coordinator.subscribe(register)
        await self.coordinator.async_request_refresh()

    async def async_will_remove_from_hass(self) -> None:
        for register in self._registers():
            self.coordinator.unsubscribe(register)
        await super().async_will_remove_from_hass()

    def _value(self, register: int | None) -> float | None:
        data = self.coordinator.data
        if register is None or data is None:
            return None
        value = data.get(register)
        return None if value is None else float(value)

    def _mode(self) -> climate_systems.HotWaterMode | None:
        """The hot water mode the pump is set to, boosting or not."""
        value = self._value(self._water.mode)
        if value is None:
            return None
        return next((mode for mode in self._water.modes if mode.value == int(value)), None)

    def _boosting(self) -> bool:
        boost = self._water.boost
        if boost is None:
            return False
        value = self._value(boost.register)
        return value is not None and int(value) != boost.off

    # -- what the pump is doing ----------------------------------------------

    @property
    def available(self) -> bool:
        return super().available and self._value(self._water.current) is not None

    @property
    def current_temperature(self) -> float | None:
        return self._value(self._water.current)

    @property
    def current_operation(self) -> str | None:
        if self._boosting():
            return climate_systems.BOOST
        mode = self._mode()
        return None if mode is None else mode.key

    @property
    def target_temperature_low(self) -> float | None:
        mode = self._mode()
        return None if mode is None else self._value(mode.start)

    @property
    def target_temperature_high(self) -> float | None:
        mode = self._mode()
        return None if mode is None else self._value(mode.stop)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attributes: dict[str, Any] = {
            "description": explain_own("water_heater", self._language),
            "modbus_register": self._water.mode,
        }
        top = self._value(self._water.top)
        if top is not None:
            attributes["top_temperature"] = top
        mode = self._mode()
        if mode is not None:
            attributes["start_temperature"] = self._value(mode.start)
            attributes["stop_temperature"] = self._value(mode.stop)
        return attributes

    # -- what can be asked of it --------------------------------------------

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        water = self._water
        if operation_mode == climate_systems.BOOST:
            if water.boost is None:
                raise ServiceValidationError("This pump's map gives no values for a boost")
            await self.coordinator.async_write(water.boost.register, water.boost.on)
            return
        mode = next((mode for mode in water.modes if mode.key == operation_mode), None)
        if mode is None:
            raise ServiceValidationError(f"{operation_mode} is not a hot water mode here")
        if self._boosting():
            # A mode chosen while boosting is meant instead of the boost.
            await self.coordinator.async_write(water.boost.register, water.boost.off)
        await self.coordinator.async_write(water.mode, mode.value)
