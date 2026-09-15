"""Reading and writing through a NibeGW gateway, against a stand-in for the library.

The behaviours stubbed here were all measured on the F1255-16 CU through
esphome-nibe: a second per register, "no reading" instead of errors for
unfitted hardware, 0xFFFF8000 for an absent energy meter, and the 32-bit degree
minutes register failing to decode.
"""

from __future__ import annotations

import asyncio
import importlib

from nibe.coil import Coil, CoilData
from nibe.exceptions import (
    DecodeException,
    EncodeException,
    ProductInfoReadTimeoutException,
    ReadException,
    ReadTimeoutException,
    WriteDeniedException,
    WriteTimeoutException,
)
from nibe.heatpump import HeatPump, Model, ProductInfo
import pytest

from .conftest import PACKAGE

gateway = importlib.import_module(f"{PACKAGE}.gateway")


def _run(coro):
    return asyncio.run(coro)


def _coil(address=40004, size="s16", factor=10, write=False, **kwargs):
    return Coil(
        address, f"coil-{address}", f"Coil {address}", size, factor=factor, write=write, **kwargs
    )


# ------------------------------------------------------------ values in


def test_a_scaled_reading_passes_through():
    assert gateway.value_from_coil_data(CoilData(_coil(), 14.2)) == 14.2


def test_no_reading_stays_none():
    assert gateway.value_from_coil_data(CoilData(_coil(), None)) is None


def test_a_table_label_becomes_its_number():
    coil = _coil(43427, "u8", 1, mappings={"20": "Stopped", "60": "Running"})
    assert gateway.value_from_coil_data(CoilData(coil, "RUNNING")) == 60


def test_a_value_missing_from_the_table_keeps_its_number():
    coil = _coil(43427, "u8", 1, mappings={"20": "Stopped"})
    assert gateway.value_from_coil_data(CoilData(coil, "UNKNOWN (5)")) == 5


def test_an_absent_energy_meter_is_no_reading():
    """42075 EME20 Total Energy on the development unit: raw 0xFFFF8000."""
    coil = _coil(42075, "u32", 10, unit="kWh")
    assert gateway.value_from_coil_data(CoilData(coil, 0xFFFF8000 / 10)) is None


def test_a_real_32_bit_counter_is_kept():
    coil = _coil(43416, "s32", 1)
    assert gateway.value_from_coil_data(CoilData(coil, 86219)) == 86219


def test_dates_are_left_out():
    coil = _coil(48044, "u16", 1, write=True, type="date")
    assert gateway.value_from_coil_data(CoilData(coil, None)) is None


# ------------------------------------------------------------ values out


def test_a_setting_scaled_by_100_is_written_exactly():
    """int(0.29 * 100) is 28 in the library's own conversion."""
    coil = _coil(47212, "s16", 100, write=True, min=0, max=4500)
    data = gateway.coil_data_for_write(coil, 0.29)
    assert data.raw_value == 29
    data.validate()


def test_a_negative_offset_is_written_exactly():
    coil = _coil(47011, "s8", 1, write=True, min=-10, max=10)
    assert gateway.coil_data_for_write(coil, -3).raw_value == -3


def test_a_table_value_is_written_as_its_label():
    coil = _coil(47041, "s8", 1, write=True, mappings={"0": "Economy", "1": "Normal"})
    data = gateway.coil_data_for_write(coil, 1)
    assert data.value == "NORMAL" and data.raw_value == 1


def test_an_unknown_table_value_is_refused():
    coil = _coil(47041, "s8", 1, write=True, mappings={"0": "Economy"})
    with pytest.raises(gateway.GatewayRejected):
        gateway.coil_data_for_write(coil, 7)


def test_read_only_and_dates_are_refused():
    with pytest.raises(gateway.GatewayRejected):
        gateway.coil_data_for_write(_coil(), 1.0)
    with pytest.raises(gateway.GatewayRejected):
        gateway.coil_data_for_write(_coil(48044, "u16", 1, write=True, type="date"), 1)


# ------------------------------------------------------------ the client


class FakeNibeGW:
    """Answers like esphome-nibe did for the F1255-16, without a network."""

    instances: list[FakeNibeGW] = []

    def __init__(self, heatpump, remote_ip, **kwargs):
        self.heatpump = heatpump
        self.remote_ip = remote_ip
        self.kwargs = kwargs
        self.values: dict[int, object] = {40004: 14.2, 48852: "ON"}
        self.timeouts: set[int] = set()
        self.undecodable: set[int] = set()
        self.deny_writes = False
        self.product: ProductInfo | None = ProductInfo("F1255-16 CU", 9721)
        self.reads: list[int] = []
        self.writes: list[tuple[int, int]] = []
        self.started = self.stopped = False
        FakeNibeGW.instances.append(self)

    async def start(self):
        self.started = True
        if self.heatpump.word_swap is None:
            try:
                data = await self.read_coil(self.heatpump.get_coil_by_address(48852), 1)
                self.heatpump.word_swap = data.value == "ON"
            except Exception:
                pass

    async def stop(self):
        self.stopped = True

    async def read_coil(self, coil, timeout=5):
        self.reads.append(coil.address)
        if coil.address in self.timeouts:
            raise ReadTimeoutException(f"Timeout waiting for read response for {coil.name}")
        if coil.address in self.undecodable:
            raise ReadException("Failed decoding response") from DecodeException("bad")
        data = CoilData(coil, self.values.get(coil.address))
        self.heatpump.notify_coil_update(data)
        return data

    async def write_coil(self, coil_data, timeout=5):
        coil_data.validate()
        if self.deny_writes:
            raise WriteDeniedException("denied")
        try:
            raw = coil_data.raw_value
        except AssertionError as err:
            raise EncodeException(str(err)) from err
        self.writes.append((coil_data.coil.address, raw))

    async def read_product_info(self, timeout=20):
        if self.product is None:
            raise ProductInfoReadTimeoutException("no product message")
        return self.product

    def push(self, address, value):
        """What a LOG.SET telegram does: a value nobody asked for."""
        coil = self.heatpump.get_coil_by_address(address)
        self.heatpump.notify_coil_update(CoilData(coil, value))


@pytest.fixture
def client():
    FakeNibeGW.instances.clear()
    instance = gateway.GatewayClient("10.0.50.47", Model.F1255, connection_factory=FakeNibeGW)
    _run(instance.start())
    return instance


def _fake(client) -> FakeNibeGW:
    return client._connection


def test_start_opens_an_ephemeral_port_and_learns_the_word_order(client):
    fake = _fake(client)
    assert fake.kwargs["listening_port"] == 0
    assert fake.kwargs["remote_read_port"] == 9999 and fake.kwargs["remote_write_port"] == 10000
    assert fake.kwargs["read_retries"] == 1
    assert client.word_swap is True


def test_an_unknown_word_order_falls_back_to_the_factory_setting():
    FakeNibeGW.instances.clear()

    class Mute(FakeNibeGW):
        async def read_coil(self, coil, timeout=5):
            raise ReadTimeoutException("nothing")

    instance = gateway.GatewayClient("10.0.50.47", Model.F1255, connection_factory=Mute)
    _run(instance.start())
    assert instance.word_swap is gateway.DEFAULT_WORD_SWAP


def test_a_read_returns_the_number(client):
    assert _run(client.read(40004)) == 14.2


def test_a_lost_answer_is_a_timeout(client):
    _fake(client).timeouts.add(40008)
    with pytest.raises(gateway.GatewayTimeout):
        _run(client.read(40008))


def test_an_undecodable_register_is_an_error_but_not_a_timeout(client):
    _fake(client).undecodable.add(40940)
    with pytest.raises(gateway.GatewayError) as caught:
        _run(client.read(40940))
    assert not isinstance(caught.value, gateway.GatewayTimeout)


def test_a_register_outside_the_map_is_an_error(client):
    with pytest.raises(gateway.GatewayError):
        _run(client.read(40001))


def test_a_write_reaches_the_pump_as_a_raw_value(client):
    _run(client.write(47011, -2))  # Heat Offset S1
    assert _fake(client).writes == [(47011, -2)]


def test_a_refused_write_says_so(client):
    _fake(client).deny_writes = True
    with pytest.raises(gateway.GatewayRejected):
        _run(client.write(47011, 1))


def test_a_value_outside_the_limits_is_refused_before_it_is_sent(client):
    with pytest.raises(gateway.GatewayRejected):
        _run(client.write(47011, 99))
    assert _fake(client).writes == []


def test_a_write_that_times_out_is_a_timeout(client):
    async def slow(coil_data, timeout=5):
        raise WriteTimeoutException("no feedback")

    _fake(client).write_coil = slow
    with pytest.raises(gateway.GatewayTimeout):
        _run(client.write(47011, 1))


def test_listeners_see_pushed_values_as_numbers(client):
    seen = []
    remove = client.add_listener(lambda register, value: seen.append((register, value)))
    _fake(client).push(43427, "RUNNING")
    _fake(client).push(40033, None)
    remove()
    _fake(client).push(40004, 1.0)
    assert seen == [(43427, 60), (40033, None)]


def test_one_failing_listener_does_not_silence_the_rest(client):
    seen = []
    client.add_listener(lambda register, value: 1 / 0)
    client.add_listener(lambda register, value: seen.append(register))
    _fake(client).push(40004, 3.0)
    assert seen == [40004]


def test_stop_closes_the_connection(client):
    fake = _fake(client)
    _run(client.stop())
    assert fake.stopped and not client.started
    with pytest.raises(gateway.GatewayError):
        _run(client.read(40004))


# ------------------------------------------------------------ probing


def test_a_probe_sorts_readings_from_missing_hardware(client):
    fake = _fake(client)
    fake.values.update({40008: 30.6, 40033: None})
    fake.undecodable.add(40940)
    result = _run(gateway.probe(client, [40004, 40008, 40033, 40940]))
    assert result.reporting == {40004, 40008}
    assert result.silent == {40033}
    assert result.failed == {40940}
    assert result.probed == {40004, 40008, 40033, 40940}


def test_a_run_of_timeouts_means_the_gateway_is_gone(client):
    fake = _fake(client)
    fake.timeouts.update({40008, 40012, 40013, 40014})
    with pytest.raises(gateway.GatewayTimeout):
        _run(gateway.probe(client, [40004, 40008, 40012, 40013, 40014]))
    assert fake.reads[-3:] == [40008, 40012, 40013]


def test_scattered_timeouts_do_not_end_a_probe(client):
    fake = _fake(client)
    fake.timeouts.update({40008, 40013})
    result = _run(gateway.probe(client, [40004, 40008, 40012, 40013, 40014]))
    assert result.failed == {40008, 40013}


def test_progress_is_reported_per_register(client):
    progress = []
    _run(gateway.probe(client, [40004, 40004], progress=lambda *step: progress.append(step)))
    assert progress == [(1, 2), (2, 2)]


# ------------------------------------------------------------ identifying


def test_identification_announces_itself_before_waiting_for_the_product_message():
    FakeNibeGW.instances.clear()
    info = _run(gateway.async_identify_gateway("10.0.50.47", connection_factory=FakeNibeGW))
    assert info == ProductInfo("F1255-16 CU", 9721)
    fake = FakeNibeGW.instances[0]
    assert fake.reads == [gateway.ANNOUNCE_REGISTER]
    assert fake.stopped


def test_nothing_behind_the_address_is_none_not_an_exception():
    FakeNibeGW.instances.clear()

    class Nobody(FakeNibeGW):
        async def read_coil(self, coil, timeout=5):
            raise ReadTimeoutException("nothing")

    assert _run(gateway.async_identify_gateway("10.0.50.99", connection_factory=Nobody)) is None
    assert FakeNibeGW.instances[0].stopped


def test_a_gateway_without_a_product_message_is_none():
    FakeNibeGW.instances.clear()

    class Silent(FakeNibeGW):
        async def read_product_info(self, timeout=20):
            raise ProductInfoReadTimeoutException("no product message")

    assert _run(gateway.async_identify_gateway("10.0.50.47", connection_factory=Silent)) is None


# ------------------------------------------------------------ the schedule


REGISTERS = {
    40004: {"title": "BT1 Outdoor Temperature", "unit": "°C"},
    43416: {"title": "Compressor starts EB100-EP14"},
    43420: {"title": "Tot. op.time compr. EB100-EP14", "unit": "h"},
    47007: {"title": "Heat Curve S1", "write": True},
}


def test_measurements_settings_and_counters_have_their_own_pace():
    schedule = gateway.PollSchedule(60.0, REGISTERS)
    assert schedule.interval(40004) == 60.0
    assert schedule.interval(43416) == 300.0
    assert schedule.interval(43420) == 300.0
    assert schedule.interval(47007) == 600.0
    assert gateway.PollSchedule(120.0, REGISTERS).interval(47007) == 1200.0


def test_never_read_comes_first_then_the_most_overdue():
    schedule = gateway.PollSchedule(60.0, REGISTERS)
    schedule.seen(40004, 0.0)
    schedule.seen(43416, 0.0)
    # 43420 and 47007 were never read; then 40004 is 340 s late, 43416 100 s.
    assert schedule.due(REGISTERS, 400.0) == [43420, 47007, 40004, 43416]


def test_a_register_read_late_in_a_cycle_is_still_due_in_the_next():
    schedule = gateway.PollSchedule(60.0, REGISTERS)
    schedule.seen(40004, 20.0)
    assert schedule.due([40004], 60.0) == []
    assert schedule.due([40004], 66.0) == [40004]


def test_a_failing_register_backs_off_and_recovers():
    schedule = gateway.PollSchedule(60.0, REGISTERS)
    schedule.failed(40004, 0.0)
    assert schedule.due([40004], 59.0) == []
    assert schedule.due([40004], 60.0) == [40004]
    schedule.failed(40004, 60.0)
    assert schedule.due([40004], 179.0) == []
    for attempt in range(20):
        schedule.failed(40004, 1000.0 + attempt)
    assert schedule.retry_at[40004] <= 1019.0 + gateway.PollSchedule.MAX_BACKOFF
    schedule.seen(40004, 5000.0)
    assert 40004 not in schedule.failures


def test_a_pushed_register_is_never_read():
    schedule = gateway.PollSchedule(60.0, REGISTERS)
    for second in range(0, 600, 5):
        schedule.seen(40004, float(second))
        assert 40004 not in schedule.due([40004], second + 1.0)


def test_forgetting_a_register_starts_it_afresh():
    schedule = gateway.PollSchedule(60.0, REGISTERS)
    schedule.failed(40004, 0.0)
    schedule.forget(40004)
    assert schedule.due([40004], 1.0) == [40004]


def test_the_word_order_fixture_matches_the_library():
    """The fake relies on 48852 being the word swap register in the F1255 map."""
    heatpump = HeatPump(Model.F1255)
    _run(heatpump.initialize())
    assert heatpump.get_coil_by_address(48852).title == "Modbus40 Word Swap"
