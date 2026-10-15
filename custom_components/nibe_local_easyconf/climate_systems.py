"""Which registers make up a climate system and the hot water, on either series.

NIBE's maps give the registers one by one; a thermostat needs them as a set:
the room temperature the system regulates on, the setpoint it is given,
whether it has been told to use the room sensor at all, and what the pump is
busy with. The `nibe` library groups them by address per series
(coil_groups.py); these tables say the same thing by title, which is how the
rest of this integration tells registers apart - the same address means
different things on the two series, and the title is what travels between
maps. Both were checked against the development units: the S1155 answers
Roomsensor 1-1 and the room average with the same 19.5 °C and keeps its
setpoint in 40207, the F1255 has no room sensor and answers 40033 with nothing.

The hot water is the same shape on both series under different words. The
F-series has a comfort mode - economy, normal, luxury - and the S-series a
demand mode - small, medium, large; each picks a pair of start and stop
temperatures, and the pump charges the cylinder when the charging sensor (BT6)
falls below the start temperature and stops when it reaches the stop
temperature. BT6 is therefore the temperature a water heater here reports: it
is the one the pump's own figures are about. The S1155 has no top sensor at
all, which settled the choice.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .hot_water_boost import Boost, boost_register

#: How many climate systems a map can hold. NIBE's F-series maps have four; the
#: S-series maps eight, of which the last four have no setpoint register.
CLIMATE_SYSTEMS = (1, 2, 3, 4)


@dataclass(frozen=True)
class ClimateSystem:
    """The registers of one climate system."""

    number: int
    #: The room temperature the system regulates on, when it has a sensor.
    current: int | None
    #: The room setpoint, heating.
    setpoint: int
    #: The room setpoint, cooling, on a pump that cools.
    cool_setpoint: int | None
    #: Whether the pump regulates on the room sensor (1) or on the heat curve (0).
    use_room_sensor: int
    #: The shunt or mixing valve, closed when the system is not being served.
    mixing_valve: int | None


@dataclass(frozen=True)
class Unit:
    """Registers about the pump as a whole that every climate system reads."""

    #: What the pump is working on: off, hot water, heating, pool, cooling.
    priority: int | None
    #: Whether cooling follows the room sensor too; 0 is off on both series.
    cooling_with_room_sensor: int | None


@dataclass(frozen=True)
class HotWaterMode:
    """One of the pump's hot water modes and the temperatures it works between."""

    key: str
    value: int
    start: int | None
    stop: int | None


@dataclass(frozen=True)
class HotWater:
    """The registers behind the water heater."""

    #: The charging temperature (BT6), which the start and stop temperatures are about.
    current: int
    #: The top of the cylinder (BT7), where fitted.
    top: int | None
    #: The writable mode: comfort mode on the F-series, demand mode on the S-series.
    mode: int
    modes: tuple[HotWaterMode, ...]
    #: The one-time increase, where the map gives its values.
    boost: Boost | None
    #: Which translation names the modes: the F-series' words or the S-series'.
    words: str


#: Titles per role, per series. Each entry is a format with the system number
#: and, for the F-series, the module prefix NIBE puts on systems 2-4.
_F_PREFIX = {1: "", 2: "EP21-", 3: "EP22-", 4: "EP23-"}

_CLIMATE_TITLES = (
    # F-series
    {
        "current": ("{prefix}BT50 Room Temp S{n}",),
        "setpoint": ("Room sensor setpoint S{n}",),
        "cool_setpoint": ("Room sensor cool setpoint S{n}",),
        "use_room_sensor": ("Use room sensor S{n}",),
        "mixing_valve": ("Mixing Valve State S{n}",),
    },
    # S-series: the average the pump regulates on first, then the first sensor.
    {
        "current": ("Room average temp. clim. system {n} (BT50)", "Roomsensor {n}-1"),
        "setpoint": ("Room sensor set point value climate system {n}",),
        "cool_setpoint": ("Room sensor set point value climate system {n}, cooling",),
        "use_room_sensor": ("Use room sensor climate system {n}",),
        "mixing_valve": ("Oper. mode shunt climate system {n}",),
    },
)

#: The S-series titles two registers "Priority"; the lower one answers in words
#: and is what the overview shows. Either carries NIBE's table of tens.
_UNIT_TITLES = {
    "priority": ("Prio", "Priority"),
    "cooling_with_room_sensor": ("Cooling with room sensor", "Cooling with room sensors"),
}

#: Priority values, the same on both series: eU8StatePrio in NIBE's register list.
PRIORITY_HEATING = 30
PRIORITY_COOLING = 60
#: The mixing valve state that means the system is not being served.
MIXING_VALVE_CLOSED = 30

_HOT_WATER = (
    # F-series: comfort mode. The pump's own words, as its menu has them.
    {
        "words": "hot_water",
        "current": ("BT6 HW Load",),
        "top": ("BT7 HW Top",),
        "mode": ("Hot water comfort mode",),
        "modes": (
            ("economy", "Economy", "Start temperature HW Economy", "Stop temperature HW Economy"),
            ("normal", "Normal", "Start temperature HW Normal", "Stop temperature HW Normal"),
            ("luxury", "Luxury", "Start temperature HW Luxury", "Stop temperature HW Luxury"),
            ("smart", "Smart Control", None, None),
        ),
    },
    # S-series: demand mode, whose small, medium and large pick the low, normal
    # and high pairs of temperatures.
    {
        "words": "hot_water_demand",
        "current": ("Hot water charging (BT6)",),
        "top": ("Hot water top (BT7)",),
        "mode": ("Hot water demand mode",),
        "modes": (
            (
                "small",
                "Small",
                "Start temperature HW low temperature",
                "Stop temperature HW low temperature",
            ),
            (
                "medium",
                "Medium",
                "Start temperature HW normal temperature",
                "Stop temperature HW normal temperature",
            ),
            (
                "large",
                "Large",
                "Start temperature HW high temperature",
                "Stop temperature HW high temperature",
            ),
            ("smart", "Smart control", None, None),
        ),
    },
)

#: The one-time increase in words, as an operation mode.
BOOST = "boost"


def _index(registers: Mapping[int, dict], present: Iterable[int]) -> dict[str, int]:
    """Title -> register, among the registers the pump has; the lowest wins a tie."""
    index: dict[str, int] = {}
    for register in sorted(present, reverse=True):
        meta = registers.get(register)
        if meta and meta.get("title"):
            index[meta["title"]] = register
    return index


def _find(index: Mapping[str, int], titles: Iterable[str], **fields) -> int | None:
    for title in titles:
        register = index.get(title.format(**fields))
        if register is not None:
            return register
    return None


def climate_systems(registers: Mapping[int, dict], present: Iterable[int]) -> list[ClimateSystem]:
    """The climate systems this pump has registers for, in order.

    A system needs its setpoint and its room sensor switch to be a thermostat
    at all; the sensor itself, the cooling setpoint and the shunt are taken
    where the map has them.
    """
    index = _index(registers, present)
    systems: list[ClimateSystem] = []
    for number in CLIMATE_SYSTEMS:
        for titles in _CLIMATE_TITLES:
            fields = {"n": number, "prefix": _F_PREFIX[number]}
            setpoint = _find(index, titles["setpoint"], **fields)
            use_room_sensor = _find(index, titles["use_room_sensor"], **fields)
            if setpoint is None or use_room_sensor is None:
                continue
            if not registers[setpoint].get("write") or not registers[use_room_sensor].get("write"):
                continue
            systems.append(
                ClimateSystem(
                    number=number,
                    current=_find(index, titles["current"], **fields),
                    setpoint=setpoint,
                    cool_setpoint=_find(index, titles["cool_setpoint"], **fields),
                    use_room_sensor=use_room_sensor,
                    mixing_valve=_find(index, titles["mixing_valve"], **fields),
                )
            )
            break
    return systems


def unit(registers: Mapping[int, dict], present: Iterable[int]) -> Unit:
    """What every climate system reads about the pump as a whole."""
    index = _index(registers, present)
    return Unit(
        priority=_find(index, _UNIT_TITLES["priority"]),
        cooling_with_room_sensor=_find(index, _UNIT_TITLES["cooling_with_room_sensor"]),
    )


def _mode_value(meta: dict, label: str) -> int | None:
    """The raw value behind a label in the register's own table."""
    for value, text in (meta.get("mappings") or {}).items():
        if str(text).strip().lower() == label.lower():
            return int(value)
    return None


def hot_water(registers: Mapping[int, dict], present: Iterable[int]) -> HotWater | None:
    """The water heater's registers, if this pump heats water."""
    index = _index(registers, present)
    for table in _HOT_WATER:
        current = _find(index, table["current"])
        mode = _find(index, table["mode"])
        if current is None or mode is None or not registers[mode].get("write"):
            continue
        modes = []
        for key, label, start, stop in table["modes"]:
            value = _mode_value(registers[mode], label)
            if value is None:
                continue
            modes.append(
                HotWaterMode(
                    key=key,
                    value=value,
                    start=None if start is None else _find(index, (start,)),
                    stop=None if stop is None else _find(index, (stop,)),
                )
            )
        if not modes:
            continue
        return HotWater(
            current=current,
            top=_find(index, table["top"]),
            mode=mode,
            modes=tuple(modes),
            boost=boost_register(registers, present),
            words=table["words"],
        )
    return None
