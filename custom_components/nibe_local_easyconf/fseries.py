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

from .const import is_accessory_flag

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


#: The gateway's network name: nibe-<the pump's serial>-gw, as the adapter names
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

#: Registers the pump answers but the library's F1155/F1255 map does not carry.
#:
#: 47260 is the fan speed selector of an exhaust air module: normal, or one of
#: the four speeds set in 47261-47265. NIBE leaves it out of its published
#: Modbus list - the library has it for the F370, F730, F750 and the VVM
#: models, where the fan is built in, but not for the F1155/F1255, where it
#: arrives with the FLM accessory. Owners found it anyway, and myUplink has
#: always shown it. The definition is the library's own, copied verbatim.
EXTRA_REGISTERS: dict[int, dict] = {
    47260: {
        "title": "Fan Mode",
        "size": "u8",
        "factor": 1,
        "min": 0,
        "max": 4,
        "write": True,
        "mappings": {
            "0": "Normal",
            "1": "Fan mode 1",
            "2": "Fan mode 2",
            "3": "Fan mode 3",
            "4": "Fan mode 4",
        },
    },
}

#: The accessories a pump can have, and the registers that come with each.
#:
#: Every register answers through the gateway whether its hardware is fitted or
#: not, so an exhaust air module that is not there would otherwise arrive as a
#: fan running at zero per cent. NIBE solves it for us: each accessory has a
#: register that says whether it is registered in the pump, titled "<name>
#: accessory", and its own registers carry the accessory's name. Setup reads
#: the flags, then reads the registers of the accessories that answered yes.
#:
#: `extra` is for registers that belong to an accessory without saying so in
#: their title, like the exhaust fan speeds that arrive with an FLM module.
#: Registers whose definition in the library is thinner than the pump's own
#: behaviour. 49280 sets which speed an exhaust air module runs at, and takes
#: the same values 43108 reports back, but the library gives it no labels and
#: no range, so it would arrive as a number between nothing and nothing.
REGISTER_PATCHES: dict[int, dict] = {
    49280: {
        "min": 0,
        "max": 4,
        "mappings": {
            "0": "Normal",
            "1": "Fan mode 1",
            "2": "Fan mode 2",
            "3": "Fan mode 3",
            "4": "Fan mode 4",
        },
    },
}


@dataclass(frozen=True)
class Accessory:
    flag: str
    prefixes: tuple[str, ...]
    extra: frozenset[str] = frozenset()


FAN_TITLES: frozenset[str] = frozenset({
    "Fan Mode",
    "Fan speed current",
    "Exhaust Fan speed normal",
    "Exhaust Fan speed 1",
    "Exhaust Fan speed 2",
    "Exhaust Fan speed 3",
    "Exhaust Fan speed 4",
})

ACCESSORIES: tuple[Accessory, ...] = (
    Accessory("FLM 1 accessory", ("FLM 1",), FAN_TITLES),
    Accessory("FLM 2 accessory", ("FLM 2",)),
    Accessory("FLM 3 accessory", ("FLM 3",)),
    Accessory("FLM 4 accessory", ("FLM 4",)),
    Accessory("ERS 1 accessory", ("ERS 1", "External ERS 1")),
    Accessory("ERS 2 accessory", ("ERS 2", "External ERS 2")),
    Accessory("ERS 3 accessory", ("ERS 3", "External ERS 3")),
    Accessory("ERS 4 accessory", ("ERS 4", "External ERS 4")),
    Accessory("Pool 1 accessory", ("Pool 1",)),
    Accessory("Pool 2 accessory", ("Pool 2",)),
)

#: Values NIBE answers with when an accessory is registered in the pump.
_FITTED = ("ON", "1", "1.0", "TRUE", "YES")


def accessory_for(title: str) -> Accessory | None:
    """The accessory a register belongs to, if any."""
    for accessory in ACCESSORIES:
        if title == accessory.flag or title in accessory.extra:
            return accessory
        if any(title.startswith(f"{prefix} ") for prefix in accessory.prefixes):
            return accessory
    return None


def flag_registers(registers: dict[int, dict]) -> list[int]:
    """Every register where the pump says whether an accessory is registered.

    More than the accessories in ACCESSORIES, which are the ones that bring
    registers of their own: a pump also answers for its room units, its extra
    climate systems and its boiler control, and "no" is half the answer.
    """
    flags = {accessory.flag for accessory in ACCESSORIES}
    return sorted(
        register
        for register, meta in registers.items()
        if (title := meta.get("title") or "") in flags or is_accessory_flag(title)
    )


def fitted_accessories(registers: dict[int, dict], values: dict[int, object]) -> list[Accessory]:
    """The accessories whose flag answered yes during the scan."""
    by_title = {meta.get("title"): register for register, meta in registers.items()}
    fitted = []
    for accessory in ACCESSORIES:
        register = by_title.get(accessory.flag)
        if register is not None and str(values.get(register)).upper() in _FITTED:
            fitted.append(accessory)
    return fitted


def accessory_registers(registers: dict[int, dict], values: dict[int, object]) -> list[int]:
    """What is worth reading once the flags are known: the registers of every
    accessory the pump says it has, and nothing for the ones it does not."""
    fitted = fitted_accessories(registers, values)
    wanted = set()
    for register, meta in registers.items():
        title = meta.get("title") or ""
        accessory = accessory_for(title)
        if accessory in fitted and title != accessory.flag:
            wanted.add(register)
    return sorted(wanted)


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

# -- what the pump costs and what it delivers --------------------------------
# The F-series keeps no electricity meter, so there is nothing to divide the
# heat by - which is why it had no coefficient of performance. It does report
# what the compressor and the immersion heater draw right now, and how fast its
# two circulation pumps are running, and its own heat meters count the heat it
# has delivered. Adding the power up over time gives the kilowatt hours the
# meter would have shown.

#: Power the pump reports, in kilowatts.
COMPRESSOR_POWER: int = 43141
ADDITION_POWER: int = 43084
#: The circulation pumps' speed, in percent.
HEAT_MEDIUM_PUMP_SPEED: int = 43437
BRINE_PUMP_SPEED: int = 43439
#: The pump's own heat meters, in kilowatt hours: heating, hot water, pool.
HEAT_METERS: tuple[int, ...] = (44300, 44298, 44304)

#: NIBE's own figures for the circulation pumps, watts at their lowest and at
#: their highest speed, read from "Elektrisk data" in the installer manual: the
#: brine pump (KB) first, then the heating medium pump (VB). A smaller pump has
#: smaller circulation pumps, so they are given per size.
CIRCULATION_PUMPS: dict[int, tuple[tuple[int, int], tuple[int, int]]] = {
    6: ((10, 87), (2, 63)),
    12: ((3, 180), (2, 60)),
    16: ((20, 180), (10, 87)),
}

#: The control system, the display and the relays, which run whatever else is
#: happening. NIBE publishes no figure for it; this is what an F-series draws
#: with both pumps stopped, and it is small enough that being a few watts out
#: moves a yearly coefficient of performance by about a hundredth.
ELECTRONICS_W: float = 15.0


def circulation_pumps(size: str | int | None) -> tuple[tuple[int, int], tuple[int, int]]:
    """The two circulation pumps' watt figures for a pump of this size.

    An unknown size gets the middle of NIBE's range rather than nothing: the
    pumps are a few percent of what the compressor draws, so a size that the
    serial did not name is better served by a good guess than by zero.
    """
    known = CIRCULATION_PUMPS
    try:
        kilowatts = int(size)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return known[12]
    if kilowatts in known:
        return known[kilowatts]
    return known[min(known, key=lambda each: abs(each - kilowatts))]


def pump_watts(limits: tuple[int, int], speed: float | None) -> float:
    """What a circulation pump draws at that speed.

    A pump's power follows the cube of its speed, and NIBE's two figures are
    the ends of it. One that stands still draws nothing at all.
    """
    if speed is None:
        return 0.0
    share = max(0.0, min(float(speed), 100.0)) / 100.0
    if share <= 0:
        return 0.0
    low, high = limits
    return low + (high - low) * share**3


def default_registers(registers: dict[int, dict]) -> list[int]:
    """The registers setup reads first: the usual ones, and the flags that say
    which accessories the pump has."""
    wanted = {r for r, meta in registers.items() if meta.get("title") in DEFAULT_TITLES}
    return sorted(wanted | set(flag_registers(registers)))


def is_default(meta: dict, reporting: bool) -> bool:
    """Whether a register's entity is switched on when first created.

    An accessory's registers are only read when its flag said the accessory is
    there, so one that reported a value has hardware behind it.
    """
    title = meta.get("title") or ""
    if meta.get("type") == "date" or not reporting:
        return False
    return (
        title in DEFAULT_TITLES
        or is_accessory_flag(title)
        or accessory_for(title) is not None
    )


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
