"""Hot water boost: the switch an energy manager turns on to have the tank heated now.

EMS Steward plans hot water in quarters and writes a switch: on while it wants
the tank heated, off otherwise, with "water heater is a boost" ticked so that
off is the neutral state. On the F-series the boost is temporary lux
("tillfällig lyx", register 48132), whose "One time increase" heats the tank
once to the luxury temperature. That is what myUplink's own "Tillfällig lyx"
switch writes: on the F1255-16 CU this was developed against, every time EMS
switched it on the register read One time increase, and Off when EMS switched
it off. This switch writes the same two values through the gateway instead of
the cloud.

The 3, 6 and 12 hour settings stay with the register's own select. The switch
reads any of them as on, so a boost started at the pump does not look like an
idle tank.

The S-series calls its boost "More hot water" (40698), and neither the maps
nor NIBE's register documentation give its values, so it gets no switch yet.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

TITLE = "temporary lux"
ON_LABEL = "one time increase"
OFF_LABEL = "off"


@dataclass(frozen=True)
class Boost:
    register: int
    #: The raw value written to switch the boost on, and to switch it off.
    on: int
    off: int


def boost_register(registers: Mapping[int, dict], present: Iterable[int]) -> Boost | None:
    """The temporary lux register with its on and off values, if this pump has one."""
    for register in sorted(present):
        meta = registers.get(register)
        if not meta or not meta.get("write") or meta.get("title", "").lower() != TITLE:
            continue
        values = {
            str(label).lower(): int(value) for value, label in (meta.get("mappings") or {}).items()
        }
        if ON_LABEL in values and OFF_LABEL in values:
            return Boost(register, values[ON_LABEL], values[OFF_LABEL])
    return None
