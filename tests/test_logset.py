"""The LOG.SET generator writes what ModbusManager writes."""

from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path
import sys

from nibe.heatpump import Model
import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "make_logset.py"
spec = importlib.util.spec_from_file_location("make_logset_under_test", TOOL)
make_logset = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = make_logset
spec.loader.exec_module(make_logset)

F1255 = make_logset.model_map(Model.F1255)
DEFAULTS = make_logset.load_fseries().logset_registers(F1255)


def _lines(content: bytes) -> list[str]:
    return content.decode("ascii").split("\r\n")


def test_the_default_file_has_modbusmanagers_layout():
    content = make_logset.build(F1255, DEFAULTS, date(2026, 9, 14))
    lines = _lines(content)
    assert lines[0] == "[NIBL;20260914;9696]"
    assert lines[1].startswith("Divisors\t\t")
    assert lines[2].startswith("Date\tTime\t")
    assert lines[3:] == [str(r) for r in DEFAULTS]
    assert len(lines[1].split("\t")) == len(lines[2].split("\t")) == len(DEFAULTS) + 2


def test_crlf_ascii_and_no_final_newline():
    content = make_logset.build(F1255, DEFAULTS, date(2026, 9, 14))
    content.decode("ascii")
    assert b"\r\n" in content
    assert b"\n" not in content.replace(b"\r\n", b"")
    assert not content.endswith(b"\r\n")


def test_divisors_are_the_register_factors():
    content = make_logset.build(F1255, [40004, 43427, 43084], date(2026, 9, 14))
    assert _lines(content)[1] == "Divisors\t\t10\t1\t100"


def test_titles_carry_units_without_the_degree_sign():
    content = make_logset.build(F1255, [40004, 43437], date(2026, 9, 14))
    assert _lines(content)[2] == (
        "Date\tTime\tBT1 Outdoor Temperature [C]\tSupply Pump Speed EP14 [%]"
    )


def test_the_defaults_fill_exactly_twenty_slots():
    assert sum(make_logset.slots(F1255[r]) for r in DEFAULTS) == 20


def test_a_32_bit_register_counts_twice():
    nineteen = [r for r in DEFAULTS][:19]
    with pytest.raises(ValueError, match="21 slots"):
        make_logset.build(F1255, [*nineteen, 43416], date(2026, 9, 14))  # compressor starts, s32


@pytest.mark.parametrize(
    ("chosen", "message"),
    [([], "slots"), ([40004, 40004], "twice"), ([40001], "not in this model")],
)
def test_impossible_selections_are_refused(chosen, message):
    with pytest.raises(ValueError, match=message):
        make_logset.build(F1255, chosen, date(2026, 9, 14))


def test_the_command_line_writes_the_file(tmp_path):
    out = tmp_path / "LOG.SET"
    assert make_logset.main(["--out", str(out)]) == 0
    assert _lines(out.read_bytes())[3] == "40004"


def test_the_pump_only_reads_that_exact_name(tmp_path):
    with pytest.raises(SystemExit):
        make_logset.main(["--out", str(tmp_path / "LOG.SET.txt")])
