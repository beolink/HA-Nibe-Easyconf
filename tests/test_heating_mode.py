"""The heating mode: which offset each mode writes, and how a change by hand is taken."""

from __future__ import annotations

import asyncio
import importlib
from importlib.resources import files
import json

import pytest

from .conftest import PACKAGE

heating_mode = importlib.import_module(f"{PACKAGE}.heating_mode")
registry = importlib.import_module(f"{PACKAGE}.registry")

F1255_MAP = {
    int(key): value
    for key, value in json.loads((files("nibe.data") / "f1155_f1255.json").read_text()).items()
}

DEFAULTS = heating_mode.steps_from({})


def test_the_options_are_the_ids_ems_writes():
    # EMS Steward's load contract: a bound select offers exactly these.
    assert heating_mode.MODES == ("blocked", "eco", "normal", "boost")


def test_the_f_series_steers_heat_offset_s1():
    assert heating_mode.offset_register(F1255_MAP, F1255_MAP) == 47011


def test_the_s_series_steers_the_offset_of_climate_system_1():
    union = registry.union_map()
    assert heating_mode.offset_register(union, union) == 40031


def test_no_offset_among_what_the_pump_answered_means_no_heating_mode():
    present = set(F1255_MAP) - {47011}
    assert heating_mode.offset_register(F1255_MAP, present) is None


def test_the_default_steps_mirror_ems_thermostat_set_backs():
    assert DEFAULTS == {"blocked": -3, "eco": -1, "normal": 0, "boost": 1}


def test_steps_come_from_the_options_where_set():
    steps = heating_mode.steps_from({"heating_mode_eco": -2.0, "scan_interval": 60})
    assert steps == {"blocked": -3, "eco": -2, "normal": 0, "boost": 1}


@pytest.mark.parametrize(
    ("mode", "normal", "offset"),
    [
        ("blocked", 0, -3),
        ("eco", 0, -1),
        ("normal", 0, 0),
        ("boost", 0, 1),
        ("eco", 2, 1),
        ("blocked", -9, -10),  # kept inside the register's range
        ("boost", 10, 10),
    ],
)
def test_a_mode_writes_steps_from_normal(mode, normal, offset):
    assert heating_mode.offset_for(mode, normal, DEFAULTS, -10, 10) == offset


def test_the_first_offset_seen_is_normal():
    assert heating_mode.learn(-2) == heating_mode.ModeState("normal", -2, -2)


def test_an_unchanged_offset_changes_nothing():
    state = heating_mode.ModeState("eco", 0, -1)
    assert heating_mode.follow(state, -1) is state


def test_a_change_by_hand_in_normal_is_the_new_normal():
    state = heating_mode.ModeState("normal", 0, 0)
    assert heating_mode.follow(state, 1) == heating_mode.ModeState("normal", 1, 1)


def test_a_change_by_hand_in_another_mode_leaves_normal_alone():
    state = heating_mode.ModeState("blocked", 0, -3)
    assert heating_mode.follow(state, -2) == heating_mode.ModeState("blocked", 0, -2)


def test_choosing_normal_takes_what_the_pump_stored_as_normal():
    state = heating_mode.ModeState("eco", 0, -1)
    assert heating_mode.chosen(state, "normal", 0) == heating_mode.ModeState("normal", 0, 0)
    assert heating_mode.chosen(state, "boost", 1) == heating_mode.ModeState("boost", 0, 1)


# ------------------------------------------------------- the shared controller


class FakeStore:
    def __init__(self, data=None):
        self.data = data
        self.saved = 0

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.data = data
        self.saved += 1

    def async_delay_save(self, data_func, delay):
        self.data = data_func()
        self.saved += 1


class FakeCoordinator:
    """What the controller asks of a coordinator, and nothing more."""

    def __init__(self, offset):
        self.registers = {47011: {"title": "Heat Offset S1", "write": True, "min": -10, "max": 10}}
        self.data = {47011: offset}
        self.subscribed = []
        self.listeners = []
        self.writes = []
        self.redraws = 0

    def subscribe(self, register):
        self.subscribed.append(register)

    def unsubscribe(self, register):
        self.subscribed.remove(register)

    def async_add_listener(self, callback):
        self.listeners.append(callback)
        return lambda: self.listeners.remove(callback)

    def async_update_listeners(self):
        self.redraws += 1
        for callback in list(self.listeners):
            callback()

    async def async_write(self, register, value):
        self.writes.append((register, value))
        self.data = {**self.data, register: value}


def _controller(offset=0, stored=None):
    coordinator = FakeCoordinator(offset)
    controller = heating_mode.Controller(coordinator, 47011, DEFAULTS, FakeStore(stored))
    return coordinator, controller


def test_the_controller_learns_normal_when_it_starts_following():
    coordinator, controller = _controller(offset=2)
    assert controller.state is None and not controller.available
    stop = controller.start()
    assert coordinator.subscribed == [47011] and len(coordinator.listeners) == 1
    assert controller.state == heating_mode.ModeState("normal", 2, 2)
    assert controller.available
    assert controller.offsets() == {"blocked": -1, "eco": 1, "normal": 2, "boost": 3}
    stop()
    assert coordinator.subscribed == [] and coordinator.listeners == []


def test_choosing_a_mode_writes_its_offset_and_redraws_everyone():
    coordinator, controller = _controller(offset=0)
    controller.start()
    asyncio.run(controller.async_choose("eco"))
    assert coordinator.writes == [(47011, -1)]
    assert controller.state == heating_mode.ModeState("eco", 0, -1)
    # The select and the thermostat both show the mode; one call reaches both.
    assert coordinator.redraws == 1
    # And the store holds it for the next start.
    assert controller._store.data == {"mode": "eco", "normal": 0, "offset": -1}


def test_the_read_back_of_its_own_write_is_not_a_change_by_hand():
    coordinator, controller = _controller(offset=0)
    controller.start()
    asyncio.run(controller.async_choose("blocked"))
    # The coordinator's next update carries the offset just written.
    coordinator.async_update_listeners()
    assert controller.state == heating_mode.ModeState("blocked", 0, -3)


def test_a_change_by_hand_reaches_the_controller_through_the_listener():
    coordinator, controller = _controller(offset=0)
    controller.start()
    coordinator.data = {47011: 1}  # turned up on the display, in normal
    coordinator.async_update_listeners()
    assert controller.state == heating_mode.ModeState("normal", 1, 1)
    asyncio.run(controller.async_choose("eco"))
    assert coordinator.writes[-1] == (47011, 0)


def test_the_stored_mode_is_taken_up_before_the_pump_is_followed():
    """A restart in eco must not learn eco's offset as normal."""
    _coordinator, controller = _controller(
        offset=-1, stored={"mode": "eco", "normal": 0, "offset": -1}
    )
    asyncio.run(controller.async_load())
    controller.start()
    assert controller.state == heating_mode.ModeState("eco", 0, -1)


def test_a_mode_cannot_be_chosen_before_the_offset_is_read():
    _coordinator, controller = _controller(offset=None)
    controller.start()
    assert not controller.available
    with pytest.raises(RuntimeError):
        asyncio.run(controller.async_choose("eco"))
    with pytest.raises(ValueError):
        asyncio.run(controller.async_choose("warm"))
