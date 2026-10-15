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

The S-series calls its boost "More hot water" (40698, eS8XhwSel in NIBE's
register list), and no map gives its values. Measured on the S1155 at the
first site on 2026-10-15: the value is a number of hours. Writing 4 set "More
hot water (Number of minutes)" (40226, eTimeManualXhw) to 240 and the pump
switched to hot water within ten seconds; 1 gave 60 minutes; 0 ended it at
once. The status register 31079 (eU8TmpLuxActive) says whether the charge the
boost started is still running. So on the S-series the switch writes three
hours - the smallest span NIBE's own menu offers - and off writes 0, and any
value above 0 reads as on. An energy manager that re-asserts on every quarter
keeps it going for as long as it wants; one that stops leaves at most three
hours behind it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

TITLE = "temporary lux"
ON_LABEL = "one time increase"
OFF_LABEL = "off"
#: The S-series register, and the hours its on writes.
HOURS_TITLE = "more hot water"
HOURS_ON = 3


@dataclass(frozen=True)
class Boost:
    register: int
    #: The raw value written to switch the boost on, and to switch it off.
    on: int
    off: int
    #: "one_time" for the F-series' one time increase, "hours" for the
    #: S-series' more hot water, which is a span rather than a charge.
    kind: str = "one_time"


def boost_register(registers: Mapping[int, dict], present: Iterable[int]) -> Boost | None:
    """The boost register with its on and off values, if this pump has one.

    Temporary lux with a value table on the F-series; more hot water, in
    hours, on the S-series.
    """
    for register in sorted(present):
        meta = registers.get(register)
        if not meta or not meta.get("write"):
            continue
        title = meta.get("title", "").lower()
        if title == HOURS_TITLE and not meta.get("mappings"):
            return Boost(register, HOURS_ON, 0, "hours")
        if title != TITLE:
            continue
        values = {
            str(label).lower(): int(value) for value, label in (meta.get("mappings") or {}).items()
        }
        if ON_LABEL in values and OFF_LABEL in values:
            return Boost(register, values[ON_LABEL], values[OFF_LABEL])
    return None
