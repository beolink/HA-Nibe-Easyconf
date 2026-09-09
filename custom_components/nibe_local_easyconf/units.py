"""Map NIBE's unit strings onto Home Assistant units and device classes."""

from __future__ import annotations

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
    # Degree minutes are a NIBE-specific control quantity with no HA equivalent.
    "DM": (None, None, MEASUREMENT),
}


def resolve(meta: dict) -> tuple[str | None, SensorDeviceClass | None, SensorStateClass | None]:
    """Units, device class and state class for a register."""
    unit = (meta.get("unit") or "").strip()
    entry = UNITS.get(unit)
    if entry is None:
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
    return ha_unit, device_class, state_class
