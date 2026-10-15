"""Constants and the policy for which registers become entities by default."""

from __future__ import annotations

import re
from typing import Final

DOMAIN: Final = "nibe_local_easyconf"

CONF_MODEL: Final = "model"
CONF_UNIT_ID: Final = "unit_id"
CONF_SCAN_UNKNOWN: Final = "scan_unknown"
CONF_SEND_STATISTICS: Final = "send_statistics"
CONF_TRAITS: Final = "traits"
#: The 14-digit NIBE serial, when the pump's network name gave it away. Kept on
#: the device; only the article number and build date go into the report.
CONF_SERIAL: Final = "serial"

#: How the pump is reached. Absent on entries from before the F-series, which
#: are all Modbus TCP.
CONF_CONNECTION: Final = "connection"
CONNECTION_MODBUS_TCP: Final = "modbus_tcp"
CONNECTION_NIBEGW: Final = "nibegw"
#: NibeGW gateway ports: where it takes read requests and write requests.
CONF_READ_PORT: Final = "read_port"
CONF_WRITE_PORT: Final = "write_port"
#: The F-series pump's own product message, e.g. "F1255-16 CU".
CONF_PRODUCT: Final = "product"
#: Software version from the product message; the S-series reads a register.
CONF_FIRMWARE: Final = "firmware"
#: MODBUS 40's 32-bit word order (register 48852), as found at setup.
CONF_WORD_SWAP: Final = "word_swap"

#: Outdoor temperature (BT1) on every F-series map. Read once at start-up to
#: prove the gateway is there and the pump is talking to it.
GATEWAY_PROBE_REGISTER: Final = 40004

#: Shown in the options text so the user can read what is sent before deciding.
STATS_ENDPOINT: Final = "stats.rnet.se"
STATS_PRIVACY_URL: Final = "https://stats.rnet.se/integritet"

#: The pump's own lifetime energy counters, in tenths of a kWh: heat delivered
#: and electricity consumed. Their ratio is the coefficient of performance.
ENERGY_OUT_REGISTER: Final = 33822
ENERGY_IN_REGISTER: Final = 33824

#: Software version of the main control board (EB100). A plain number on the
#: S-series, and the only firmware the pump exposes over Modbus.
FIRMWARE_REGISTER: Final = 31497

DEFAULT_PORT: Final = 502
DEFAULT_UNIT_ID: Final = 1
DEFAULT_SCAN_INTERVAL: Final = 60

#: How long a single poll cycle may take before we log that it is falling behind.
SLOW_POLL_WARNING: Final = 30.0

SERVICE_RESCAN: Final = "rescan_registers"
SERVICE_IMPORT_HISTORY: Final = "import_energy_history"

#: Component designations worth an entity on a normal installation.
CORE_COMPONENTS: Final = frozenset({
    "BT1", "BT2", "BT3", "BT6", "BT7", "BT10", "BT11", "BT12", "BT14", "BT15",
    "BT16", "BT17", "BT20", "BT21", "BT22", "BT25", "BT50", "BT63", "BT64",
    "BT71", "BT74", "BP4", "BP8", "BE1", "BE2", "BE3", "GP1", "GP2", "GP12",
    "QN10", "BF1",
})

#: Titles matching any of these earn a default-enabled entity. Patterns are
#: deliberately specific: a broad r"\benergy\b" pulled in the 24 hourly
#: electricity-price settings and the whole 50-register "smart energy source"
#: tariff configuration, which nobody wants on a dashboard by default.
CORE_TITLE_PATTERNS: Final = tuple(
    re.compile(p, re.I)
    for p in (
        r"\bdegree.?minute",
        r"\bcompressor (frequency|status|state|starts)",
        r"\bcompressor power input\b",
        r"\brequested compressor frequency$",
        r"\btotal (run |operating )time",
        r"\bpriority$",
        r"\bhot water (mode|demand|charging|top)\b",
        r"\bcalculated supply climate system 1\b",
        r"\bheating (curve|offset) climate system 1\b",
        r"\balarm (number|action)\b",
        r"\bclass 1 alarm\b",
        r"\breset alarm\b",
        r"\bfan speed\b",
        r"\bheating medium pump speed\b",
        r"\bdefrosting\b",
        r"\boperating mode( |$)",
        r"\bpower internal additional heat\b",
        r"\btotal energy\b",
        r"\b(current|instantaneous used) power\b",
        r"\benergy log - (produced|used) energy\b",
        r"\benergy log - current power consumption$",
        r"\btemporary lux\b",
        r"\bdiverter valve hot water\b",
        r"\bmax\.? internal additional heat$",
        r"\bpermit additional heat, heating\b",
        # The two lifetime counters behind the COP, and what the Energy
        # dashboard wants: heat delivered and electricity consumed.
        r"^tot\. (production|consumption)$",
    )
)

#: Registers that belong to hardware most installations do not have, plus the
#: large tariff/price configuration families. The pump answers all of these with
#: plausible-looking values whether or not the hardware exists, so they are
#: created disabled and only appear if the user goes looking for them.
NON_DEFAULT: Final = tuple(
    re.compile(p, re.I)
    for p in (
        r"\bEB10[1-8]\b",
        r"\bheat pump [2-8]\b",
        r"\b(clim\.|climate) system [2-8]\b",
        r"\bsystem [2-8]\b",
        r"\bzone \d+",
        r"\bEP(2[1-3]|4[4-7])\b",
        r"\bers [2-4]\b",
        r"\bfloor drying\b",
        r"\bsolar\b",
        r"\bpool\b",
        r"\bsmart energy source\b",
        r"\benergy price\b",
        r"\bel\. price\b",
        r"\btariff\b",
        r"\bprim\. factor\b",
        r"\bexternal reading of\b",
        r"\bSPA\b|\bsmart price adaption\b",
        r"\b(start|end) (month|day)\b",
        # S-series 40019, "Limit DM" until nibe 2.25 retitled it as the degree
        # minutes in 16 bits, which 40012 already shows in 32. It stays off as
        # it was, or every existing installation would have it switched on.
        # The F-series spells it with a capital M and settles its defaults in
        # fseries.is_default, so this is the S-series alone.
        r"^degree minutes \(16 bit\)$",
    )
)

_CODE_RE: Final = re.compile(r"\b([A-Z]{2}\d{1,3})\b")

#: Where the pump says whether an accessory is registered in its own menu. NIBE
#: ends every one of those titles with "accessory"; the room units and the
#: boiler control are the exceptions, and they are named here. A flag that says
#: no is as much of an answer as one that says yes, so they are all enabled and
#: gathered on the page under "accessories registered".
ACCESSORY_FLAG: Final = re.compile(
    r"\baccessory$|^rmu system \d$|^opt$|^system \d \(rmu\)$|modbus ?40"
    # NIBE leaves the word off a few of them: the hot water comfort accessory
    # with its own heater, and the two external energy meters.
    r"|^hw comfort$|^eme ?\d+ activated$",
    re.I,
)


def is_accessory_flag(title: str) -> bool:
    """Whether this register is one of those answers."""
    return bool(ACCESSORY_FLAG.search(title or ""))


def is_core_register(title: str, meta: dict) -> bool:
    """Whether this register earns an entity that is enabled out of the box.

    An S-series pump answers roughly 900 registers. Creating 900 enabled
    entities would bury the twenty that matter and make every poll cycle
    expensive, so everything else is registered disabled and can be switched on
    from the entity settings.
    """
    # Before the rest: a pool or a second climate system the pump does not have
    # is exactly what the flag is there to say.
    if is_accessory_flag(title):
        return True
    if any(pattern.search(title) for pattern in NON_DEFAULT):
        return False
    codes = set(_CODE_RE.findall(title))
    if codes & CORE_COMPONENTS:
        return True
    return any(pattern.search(title) for pattern in CORE_TITLE_PATTERNS)


#: Home Assistant platform each register maps onto.
PLATFORM_SENSOR: Final = "sensor"
PLATFORM_BINARY_SENSOR: Final = "binary_sensor"
PLATFORM_NUMBER: Final = "number"
PLATFORM_SELECT: Final = "select"
PLATFORM_SWITCH: Final = "switch"
PLATFORM_BUTTON: Final = "button"
PLATFORM_CLIMATE: Final = "climate"
PLATFORM_WATER_HEATER: Final = "water_heater"

#: The platforms a register lands on, one entity each.
REGISTER_PLATFORMS: Final = (
    PLATFORM_SENSOR,
    PLATFORM_BINARY_SENSOR,
    PLATFORM_BUTTON,
    PLATFORM_NUMBER,
    PLATFORM_SELECT,
    PLATFORM_SWITCH,
)

#: Everything that is set up: the register platforms, and the two entities
#: made of several registers each - the thermostat and the water heater.
PLATFORMS: Final = (*REGISTER_PLATFORMS, PLATFORM_CLIMATE, PLATFORM_WATER_HEATER)

#: Writable registers that do one thing when written and say nothing when
#: read: "Reset alarm by setting value 1", as the F-series map puts its 45171.
#: As numbers they showed 0 for ever; a button is what they are.
MOMENTARY_TITLES: Final = frozenset({"Alarm Reset", "Reset alarm"})


def _is_boolean(meta: dict) -> bool:
    """A 0/1 register with no unit behaves as a flag, not a measurement."""
    return (
        meta.get("min") == 0
        and meta.get("max") == 1
        and not meta.get("unit")
        and not meta.get("mappings")
    )


def platform_for(meta: dict) -> str:
    """Decide which platform a register belongs on.

    Writable registers become controls, read-only ones become sensors. A value
    mapping turns a control into a dropdown and a reading into an enum sensor;
    a plain 0/1 range becomes a switch or a binary sensor. A register that is
    only ever written becomes a button.
    """
    writable = bool(meta.get("write"))
    if writable and meta.get("title") in MOMENTARY_TITLES:
        return PLATFORM_BUTTON
    if meta.get("mappings"):
        return PLATFORM_SELECT if writable else PLATFORM_SENSOR
    if _is_boolean(meta):
        return PLATFORM_SWITCH if writable else PLATFORM_BINARY_SENSOR
    return PLATFORM_NUMBER if writable else PLATFORM_SENSOR
