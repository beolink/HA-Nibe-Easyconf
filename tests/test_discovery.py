"""Register addressing and the read-batching that keeps polling cheap."""

import importlib

from .conftest import PACKAGE

discovery = importlib.import_module(f"{PACKAGE}.discovery")
modbus = importlib.import_module(f"{PACKAGE}.modbus")


def test_register_numbers_map_to_function_codes():
    """3xxxx registers are input registers, 4xxxx are holding registers."""
    assert discovery.function_code(30002) == modbus.FC_READ_INPUT
    assert discovery.function_code(40012) == modbus.FC_READ_HOLDING
    assert discovery.function_code(47398) == modbus.FC_READ_HOLDING


def test_addresses_are_one_below_the_register_number():
    assert discovery.modbus_address(30002) == 1
    assert discovery.modbus_address(40001) == 0
    assert discovery.modbus_address(46065) == 6064


def test_contiguous_runs():
    assert discovery._contiguous([1, 2, 3, 7, 8, 20]) == [(1, 3), (7, 2), (20, 1)]
    assert discovery._contiguous([]) == []
    assert discovery._contiguous([5]) == [(5, 1)]


def _meta(size="s16"):
    return {"size": size, "factor": 1, "title": "t"}


def test_spans_cover_every_wanted_register():
    registers = {30002: _meta(), 30003: _meta(), 30010: _meta()}
    spans = discovery.plan_spans(registers, set(registers))
    covered = {
        address
        for span in spans
        for address in range(span.start, span.start + span.count)
    }
    for register in registers:
        assert discovery.modbus_address(register) in covered


def test_32bit_registers_claim_both_words():
    registers = {31535: _meta("u32")}
    spans = discovery.plan_spans(registers, {31535})
    assert sum(span.count for span in spans) == 2


def test_gaps_are_bridged_only_across_implemented_registers():
    """One extra word on the wire is far cheaper than another round-trip -
    but only if the pump actually implements the register in between."""
    registers = {30002: _meta(), 30003: _meta(), 30004: _meta()}
    wanted = {30002, 30004}

    # 30003 is not implemented, so the two reads must stay apart.
    assert len(discovery.plan_spans(registers, wanted, present=wanted)) == 2

    # With 30003 implemented, one read covers all three.
    bridged = discovery.plan_spans(registers, wanted, present=set(registers))
    assert len(bridged) == 1
    assert bridged[0].count == 3


def test_bridging_respects_the_gap_limit():
    registers = {30000 + i: _meta() for i in range(1, 60)}
    wanted = {30002, 30050}
    spans = discovery.plan_spans(registers, wanted, present=set(registers), max_gap=4)
    assert len(spans) == 2


def test_spans_never_exceed_the_read_limit():
    registers = {30000 + i: _meta() for i in range(1, 400)}
    spans = discovery.plan_spans(registers, set(registers), present=set(registers))
    assert spans
    assert all(span.count <= modbus.MAX_READ_COUNT for span in spans)


def test_illegal_function_means_the_register_is_absent():
    """NIBE answers 01 where the spec says 02; both must mean 'not here'."""
    assert modbus.ModbusError(1).not_implemented
    assert modbus.ModbusError(2).not_implemented
    assert not modbus.ModbusError(4).not_implemented
