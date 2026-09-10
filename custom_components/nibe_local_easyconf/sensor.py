"""Read-only registers."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import PLATFORM_SENSOR
from .coordinator import NibeCoordinator
from .entity import NibeRegisterEntity, async_add_register_entities, device_info
from .official import alarm_text, is_alarm_register, labels_for
from .units import resolve


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_register_entities(entry, PLATFORM_SENSOR, NibeSensor, async_add_entities)
    coordinator: NibeCoordinator = entry.runtime_data
    if coordinator.serial is not None and coordinator.serial.manufactured:
        async_add_entities([NibeManufacturedSensor(coordinator)])
    if coordinator.cop is not None:
        async_add_entities([NibeCopSensor(coordinator, span) for span in ("day", "year")])


class NibeSensor(NibeRegisterEntity, SensorEntity):
    """A measured value, or an enumerated state."""

    def __init__(self, coordinator, register, meta, language="sv") -> None:
        super().__init__(coordinator, register, meta, language)
        unit, device_class, state_class = resolve(meta)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class

        # An alarm register is a code into NIBE's alarm list. It reads as the
        # alarm's text, and keeps the code as an attribute for automations.
        self._alarm = is_alarm_register(meta.get("title", ""))
        if self._alarm:
            self._attr_native_unit_of_measurement = None
            self._attr_state_class = None
            self._attr_device_class = None
            self._attr_icon = "mdi:alert-circle-outline"

        self._mappings = (
            {}
            if self._alarm
            else labels_for(register, language) or meta.get("mappings") or {}
        )
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
        if self._alarm:
            return alarm_text(value, self._language)
        if self._mappings:
            return self._mappings.get(str(int(value)))
        return value

    @property
    def extra_state_attributes(self):
        attributes = super().extra_state_attributes
        if self._alarm and self.native_value_raw is not None:
            attributes["alarm_code"] = int(self.native_value_raw)
        return attributes


class NibeManufacturedSensor(CoordinatorEntity[NibeCoordinator], SensorEntity):
    """The day the pump was built, from its serial number.

    Not a register: NIBE encodes the year and the day of the year in digits
    7-11 of the serial, which the pump announces in its network name.
    """

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DATE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:factory"

    def __init__(self, coordinator: NibeCoordinator) -> None:
        super().__init__(coordinator)
        language = coordinator.config_entry.data.get("language", "sv")
        self._attr_name = "Tillverkad" if language.startswith("sv") else "Manufactured"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-manufactured"
        self._attr_device_info = device_info(coordinator)

    @property
    def native_value(self):
        return self.coordinator.serial.manufactured

    @property
    def extra_state_attributes(self) -> dict:
        serial = self.coordinator.serial
        return {
            "article_number": serial.article,
            "iso_week": serial.iso_week,
            "day_of_year": serial.day_of_year,
        }


class NibeCopSensor(CoordinatorEntity[NibeCoordinator], SensorEntity):
    """Coefficient of performance over the last day, or over a rolling year.

    The yearly sensor shows the lifetime figure until a year of samples exists,
    and says so in its `basis` attribute - the same behaviour as the CTC
    integration's. The daily report is stricter and sends a yearly figure only
    once it truly covers a year.
    """

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:heat-pump-outline"

    def __init__(self, coordinator: NibeCoordinator, span: str) -> None:
        super().__init__(coordinator)
        self._span = span
        self._language = coordinator.config_entry.data.get("language", "sv")
        sv = self._language.startswith("sv")
        self._attr_name = {
            "day": "COP, dygn" if sv else "COP, day",
            "year": "COP, år" if sv else "COP, year",
        }[span]
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-cop-{span}"
        self._attr_device_info = device_info(coordinator)

    def _result(self):
        tracker = self.coordinator.cop
        out, consumed = self.coordinator.energy_out, self.coordinator.energy_in
        if self._span == "day":
            return tracker.result_day(out, consumed)
        return tracker.result(out, consumed)

    @property
    def native_value(self):
        return self._result().value

    @property
    def extra_state_attributes(self) -> dict:
        return self._result().as_attributes(self._language)
