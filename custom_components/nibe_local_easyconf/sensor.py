"""Read-only registers."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import fseries
from .const import PLATFORM_SENSOR
from .coordinator import NibeCoordinator
from .entity import NibeRegisterEntity, async_add_register_entities, device_info
from .explanations import explain_own
from .translations_extra import entity_language
from .units import resolve


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_register_entities(entry, PLATFORM_SENSOR, NibeSensor, async_add_entities)
    coordinator: NibeCoordinator = entry.runtime_data
    if coordinator.serial is not None and coordinator.serial.manufactured:
        async_add_entities([NibeManufacturedSensor(coordinator)])
    if coordinator.cop is not None:
        async_add_entities(
            [NibeCopSensor(coordinator, span) for span in ("day", "year", "lifetime")]
        )
    if getattr(coordinator, "electricity", None) is not None:
        async_add_entities([NibeCountedElectricitySensor(coordinator)])


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
        self._alarm = coordinator.is_alarm(meta)
        if self._alarm:
            self._attr_native_unit_of_measurement = None
            self._attr_state_class = None
            self._attr_device_class = None
            self._attr_icon = "mdi:alert-circle-outline"

        self._mappings = {} if self._alarm else self._labels
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
            return self.coordinator.alarm_text(value, self._language)
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
        language = entity_language(
            coordinator.hass.config.language, coordinator.config_entry.data.get("language")
        )
        self._language = language
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
            "description": explain_own("manufactured", self._language),
            "article_number": serial.article,
            "iso_week": serial.iso_week,
            "day_of_year": serial.day_of_year,
        }


class NibeCountedElectricitySensor(CoordinatorEntity[NibeCoordinator], SensorEntity):
    """The electricity an F-series pump has used, counted rather than measured.

    power.py has how it is arrived at and what it is worth. The parts are kept
    as attributes so the figure can be taken apart: a coefficient of
    performance that looks wrong is usually one of them.
    """

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "kWh"
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:lightning-bolt-outline"

    def __init__(self, coordinator: NibeCoordinator) -> None:
        super().__init__(coordinator)
        self._language = entity_language(
            coordinator.hass.config.language, coordinator.config_entry.data.get("language")
        )
        sv = self._language.startswith("sv")
        self._attr_name = "Förbrukad el (beräknad)" if sv else "Electricity used (counted)"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-counted-electricity"
        self._attr_device_info = device_info(coordinator)

    @property
    def native_value(self) -> float:
        return round(self.coordinator.electricity.kwh, 3)

    @property
    def extra_state_attributes(self) -> dict:
        counter = self.coordinator.electricity
        parts = counter.parts
        watts = self.coordinator.watts or {}
        brine, medium = self.coordinator.pump_watt_limits
        counting_heat = counter.counting_heat
        return {
            "description": explain_own(
                "counted_electricity" if counting_heat else "heat_not_counted",
                self._language,
            ),
            # Whether the other half of a coefficient of performance exists on
            # this pump at all; see power.py.
            "pump_counts_heat": counting_heat,
            "compressor_kwh": round(parts.compressor, 3),
            "additional_heat_kwh": round(parts.addition, 3),
            "circulation_pumps_kwh": round(parts.pumps, 3),
            "electronics_kwh": round(parts.electronics, 3),
            "power_now_w": round(sum(watts.values()), 1) if watts else None,
            # What the count rests on, so it can be judged rather than trusted.
            "brine_pump_w": f"{brine[0]}-{brine[1]}",
            "heat_medium_pump_w": f"{medium[0]}-{medium[1]}",
            "electronics_w": fseries.ELECTRONICS_W,
            "heat_delivered_kwh": (
                None
                if self.coordinator.energy_out is None
                else round(self.coordinator.energy_out, 1)
            ),
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
        self._language = entity_language(
            coordinator.hass.config.language, coordinator.config_entry.data.get("language")
        )
        sv = self._language.startswith("sv")
        # Short, because it stands on a chip beside its value. The word
        # värmefaktor lives in the explanation, where someone searching for it
        # will still find the sensor: the page's filter reads both.
        #
        # The longest span is the pump's whole life on the S-series, which
        # counts its own kilowatt hours, and everything this integration has
        # counted on the F-series, which does not. Naming it for what it is on
        # each keeps the figure from claiming more than it covers.
        counted_here = getattr(coordinator, "is_gateway", False)
        self._attr_name = {
            "day": "COP, dygn" if sv else "COP, day",
            "year": "COP, år" if sv else "COP, year",
            "lifetime": (
                ("COP, sedan start" if sv else "COP, since start")
                if counted_here
                else ("COP, livstid" if sv else "COP, lifetime")
            ),
        }[span]
        self._counted_here = counted_here
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-cop-{span}"
        self._attr_device_info = device_info(coordinator)

    def _result(self):
        tracker = self.coordinator.cop
        out, consumed = self.coordinator.energy_out, self.coordinator.energy_in
        if self._span == "day":
            return tracker.result_day(out, consumed)
        if self._span == "lifetime":
            return tracker.result_lifetime(out, consumed)
        return tracker.result(out, consumed)

    @property
    def native_value(self):
        return self._result().value

    @property
    def extra_state_attributes(self) -> dict:
        result = self._result()
        attributes = result.as_attributes(self._language)
        # Which span this figure stands on, as a word rather than as a name:
        # the dashboard tells them apart without reading Swedish.
        attributes["span"] = self._span
        if self._counted_here and result.basis == "lifetime":
            # The pump's heat meters have run since it was installed, but the
            # electricity is counted from the day this integration began.
            attributes["basis"] = (
                "sedan mätningen började"
                if self._language.startswith("sv")
                else "since counting began"
            )
        attributes["description"] = explain_own(
            f"cop_{self._span}_gateway" if self._counted_here and self._span == "lifetime"
            else f"cop_{self._span}",
            self._language,
        )
        history = self.coordinator.cop.history
        if history and history.get("production"):
            # Where the samples before installation came from, so a yearly
            # figure that appears early can be traced to its source.
            attributes["history_from"] = history.get("from")
            attributes["history_production"] = history.get("production")
            attributes["history_consumption"] = history.get("consumption")
        return attributes
