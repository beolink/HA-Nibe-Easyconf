"""NIBE F-series: which pump it is, and what a normal installation cares about.

The S-series half of this integration settles what a pump has by probing it
over Modbus TCP. Through a NibeGW gateway that approach does not carry over,
for reasons measured on an F1255-16 (see gateway.py):

* The pump names itself. Every fifteen seconds it sends a product message such
  as "F1255-16 CU" with its software version, so there is no model to pick and
  no register fingerprint to guess from.
* It answers every register, fitted or not, so which registers exist is not a
  question the bus can answer - only which ones report a value.
* Every read costs a second. A full scan of the 982 registers in the F1155/
  F1255 map takes a quarter of an hour.

So setup reads the registers below, the ones worth showing by default, and an
entity is switched on only when its register reported a value. Everything else
in the map still becomes an entity, switched off, as on the S-series.

The titles are NIBE's, as the `nibe` library ships them; they are the same
across every F-series map, so one list serves the F1145 up to the VVM 500.

No Home Assistant imports: the tests check this module offline.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from nibe.heatpump import Model, Series

#: Model name -> nibe Model, for every F-series model the library maps.
F_SERIES_MODELS: dict[str, Model] = {
    name: model for name, model in Model.__members__.items() if model.series is Series.F
}

#: Config entry model key -> device label. Keys are lower case, like the
#: S-series keys in registry.MODEL_LABELS, and come from the product message.
MODEL_LABELS: dict[str, str] = {
    name.lower(): f"NIBE {name[:3]} {name[3:]}" if name[:3] in ("SMO", "VVM") else f"NIBE {name}"
    for name in F_SERIES_MODELS
}

_PRODUCT_RE = re.compile(r"^\s*(F|SMO|VVM)\s*(\d{2,4})\s*(?:-\s*(\d{1,2}))?\s*(.*?)\s*$", re.I)


@dataclass(frozen=True)
class Product:
    """What the pump says it is, split into the parts that mean something."""

    model: Model
    #: "F1255": the name the library and the register maps know it by.
    name: str
    #: "16": the size, in kW for the ground source pumps.
    size: str | None
    #: "CU": the variant suffix, e.g. copper or stainless tank, cooling, energy meter.
    variant: str | None
    #: The product message verbatim, "F1255-16 CU".
    text: str

    @property
    def key(self) -> str:
        return self.name.lower()

    @property
    def label(self) -> str:
        return f"NIBE {self.text}"


def identify_product(text: str | None) -> Product | None:
    """Split the pump's product message, or None for anything not F-series.

    The library has ProductInfo.identify_model for this, but it matches by
    substring in enum order, which cannot tell "VVM 320" (with a space, as NIBE
    writes it) from nothing at all.
    """
    if not text:
        return None
    match = _PRODUCT_RE.match(text)
    if not match:
        return None
    family, number, size, variant = match.groups()
    name = f"{family.upper()}{number}"
    model = F_SERIES_MODELS.get(name)
    if model is None:
        return None
    return Product(model=model, name=name, size=size, variant=variant or None, text=text.strip())


#: The gateway's network name: nibe-<the pump's serial>-gw, as esphome/ names
#: it, or plain nibe-gw. The S-series pump itself is NIBE-<serial>, without -gw.
_GATEWAY_HOSTNAME_RE = re.compile(r"^nibe(?:-\d{14})?-gw(?:[.-]|$)", re.I)


def is_gateway_hostname(hostname: str | None) -> bool:
    """Whether a DHCP or mDNS name belongs to a NibeGW gateway for a NIBE pump."""
    return bool(hostname and _GATEWAY_HOSTNAME_RE.match(hostname.strip()))


# -- what kind of machine ----------------------------------------------------

#: Ground source (brine-to-water) pumps.
GROUND_SOURCE = frozenset({"F1145", "F1245", "F1155", "F1255", "F1345", "F1355"})
#: Exhaust air pumps.
EXHAUST_AIR = frozenset({"F370", "F470", "F730", "F750"})

#: Registers whose reading reveals hardware the model name does not: a hot
#: water tank on a pump without one built in, and a cooling circuit. Read by
#: title, which is the same in every F-series map.
HOT_WATER_TITLES = frozenset({"BT6 HW Load", "BT7 HW Top"})
COOLING_TITLES = frozenset({"EQ1-BT64 Cool Supply Temp"})


def traits_for(product: Product, reporting_titles: set[str]) -> set[str]:
    """The same closed trait list the S-series detection produces.

    Ground source and exhaust air come from the model: an F1255 without an
    exhaust air module still answers the exhaust air sensor with a plausible
    room temperature, so a reading proves nothing there.
    """
    traits: set[str] = set()
    if product.name in GROUND_SOURCE:
        traits.add("ground_source")
    if product.name in EXHAUST_AIR:
        traits.add("exhaust_air")
    if reporting_titles & HOT_WATER_TITLES:
        traits.add("hot_water")
    if reporting_titles & COOLING_TITLES:
        traits.add("cooling")
    return traits


# -- what is on by default ---------------------------------------------------

#: Registers worth an enabled entity on a normal installation, by NIBE title.
#: One that does not report a value at setup - a room sensor, a cooling
#: circuit, current sensors - stays switched off like everything else.
DEFAULT_TITLES: frozenset[str] = frozenset({
    # temperatures
    "BT1 Outdoor Temperature",
    "BT1 Average",
    "BT2 Supply temp S1",
    "EB100-EP14-BT3 Return temp",
    "BT7 HW Top",
    "BT6 HW Load",
    "EB100-EP14-BT10 Brine In Temp",
    "EB100-EP14-BT11 Brine Out Temp",
    "EB100-EP14-BT12 Condensor Out",
    "EB100-EP14-BT14 Hot Gas Temp",
    "EB100-EP14-BT15 Liquid Line",
    "EB100-EP14-BT17 Suction",
    "BT50 Room Temp S1",
    "EQ1-BT64 Cool Supply Temp",
    "BT25 Ext. Supply",
    "Calc. Supply S1",
    # flow, where the sensor is fitted
    "BF1 EP14 Flow",
    # The current sensors (EB100-BE1..3) are left out: without them fitted the
    # pump reports a plausible 0.0 A even with the compressor running, which
    # no "no reading" check can tell from a real zero.
    # control
    "Degree Minutes (16 bit)",
    "Prio",
    "Alarm",
    # compressor and pumps
    "Compressor Frequency, Actual",
    "Compressor State EP14",
    "Compressor starts EB100-EP14",
    "Tot. op.time compr. EB100-EP14",
    "Tot. HW op.time compr. EB100-EP14",
    "compr. in power",
    "Supply Pump Speed EP14",
    "EP14-GP2 Brine Pump Status EP14",
    # additional heat
    "Int. el.add. Power",
    "Tot. op.time add.",
    "Tot. HW op.time add.",
    # produced energy, from the heat meter
    "Heat Meter - HW Cpr and Add EP14",
    "Heat Meter - Heat Cpr and Add EP14",
    # settings people change
    "Heat Curve S1",
    "Heat Offset S1",
    "Hot water comfort mode",
    "Temporary Lux",
    "Operational mode",
    "Max int add. power",
    "Allow Additive Heating",
    "Allow Heating",
    "Holiday - Activated",
    "Alarm Reset",
})

#: The 32-bit degree minutes register decodes inconsistently through MODBUS 40
#: (the F1255-16 returned the 16-bit value in both words), so it is never read
#: by default; "Degree Minutes (16 bit)" carries the same number.
UNRELIABLE_TITLES: frozenset[str] = frozenset({"Degree Minutes (32 bit)"})


def default_registers(registers: dict[int, dict]) -> list[int]:
    """The registers in a model's map that setup reads, in address order."""
    return sorted(r for r, meta in registers.items() if meta.get("title") in DEFAULT_TITLES)


def is_default(meta: dict, reporting: bool) -> bool:
    """Whether a register's entity is switched on when first created."""
    return reporting and meta.get("title") in DEFAULT_TITLES and meta.get("type") != "date"


#: What LOG.SET should make the pump push on its own, most dynamic first. At
#: most 20 registers take part; each is then fresh twice a second instead of
#: costing a read every cycle, and never read by the poll schedule.
LOGSET_TITLES: tuple[str, ...] = (
    "BT1 Outdoor Temperature",
    "BT2 Supply temp S1",
    "EB100-EP14-BT3 Return temp",
    "BT7 HW Top",
    "BT6 HW Load",
    "EB100-EP14-BT10 Brine In Temp",
    "EB100-EP14-BT11 Brine Out Temp",
    "EB100-EP14-BT12 Condensor Out",
    "EB100-EP14-BT14 Hot Gas Temp",
    "EB100-EP14-BT15 Liquid Line",
    "EB100-EP14-BT17 Suction",
    "Calc. Supply S1",
    "Degree Minutes (16 bit)",
    "Compressor Frequency, Actual",
    "Compressor State EP14",
    "Supply Pump Speed EP14",
    "EP14-GP2 Brine Pump Status EP14",
    "Int. el.add. Power",
    "Prio",
    "Alarm",
)
LOGSET_MAX = 20


def logset_registers(registers: dict[int, dict]) -> list[int]:
    """The LOG.SET registers that exist in this model's map, in priority order."""
    by_title = {meta.get("title"): register for register, meta in registers.items()}
    chosen = [by_title[title] for title in LOGSET_TITLES if title in by_title]
    return chosen[:LOGSET_MAX]


# -- words -------------------------------------------------------------------

#: The library's value labels, upper-cased, in Swedish. Labels not listed keep
#: NIBE's English with only the first letter capitalised.
LABELS_SV: dict[str, str] = {
    "OFF": "av",
    "ON": "på",
    "YES": "ja",
    "NO": "nej",
    "AUTO": "auto",
    "MANUAL": "manuell",
    "NORMAL": "normal",
    "ECONOMY": "ekonomi",
    "LUXURY": "lyx",
    "SMART CONTROL": "smart control",
    "HOT WATER": "varmvatten",
    "HEAT": "värme",
    "COOLING": "kyla",
    "POOL": "pool",
    "ACTIVE": "aktiv",
    "INACTIVE": "inaktiv",
    "ACTIVATED": "aktiverad",
    "NOT ACTIVATED": "ej aktiverad",
    "OPEN": "öppen",
    "CLOSED": "stängd",
    "RUNNING": "i drift",
    "STARTING": "startar",
    "STOPPED": "stoppad",
    "STOPPING": "stannar",
    "PASSIVE": "passiv",
    "BLOCKED": "blockerad",
    "UNBLOCKED": "ej blockerad",
    "INTERMITTENT": "intermittent",
    "CONTINOUS": "kontinuerlig",
    "CONTINUOUS": "kontinuerlig",
    "10-DAY MODE": "10-dagarsläge",
    "ADD. HEAT ONLY": "endast tillsats",
    "AWAY FROM HOME": "bortaläge",
    "VACATION": "semester",
    "DEFAULT": "normal",
    "AFFECTING": "påverkar",
    "NOT AFFECTING": "påverkar inte",
    "SHUNT OFF": "shunt av",
    "SHUNT OPEN": "shunt öppnar",
    "SHUNT CLOSED": "shunt stänger",
    "MANUAL SETTING": "manuell inställning",
    "RADIATOR": "radiator",
    "FLOOR HEATING": "golvvärme",
    "RADIATOR + FLOOR HEATING": "radiator + golvvärme",
    "USE LOG.SET": "använd LOG.SET",
    "IGNORE LOG.SET": "ignorera LOG.SET",
    "3H": "3 h",
    "6H": "6 h",
    "12H": "12 h",
    "ONE TIME INCREASE": "engångshöjning",
}


def _english(label: str) -> str:
    """NIBE's label with a capital first letter, leaving designations alone."""
    text = label.strip()
    if text.isupper() and not re.search(r"\d", text) and "." not in text:
        text = text.lower()
    return text[:1].upper() + text[1:]


def labels_for(meta: dict, language: str = "sv") -> dict[str, str] | None:
    """A register's value table in the viewer's language, keyed by raw value."""
    mappings = meta.get("mappings")
    if not mappings:
        return None
    sv = language.startswith("sv")
    result: dict[str, str] = {}
    for raw, label in mappings.items():
        text = LABELS_SV.get(label.strip().upper()) if sv else None
        text = _english(label) if text is None else text[:1].upper() + text[1:]
        result[str(raw)] = text
    return result


#: "Alarm" is the F-series alarm number. Its codes are not the S-series list's -
#: 163 is a missing phase there and a high condenser inlet temperature here -
#: so official.ALARMS must not be used to name them.
ALARM_TITLE = "Alarm"

#: Alarm number -> (svenska, English or None). From NIBE's alarm lists for
#: products with the Emmy display, by tools/extract_nibe_alarms_fseries.py. The
#: Swedish list is the newer one and decides what exists; an English title is
#: only there where the older English list agrees with it, since NIBE gave some
#: numbers new meanings in between.
ALARMS: dict[int, tuple[str, str | None]] = {
    int(code): (titles[0], titles[1])
    for code, titles in json.loads(
        (Path(__file__).parent / "alarms_fseries.json").read_text(encoding="utf-8")
    ).items()
}


def is_alarm_register(meta: dict) -> bool:
    return meta.get("title") == ALARM_TITLE


def alarm_text(code: float | None, language: str = "sv") -> str | None:
    """The alarm's title in the viewer's language, or its number when unknown."""
    if code is None:
        return None
    number = int(code)
    sv = language.startswith("sv")
    if number == 0:
        return "Inget larm" if sv else "No alarm"
    swedish, english = ALARMS.get(number, (None, None))
    if sv and swedish:
        return swedish
    if not sv and english:
        return english
    return f"Larm {number}" if sv else f"Alarm {number}"
