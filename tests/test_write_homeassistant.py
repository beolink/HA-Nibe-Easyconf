"""The S-series write reads the register back, and shows what the pump kept.

An S-series pump acknowledges a write and may keep something else: a value
outside its own limits is clamped, and a 32-bit value sent low word first was
acknowledged and dropped (measured on the S1155 at site 120, register 42506).
Needs pytest-homeassistant-custom-component, as the coordinator imports Home
Assistant; skipped where that is not installed.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nibe_local_easyconf.const import DOMAIN
from custom_components.nibe_local_easyconf.coordinator import NibeCoordinator
from custom_components.nibe_local_easyconf.discovery import DiscoveryResult

REGISTERS = {
    40207: {
        "title": "Room sensor set point value climate system 1", "factor": 10, "unit": "°C",
        "size": "s16", "min": 50.0, "max": 300.0, "write": True,
    },
    42506: {
        "title": "Desired room temperature for zone 1", "factor": 10, "unit": "°C",
        "size": "s32", "min": 180.0, "max": 350.0, "write": True,
    },
}


class ClampingPump:
    """A Modbus client whose pump keeps at most 25.0 °C in the setpoint, and
    keeps a 32-bit write only in the order it was sent."""

    host, port, unit_id = "10.0.0.2", 502, 1

    def __init__(self):
        self.memory: dict[int, list[int]] = {}
        self.writes: list[tuple[int, list[int]]] = []

    async def write_register(self, address, value):
        self.writes.append((address, [value]))
        self.memory[address] = [min(value, 250)]

    async def write_registers(self, address, values):
        self.writes.append((address, list(values)))
        # The pump stores (high, low) and reads it out low word first.
        self.memory[address] = list(reversed(values))

    async def probe(self, fc, address, count):
        return self.memory.get(address)

    async def close(self):
        pass


async def _coordinator(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "10.0.0.2"})
    entry.add_to_hass(hass)
    client = ClampingPump()
    discovery = DiscoveryResult(present=set(REGISTERS), reporting=set(REGISTERS))
    coordinator = NibeCoordinator(hass, entry, client, discovery, registers=REGISTERS)
    coordinator.async_set_updated_data({40207: 20.0, 42506: 20.0})
    return coordinator, client


async def test_a_clamped_write_shows_what_the_pump_kept(hass):
    coordinator, client = await _coordinator(hass)
    await coordinator.async_write(40207, 28.0)
    assert client.writes == [(40207 - 40001, [280])]
    # Not the 28.0 that was sent: the 25.0 the pump holds.
    assert coordinator.data[40207] == 25.0


async def test_a_32_bit_write_goes_high_word_first_and_reads_back_as_sent(hass):
    coordinator, client = await _coordinator(hass)
    await coordinator.async_write(42506, 20.5)
    assert client.writes == [(42506 - 40001, [0, 205])]
    assert coordinator.data[42506] == 20.5


async def test_a_pump_that_does_not_answer_the_read_back_keeps_the_value_sent(hass):
    coordinator, client = await _coordinator(hass)
    client.memory = {}
    client.probe = lambda fc, address, count: _none()
    await coordinator.async_write(40207, 21.0)
    assert coordinator.data[40207] == 21.0


async def _none():
    return None
