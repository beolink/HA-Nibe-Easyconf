"""The thermostat: one per climate system, out of registers that already exist.

Home Assistant's thermostat card, its scheduler and the voice assistants all
speak to a climate entity, and `nibe_heatpump` in core offers one, so this one
does too - made of the registers climate_systems.py names rather than of
anything new. What it shows is what the pump does:

* **Auto** is the pump regulating on its heat curve, which is how most NIBE
  installations run. There is no target temperature then, because the pump
  has none; the heat offset is the lever, and the heating mode (blocked, eco,
  normal, boost) moves it, so that is what the presets are.
* **Heat** is the pump regulating on its room sensor (BT50), with the room
  setpoint as the target. Choosing it tells the pump to use the sensor. A pump
  without one is not offered the mode: the F1255 at the second site has the
  register and no sensor behind it, and would otherwise be told to regulate
  on nothing.
* **Heat/cool**, on a pump that cools and has a room sensor, adds the cooling
  setpoint as the upper target. The F-series says in a value table how
  cooling follows the room sensor; the S-series map gives no table for it, so
  the mode waits for one.

What the pump is doing - heating, cooling, idle - is read from its priority,
as the overview's status chip reads it, with the system's own shunt closing it
off where there are several systems.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import climate_systems, heating_mode
from .entity import device_info
from .explanations import explain_own
from .translations_extra import entity_language

#: Values the pump takes for "use the room sensor" and "cool with the room
#: sensor too": 0 and 1 on both series, and the F-series table says so.
ROOM_SENSOR_OFF = 0
ROOM_SENSOR_ON = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    registers, present = coordinator.registers, coordinator.discovery.present
    unit = climate_systems.unit(registers, present)
    language = entity_language(hass.config.language, entry.data.get("language"))
    async_add_entities(
        NibeClimate(coordinator, system, unit, language)
        for system in climate_systems.climate_systems(registers, present)
    )


class NibeClimate(CoordinatorEntity, ClimateEntity):
    """One climate system as a thermostat."""

    _attr_has_entity_name = True
    _attr_translation_key = "climate_system"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5

    def __init__(
        self,
        coordinator,
        system: climate_systems.ClimateSystem,
        unit: climate_systems.Unit,
        language: str,
    ) -> None:
        super().__init__(coordinator)
        self._system = system
        self._unit = unit
        self._language = language
        sv = language.startswith("sv")
        number = system.number
        self._attr_name = f"Klimatsystem {number}" if sv else f"Climate system {number}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-climate-{number}"
        self._attr_device_info = device_info(coordinator)
        # The first climate system is the house. The others are accessories
        # most installations do not have, and their settings answer whether or
        # not the hardware is there, so they wait to be switched on.
        self._attr_entity_registry_enabled_default = number == 1

        meta = coordinator.registers[system.setpoint]
        factor = meta.get("factor", 1) or 1
        self._attr_min_temp = (meta.get("min") or 50) / factor
        self._attr_max_temp = (meta.get("max") or 300) / factor

        # The heating mode steers the heat offset of climate system 1 alone.
        self._controller: heating_mode.Controller | None = (
            getattr(coordinator, "heating_mode", None) if number == 1 else None
        )
        cooling = unit.cooling_with_room_sensor
        self._can_cool = (
            system.cool_setpoint is not None
            and cooling is not None
            and bool(coordinator.registers.get(cooling, {}).get("mappings"))
        )
        # The shunt only says something on a system served through one, which
        # the first is not; a register nobody reads is not polled.
        self._mixing_valve = system.mixing_valve if number > 1 else None

        features = ClimateEntityFeature.TARGET_TEMPERATURE
        if self._can_cool:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        if self._controller is not None:
            features |= ClimateEntityFeature.PRESET_MODE
            self._attr_preset_modes = list(heating_mode.MODES)
        self._attr_supported_features = features

    # -- the registers this reads --------------------------------------------

    def _registers(self) -> list[int]:
        system, unit = self._system, self._unit
        wanted = [system.setpoint, system.use_room_sensor, unit.priority, self._mixing_valve]
        if self._sensor_fitted():
            wanted.append(system.current)
        if self._can_cool:
            wanted += [system.cool_setpoint, unit.cooling_with_room_sensor]
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

    def _sensor_fitted(self) -> bool:
        """Whether the system has a room sensor the pump could regulate on.

        The scan knows a register that answers nothing; the F1255 at the
        second site has 40033 and no sensor behind it.
        """
        current = self._system.current
        return current is not None and current not in self.coordinator.discovery.unavailable

    # -- what the pump is doing ----------------------------------------------

    @property
    def available(self) -> bool:
        return super().available and self._value(self._system.use_room_sensor) is not None

    @property
    def current_temperature(self) -> float | None:
        return self._value(self._system.current) if self._sensor_fitted() else None

    @property
    def hvac_modes(self) -> list[HVACMode]:
        modes = [HVACMode.AUTO]
        # A sensor that reads is a sensor the pump can be told to use; a mode
        # the pump is already in stays on the list whatever the sensor says.
        if self.current_temperature is not None or self.hvac_mode not in (None, HVACMode.AUTO):
            modes.append(HVACMode.HEAT)
            if self._can_cool:
                modes.append(HVACMode.HEAT_COOL)
        return modes

    @property
    def hvac_mode(self) -> HVACMode | None:
        using = self._value(self._system.use_room_sensor)
        if using is None:
            return None
        if int(using) != ROOM_SENSOR_ON:
            return HVACMode.AUTO
        if self._can_cool:
            cooling = self._value(self._unit.cooling_with_room_sensor)
            if cooling is not None and int(cooling) != ROOM_SENSOR_OFF:
                return HVACMode.HEAT_COOL
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        priority = self._value(self._unit.priority)
        if priority is None:
            return None
        valve = self._value(self._mixing_valve)
        if valve is not None and int(valve) == climate_systems.MIXING_VALVE_CLOSED:
            return HVACAction.IDLE
        if int(priority) == climate_systems.PRIORITY_HEATING:
            return HVACAction.HEATING
        if int(priority) == climate_systems.PRIORITY_COOLING:
            return HVACAction.COOLING
        return HVACAction.IDLE

    @property
    def target_temperature(self) -> float | None:
        if self.hvac_mode != HVACMode.HEAT:
            return None
        return self._value(self._system.setpoint)

    @property
    def target_temperature_low(self) -> float | None:
        if self.hvac_mode != HVACMode.HEAT_COOL:
            return None
        return self._value(self._system.setpoint)

    @property
    def target_temperature_high(self) -> float | None:
        if self.hvac_mode != HVACMode.HEAT_COOL:
            return None
        return self._value(self._system.cool_setpoint)

    @property
    def preset_mode(self) -> str | None:
        if self._controller is None or self._controller.state is None:
            return None
        return self._controller.state.mode

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attributes: dict[str, Any] = {
            "description": explain_own("climate_system", self._language),
            "room_sensor_fitted": self._sensor_fitted(),
            "modbus_register": self._system.setpoint,
        }
        controller = self._controller
        if controller is not None and controller.state is not None:
            attributes["normal_offset"] = controller.state.normal
            attributes["offsets"] = controller.offsets()
        return attributes

    # -- what can be asked of it --------------------------------------------

    async def async_set_temperature(self, **kwargs: Any) -> None:
        mode = kwargs.get(ATTR_HVAC_MODE)
        if mode is not None:
            await self.async_set_hvac_mode(mode)
        mode = mode or self.hvac_mode
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            if mode != HVACMode.HEAT:
                raise ServiceValidationError(
                    "The pump regulates on its heat curve, not on a room temperature. "
                    "Set the mode to heat to have it use the room sensor, or move the "
                    "heating mode or the heat offset instead."
                )
            await self.coordinator.async_write(self._system.setpoint, float(temperature))
        if (low := kwargs.get(ATTR_TARGET_TEMP_LOW)) is not None:
            await self.coordinator.async_write(self._system.setpoint, float(low))
        if (high := kwargs.get(ATTR_TARGET_TEMP_HIGH)) is not None:
            if not self._can_cool:
                raise ServiceValidationError("This climate system has no cooling setpoint")
            await self.coordinator.async_write(self._system.cool_setpoint, float(high))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        system, unit = self._system, self._unit
        if hvac_mode == HVACMode.AUTO:
            if self._can_cool:
                await self.coordinator.async_write(unit.cooling_with_room_sensor, ROOM_SENSOR_OFF)
            await self.coordinator.async_write(system.use_room_sensor, ROOM_SENSOR_OFF)
            return
        if hvac_mode not in (HVACMode.HEAT, HVACMode.HEAT_COOL):
            raise ServiceValidationError(f"{hvac_mode} is not a mode this pump has")
        if self.current_temperature is None:
            raise ServiceValidationError(
                f"Climate system {system.number} has no room sensor (BT50) reporting, so the "
                "pump cannot regulate on one. It keeps following its heat curve."
            )
        if hvac_mode == HVACMode.HEAT_COOL:
            if not self._can_cool:
                raise ServiceValidationError("This pump has no cooling with the room sensor")
            await self.coordinator.async_write(unit.cooling_with_room_sensor, ROOM_SENSOR_ON)
        elif self._can_cool:
            await self.coordinator.async_write(unit.cooling_with_room_sensor, ROOM_SENSOR_OFF)
        await self.coordinator.async_write(system.use_room_sensor, ROOM_SENSOR_ON)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if self._controller is None:
            raise ServiceValidationError("This climate system has no heating mode")
        if preset_mode not in heating_mode.MODES:
            raise ServiceValidationError(f"{preset_mode} is not a heating mode")
        try:
            await self._controller.async_choose(preset_mode)
        except RuntimeError as err:
            raise ServiceValidationError(str(err)) from err
