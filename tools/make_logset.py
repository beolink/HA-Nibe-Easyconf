#!/usr/bin/env python3
"""Write a LOG.SET file for an F-series pump, without NIBE's Windows-only ModbusManager.

LOG.SET tells an F-series pump which registers to send to MODBUS 40 on its own
- or to the NibeGW gateway standing in for it - every couple of seconds, so the
integration never has to read them. The layout follows files ModbusManager made
(the sources are in docs/logset.md):

    [NIBL;<date>;<database version>]
    Divisors<TAB><TAB><divisor><TAB>...
    Date<TAB>Time<TAB><title [unit]><TAB>...
    <register>
    <register>
    ...

CRLF line endings, ASCII only and no final newline, as the one independent
generator known to work writes them. The pump takes the addresses; the two
header rows go into its own USB log files, which is why they carry divisors
and titles at all.

At most 20 slots are used, and a 32-bit register takes two. The default
selection is the one in custom_components/nibe_local_easyconf/fseries.py,
all 16-bit, because 32-bit values have been seen to arrive broken in pushes.

Usage:
    python tools/make_logset.py                      # F1255 defaults to ./LOG.SET
    python tools/make_logset.py --model F750 --out /Volumes/USB/LOG.SET
    python tools/make_logset.py --list               # show the selection only
    python tools/make_logset.py 40004 40008 43005    # your own registers
"""

from __future__ import annotations

import argparse
from datetime import date
from importlib.resources import files
import importlib.util
import json
from pathlib import Path
import sys
import unicodedata

from nibe.heatpump import Model, Series

ROOT = Path(__file__).resolve().parents[1]
FSERIES = ROOT / "custom_components" / "nibe_local_easyconf" / "fseries.py"

#: The ModbusManager database version in the header. Files with 8310 (2022)
#: and 9696 (2024) both worked; the pump does not appear to check it.
DATABASE_VERSION = 9696
MAX_SLOTS = 20


def load_fseries():
    """The integration's F-series module, which has no Home Assistant imports."""
    spec = importlib.util.spec_from_file_location("nibe_local_easyconf_fseries", FSERIES)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look their module up
    spec.loader.exec_module(module)
    return module


def model_map(model: Model) -> dict[int, dict]:
    raw = (files("nibe.data") / f"{model.data_file}.json").read_text(encoding="utf-8")
    return {int(key): value for key, value in json.loads(raw).items()}


def slots(meta: dict) -> int:
    return 2 if meta.get("size") in ("u32", "s32") else 1


def header_title(meta: dict) -> str:
    """NIBE's title with its unit, as ASCII: the pump's log files are not UTF-8."""
    unit = (meta.get("unit") or "").replace("°", "").strip()
    text = f"{meta['title']} [{unit}]" if unit else meta["title"]
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_text.split())


def build(registers: dict[int, dict], chosen: list[int], today: date) -> bytes:
    """The file's bytes. Raises ValueError when the selection does not fit."""
    unknown = [r for r in chosen if r not in registers]
    if unknown:
        raise ValueError(f"not in this model's register map: {unknown}")
    if len(set(chosen)) != len(chosen):
        raise ValueError("a register is listed twice")
    used = sum(slots(registers[r]) for r in chosen)
    if not chosen or used > MAX_SLOTS:
        raise ValueError(f"{used} slots selected; LOG.SET takes 1 to {MAX_SLOTS}")
    lines = [
        f"[NIBL;{today:%Y%m%d};{DATABASE_VERSION}]",
        "\t".join(["Divisors", ""] + [str(registers[r].get("factor", 1)) for r in chosen]),
        "\t".join(["Date", "Time"] + [header_title(registers[r]) for r in chosen]),
        *(str(r) for r in chosen),
    ]
    return "\r\n".join(lines).encode("ascii")


def main(argv: list[str] | None = None) -> int:
    fseries = load_fseries()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("registers", nargs="*", type=int, help="registers, in push order")
    parser.add_argument("--model", default="F1255", help="F-series model, e.g. F1255, F750, SMO40")
    parser.add_argument(
        "--out", default="LOG.SET", help="where to write, e.g. /Volumes/USB/LOG.SET"
    )
    parser.add_argument("--list", action="store_true", help="print the selection and write nothing")
    args = parser.parse_args(argv)

    model = fseries.F_SERIES_MODELS.get(args.model.upper().replace(" ", ""))
    if model is None or model.series is not Series.F:
        parser.error(f"not an F-series model: {args.model}")
    registers = model_map(model)
    chosen = args.registers or fseries.logset_registers(registers)

    for register in chosen:
        meta = registers.get(register, {})
        print(f"{register}  {meta.get('size', '?'):>3}  {meta.get('title', 'NOT IN MAP')}")
    try:
        content = build(registers, chosen, date.today())
    except ValueError as err:
        parser.error(str(err))
    if args.list:
        return 0

    out = Path(args.out)
    if out.name != "LOG.SET":
        parser.error("the pump only reads a file named exactly LOG.SET")
    out.write_bytes(content)
    print(f"Wrote {out} ({sum(slots(registers[r]) for r in chosen)} of {MAX_SLOTS} slots)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
