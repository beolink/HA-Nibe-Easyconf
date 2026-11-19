"""Map NIBE's unit strings onto Home Assistant units and device classes."""

from __future__ import annotations

import re

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)

MEASUREMENT = SensorStateClass.MEASUREMENT
TOTAL_INCREASING = SensorStateClass.TOTAL_INCREASING

#: Titles of start counters: "Compressor starts EB100-EP14", "Compressor, number
#: of starts (EB101-EP14)", "AZ10 Number of Starts", "No. of starts (S135)".
#: "Compr. time to start" and "DM start heating" are not counters.
STARTS = re.compile(r"\bstarts\b", re.IGNORECASE)

#: NIBE unit string -> (HA unit, device class, state class)
UNITS: dict[str, tuple[str | None, SensorDeviceClass | None, SensorStateClass | None]] = {
    "°C": (UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, MEASUREMENT),
    "%": (PERCENTAGE, None, MEASUREMENT),
    "A": (UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, MEASUREMENT),
    "V": (UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, MEASUREMENT),
    "W": (UnitOfPower.WATT, SensorDeviceClass.POWER, MEASUREMENT),
    "kW": (UnitOfPower.KILO_WATT, SensorDeviceClass.POWER, MEASUREMENT),
    "kWh": (UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, TOTAL_INCREASING),
    "Wh": (UnitOfEnergy.WATT_HOUR, SensorDeviceClass.ENERGY, TOTAL_INCREASING),
    "Hz": (UnitOfFrequency.HERTZ, SensorDeviceClass.FREQUENCY, MEASUREMENT),
    "bar": (UnitOfPressure.BAR, SensorDeviceClass.PRESSURE, MEASUREMENT),
    "rpm": (REVOLUTIONS_PER_MINUTE, None, MEASUREMENT),
    "h": (UnitOfTime.HOURS, SensorDeviceClass.DURATION, TOTAL_INCREASING),
    "min": (UnitOfTime.MINUTES, SensorDeviceClass.DURATION, MEASUREMENT),
    "s": (UnitOfTime.SECONDS, SensorDeviceClass.DURATION, MEASUREMENT),
    "days": (UnitOfTime.DAYS, SensorDeviceClass.DURATION, MEASUREMENT),
    "l/m": (UnitOfVolumeFlowRate.LITERS_PER_MINUTE, None, MEASUREMENT),
    "l/min": (UnitOfVolumeFlowRate.LITERS_PER_MINUTE, None, MEASUREMENT),
    "m³/h": (UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR, None, MEASUREMENT),
    # Spellings the maps use for a handful of registers: the humidity sensors
    # of the room units, the pressure sensor BM1 and the airflow pressure
    # sensors BP15/BP16, the compressor current in milliamperes, and two
    # timers. Without an entry here they had a unit and no state class, so
    # Home Assistant kept no long-term statistics for them.
    "%RH": (PERCENTAGE, SensorDeviceClass.HUMIDITY, MEASUREMENT),
    "kPa": (UnitOfPressure.KPA, SensorDeviceClass.PRESSURE, MEASUREMENT),
    "Pa": (UnitOfPressure.PA, SensorDeviceClass.PRESSURE, MEASUREMENT),
    "mA": (UnitOfElectricCurrent.MILLIAMPERE, SensorDeviceClass.CURRENT, MEASUREMENT),
    "hrs": (UnitOfTime.HOURS, SensorDeviceClass.DURATION, MEASUREMENT),
    "sec": (UnitOfTime.SECONDS, SensorDeviceClass.DURATION, MEASUREMENT),
    # Degree minutes are a NIBE-specific control quantity with no HA equivalent.
    "DM": (None, None, MEASUREMENT),
}


def resolve(meta: dict) -> tuple[str | None, SensorDeviceClass | None, SensorStateClass | None]:
    """Units, device class and state class for a register."""
    unit = (meta.get("unit") or "").strip()
    # "+Adjust AUX Port" carries the unit "1", which is no unit at all.
    if unit == "1":
        unit = ""
    entry = UNITS.get(unit)
    if entry is None:
        # A start count has no unit in NIBE's maps, but it only ever climbs, like
        # a run time, and its long-term statistics are a running total. Without
        # the state class Home Assistant keeps no statistics for it, and history
        # brought in from myUplink or an older integration has nowhere to land.
        if not unit and not meta.get("write") and STARTS.search(meta.get("title", "")):
            return (None, None, TOTAL_INCREASING)
        return (unit or None, None, None)

    ha_unit, device_class, state_class = entry
    title = meta.get("title", "").lower()

    # Energy and runtime registers are counters only when they accumulate.
    # "Energy log - used energy over the past hour" resets every hour, and
    # "max. internal additional heat" is a setting, so neither is monotonic.
    if state_class is TOTAL_INCREASING and (
        "over the past" in title or "average" in title or meta.get("write")
    ):
        state_class = MEASUREMENT
    if meta.get("write") and device_class is SensorDeviceClass.ENERGY:
        device_class = None
    # Home Assistant rejects an energy sensor with state class "measurement":
    # energy must be a total or nothing. "Energy used over the past hour" is a
    # rolling window, not a running total, so long-term statistics summed from
    # it would be wrong - it keeps its energy unit and icon, and no state class.
    if device_class is SensorDeviceClass.ENERGY and state_class is MEASUREMENT:
        state_class = None
    return ha_unit, device_class, state_class
