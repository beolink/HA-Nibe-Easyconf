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
    )
)

_CODE_RE: Final = re.compile(r"\b([A-Z]{2}\d{1,3})\b")


def is_core_register(title: str, meta: dict) -> bool:
    """Whether this register earns an entity that is enabled out of the box.

    An S-series pump answers roughly 900 registers. Creating 900 enabled
    entities would bury the twenty that matter and make every poll cycle
    expensive, so everything else is registered disabled and can be switched on
    from the entity settings.
    """
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

PLATFORMS: Final = (
    PLATFORM_SENSOR,
    PLATFORM_BINARY_SENSOR,
    PLATFORM_NUMBER,
    PLATFORM_SELECT,
    PLATFORM_SWITCH,
)


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
    a plain 0/1 range becomes a switch or a binary sensor.
    """
    writable = bool(meta.get("write"))
    if meta.get("mappings"):
        return PLATFORM_SELECT if writable else PLATFORM_SENSOR
    if _is_boolean(meta):
        return PLATFORM_SWITCH if writable else PLATFORM_BINARY_SENSOR
    return PLATFORM_NUMBER if writable else PLATFORM_SENSOR
