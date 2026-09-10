"""Assemble the register map used for naming, scaling and describing registers.

NIBE publishes one Modbus map per model, and the `nibe` library packages them.
Picking a single map turned out to be the wrong approach:

* An S-series pump answers a *superset* of registers - roughly 3000 words on the
  unit this was developed against, against 1472 in the largest published map -
  so which registers respond says surprisingly little about which model it is.
  Fingerprinting on model-unique registers confidently identified a ground
  source pump (brine circuit live, every fan at zero, no exhaust air sensors) as
  an exhaust-air S735, purely because the S735 map is the most complete one and
  therefore owns the most "unique" generic registers.

* The maps barely disagree where they overlap. Across 1611 registers defined by
  more than one S-series map, only 8 carry a conflicting size, factor or unit,
  and title differences are cosmetic ("Condenser (BT12)" vs "Condenser sensor
  supply line (BT12)").

So the maps are merged into one union, conflicts resolved by majority vote, and
what the pump actually implements is settled by probing it instead. The model is
then only a label on the device, which the user picks or confirms.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from importlib.resources import files
import json
import logging

from .discovery import function_code, modbus_address
from .modbus import ModbusTransportError, NibeModbusClient

_LOGGER = logging.getLogger(__name__)

#: Models that speak Modbus TCP natively. Older F-series pumps need a NibeGW
#: gateway and are out of scope for this integration.
S_SERIES_MAPS = (
    "s1155_s1255", "s1156_s1256", "s2125", "s320_s325", "s330_s332",
    "s735", "smos40", "vvms320", "vvms320_vvms325", "vvms325", "vvms500",
)

#: Labels offered in the config flow. Purely cosmetic: it names the device.
MODEL_LABELS: dict[str, str] = {
    "s1155": "NIBE S1155",
    "s1255": "NIBE S1255",
    "s1156": "NIBE S1156",
    "s1256": "NIBE S1256",
    "s2125": "NIBE S2125",
    "s320": "NIBE S320",
    "s325": "NIBE S325",
    "s330": "NIBE S330",
    "s332": "NIBE S332",
    "s735": "NIBE S735",
    "smos40": "NIBE SMO S40",
    "vvms320": "NIBE VVM S320",
    "vvms325": "NIBE VVM S325",
    "vvms500": "NIBE VVM S500",
    "other": "Annan S-serie / other S-series",
}


async def async_union_map(hass) -> dict[int, dict]:
    """Load the register maps without blocking the event loop.

    `union_map` reads eleven JSON files off disk. That is fast, but Home
    Assistant rightly flags any file I/O performed inside the loop, so the first
    call is pushed to an executor. Afterwards the lru_cache makes the plain
    `union_map()` free, which is why the synchronous form is still used on hot
    paths once this has run.
    """
    return await hass.async_add_executor_job(union_map)


@lru_cache(maxsize=1)
def union_map() -> dict[int, dict]:
    """Every register any S-series map defines, merged into one.

    Where maps disagree, size/factor/unit are decided by majority vote and the
    most informative title wins. Registers defined by only one map are kept as
    they are - extra coverage costs nothing, because a register that this pump
    does not implement is filtered out by discovery anyway.
    """
    definitions: dict[int, list[dict]] = {}
    for name in S_SERIES_MAPS:
        try:
            raw = (files("nibe.data") / f"{name}.json").read_text(encoding="utf-8")
        except (FileNotFoundError, ModuleNotFoundError):
            _LOGGER.warning("Register map %s is missing from the nibe package", name)
            continue
        for key, value in json.loads(raw).items():
            definitions.setdefault(int(key), []).append(value)

    merged: dict[int, dict] = {}
    for register, variants in definitions.items():
        if len(variants) == 1:
            merged[register] = variants[0]
            continue
        entry = dict(max(variants, key=lambda v: (len(v.get("title", "")), "mappings" in v)))
        for field in ("size", "factor", "unit"):
            votes = Counter(v.get(field) for v in variants)
            entry[field] = votes.most_common(1)[0][0]
        if entry.get("unit") is None:
            entry.pop("unit", None)
        # A mapping table from any variant is better than none at all.
        if "mappings" not in entry:
            for variant in variants:
                if "mappings" in variant:
                    entry["mappings"] = variant["mappings"]
                    break
        merged[register] = entry
    return merged


#: Registers whose presence reveals what kind of machine this is. Chosen because
#: they are physically exclusive: a ground source pump has no exhaust air fan,
#: and an exhaust air pump has no brine circuit.
_TRAIT_REGISTERS: dict[str, tuple[int, ...]] = {
    "ground_source": (31522, 31523),      # brine in / brine out (BT10/BT11)
    "exhaust_air": (30082, 30084),        # supply air / exhaust air (BT22/BT20)
    "hot_water": (30010, 31689),          # hot water charging (BT6)
    "cooling": (30338,),                  # cooling supply (BT64)
}

TRAIT_LABELS: dict[str, tuple[str, str]] = {
    "ground_source": ("bergvärme/vätska-vatten", "ground source / brine-to-water"),
    "exhaust_air": ("frånluft", "exhaust air"),
    "hot_water": ("varmvattenproduktion", "hot water production"),
    "cooling": ("kyla", "cooling"),
}


async def detect_traits(
    client: NibeModbusClient, registers: dict[int, dict] | None = None
) -> set[str]:
    """Work out what the machine physically is, by reading telling sensors.

    This is deliberately based on readings rather than on which registers exist:
    the firmware answers for hardware it does not have, but an absent sensor
    still reports NIBE's "no value" sentinel.
    """
    from .codec import decode, word_count

    if registers is None:
        registers = union_map()
    traits: set[str] = set()
    for trait, candidates in _TRAIT_REGISTERS.items():
        for register in candidates:
            meta = registers.get(register)
            if meta is None:
                continue
            try:
                words = await client.probe(
                    function_code(register),
                    modbus_address(register),
                    word_count(meta.get("size", "s16")),
                )
            except ModbusTransportError:
                raise
            if words is None:
                continue
            if decode(meta, words) is not None:
                traits.add(trait)
                break
    return traits


def describe_traits(traits: set[str], language: str = "sv") -> str:
    """A short human summary of what was detected, for the config flow."""
    index = 0 if language.startswith("sv") else 1
    names = [TRAIT_LABELS[t][index] for t in sorted(traits) if t in TRAIT_LABELS]
    if not names:
        return "okänd typ" if index == 0 else "unknown type"
    return ", ".join(names)
