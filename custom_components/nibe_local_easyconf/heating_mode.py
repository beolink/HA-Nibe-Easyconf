"""Heating mode: blocked, eco, normal or boost, the way an energy manager steers a heat pump.

No NIBE map has a register for it. An energy manager such as EMS Steward
decides quarter by quarter whether the house heats as usual, holds back while
electricity is dear or stores heat while it is cheap, and it expects a select
offering exactly these four options to tell the pump.

The select turns a mode into the one lever every map has: the heat offset of
climate system 1, "temperatur" in menu 1.1 - register 47011 on the F-series,
40031 on the S-series. On an F1255 one step moves the supply temperature 2.5 °C
at every outdoor temperature (installer manual IHB SE 1614-2, page 35). The modes are
steps from the house's own normal offset, so heating is never switched off: a
blocked house coasts on its thermal mass with the minimum supply temperature
still guarding it, which is the bounded set-back EMS asks of a heat pump.

NIBE's own answer would be SG Ready, but on these pumps that is two contacts
on the input board, not a register, and smart home mode and smart price
adaption are read-only over MODBUS 40.

Normal is learned: the offset the pump had when the select first saw it. An
offset changed outside the select - at the pump, in myUplink, or through the
offset's own entity - is taken as meant:

* in normal it becomes the new normal, and the other modes follow it;
* in another mode it holds until the mode next changes, and normal stays.

The select shows the mode last chosen either way, so an energy manager does
not undo a change made by hand.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace

BLOCKED = "blocked"
ECO = "eco"
NORMAL = "normal"
BOOST = "boost"

#: The options, in order. EMS writes these ids, not translated words.
MODES: tuple[str, ...] = (BLOCKED, ECO, NORMAL, BOOST)

#: Steps from normal. EMS moves a thermostat 3 °C down when blocked, 1.5 °C
#: down in eco and 1 °C up in boost; the defaults take the same numbers as
#: steps, eco's rounded towards comfort.
DEFAULT_STEPS: Mapping[str, int] = {BLOCKED: -3, ECO: -1, BOOST: 1}

#: Options keys for the steps.
STEP_OPTIONS: Mapping[str, str] = {mode: f"heating_mode_{mode}" for mode in DEFAULT_STEPS}

#: The heat offset of climate system 1, by its title in each series' map.
OFFSET_TITLES = frozenset({"Heat Offset S1", "Heating offset climate system 1"})


@dataclass(frozen=True)
class ModeState:
    """What the select remembers across restarts."""

    mode: str
    #: The offset that is normal for this house.
    normal: int
    #: The offset the pump had when last seen, so a change can be told apart.
    offset: int


def offset_register(registers: Mapping[int, dict], present: Iterable[int]) -> int | None:
    """The writable heat offset of climate system 1, if this pump has one."""
    for register in sorted(present):
        meta = registers.get(register)
        if meta and meta.get("write") and meta.get("title") in OFFSET_TITLES:
            return register
    return None


def steps_from(options: Mapping) -> dict[str, int]:
    """Steps per mode: the entry's options where set, else the defaults."""
    steps = {
        mode: int(options.get(STEP_OPTIONS[mode], step)) for mode, step in DEFAULT_STEPS.items()
    }
    steps[NORMAL] = 0
    return steps


def offset_for(mode: str, normal: int, steps: Mapping[str, int], low: int, high: int) -> int:
    """The offset a mode writes, kept inside the register's range."""
    return max(low, min(high, normal + steps[mode]))


def learn(offset: int) -> ModeState:
    """The first sight of the pump: whatever it has is normal."""
    return ModeState(NORMAL, offset, offset)


def follow(state: ModeState, offset: int) -> ModeState:
    """The state once the pump's offset is seen at `offset` without a mode being chosen."""
    if offset == state.offset:
        return state
    if state.mode == NORMAL:
        return ModeState(NORMAL, offset, offset)
    return replace(state, offset=offset)


def chosen(state: ModeState, mode: str, offset: int) -> ModeState:
    """The state after `mode` was written and the pump stored `offset`."""
    if mode == NORMAL:
        return ModeState(NORMAL, offset, offset)
    return ModeState(mode, state.normal, offset)
