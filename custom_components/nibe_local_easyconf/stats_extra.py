"""What this integration contributes to the anonymous daily report.

Deliberately free of Home Assistant imports, so the unit tests can prove
without a Home Assistant installation that nothing but the agreed fields can
leave the house. Everything here is either a fixed slug from a closed list or a
plain count. No string that came from the pump, the network or the user is ever
passed through.

The register scan is what this integration knows that no other does: which of
NIBE's documented registers a given machine actually implements, and how many
of those are reporting a value. Fleet-wide that is the thing worth having, and
counts carry it without a single register number or reading leaving the house.

See https://stats.rnet.se/integritet for the full list and the reasoning.
"""

from __future__ import annotations

from typing import Any

from .serial import parse_serial

#: The model the user picked in the config flow, mapped to a short slug. The
#: key set is closed, so a value typed by hand or added by a future release
#: reports as "other" rather than as itself.
MODEL_SLUGS = {
    "s1155": "s1155",
    "s1255": "s1255",
    "s1156": "s1156",
    "s1256": "s1256",
    "s2125": "s2125",
    "s320": "s320",
    "s325": "s325",
    "s330": "s330",
    "s332": "s332",
    "s735": "s735",
    "smos40": "smos40",
    "vvms320": "vvms320",
    "vvms325": "vvms325",
    "vvms500": "vvms500",
}

#: Detected machine characteristics. A closed list, and each is a property of
#: the hardware rather than of the household.
TRAIT_SLUGS = ("ground_source", "exhaust_air", "hot_water", "cooling")


def model_slug(model: str | None) -> str:
    """Map the configured model to a slug from the closed list above."""
    if not model:
        return "unknown"
    return MODEL_SLUGS.get(str(model).strip().lower(), "other")


def firmware_value(raw: Any) -> int | None:
    """The S-series reports its software version as a plain number.

    Anything that is not a plausible version number is dropped rather than
    coerced, so a sentinel or a stray string can never be filed as firmware.
    """
    if raw is None:
        return None
    try:
        number = int(raw)
    except (TypeError, ValueError):
        return None
    return number if 0 < number < 100000 else None


def _count(value: Any) -> int:
    """A non-negative whole number, whatever the caller passed."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, number)


class ErrorCounter:
    """Turns a cumulative failure count into 'since the previous report'.

    A reload resets the coordinator's counter, so a value lower than the one
    seen last time means a fresh start, not a negative number of failures.
    """

    def __init__(self) -> None:
        self._seen = 0

    def delta(self, total: int) -> int:
        if total < self._seen:
            self._seen = 0
        change = total - self._seen
        self._seen = total
        return change


def build_extra(
    model: str | None,
    *,
    traits: set[str] | None = None,
    registers_present: int = 0,
    registers_reporting: int = 0,
    registers_absent: int = 0,
    entities_enabled: int = 0,
    block_reads: int = 0,
    scan_interval_s: int = 0,
    read_failures: int = 0,
    firmware: Any = None,
    serial: Any = None,
) -> dict[str, Any]:
    """Build the integration specific part of the daily report.

    Counts only. Which registers were found is never sent, nor any value read
    from one: a register number is harmless on its own, but the set of them is
    a fingerprint of the installation, and the readings are the house.
    """
    traits = traits or set()
    parsed = parse_serial(serial)

    # The article number goes in the model list, not in metrics. The backend's
    # product_code metric is sized for CTC's four-digit codes (1000-9999) and
    # clamps anything larger without complaint, so NIBE's 065443 would be
    # stored as 9999. The model list keeps short strings verbatim, and an
    # article number is exactly what it is for: one model, size and variant.
    models = [model_slug(model)]
    if parsed is not None:
        models.append(parsed.article)

    payload: dict[str, Any] = {
        "models": models,
        "features": {
            # What the machine is, from the readings rather than the model name.
            **{trait: (trait in traits) for trait in TRAIT_SLUGS},
            # What the scan found. The single most useful number in the report:
            # published register maps do not say which registers a given unit
            # implements, and this is how that gets answered across a fleet.
            "registers_present": _count(registers_present),
            "registers_reporting": _count(registers_reporting),
            "registers_absent": _count(registers_absent),
            "entities_enabled": _count(entities_enabled),
            # How hard the integration works. These live in features rather
            # than metrics because the backend keeps metrics to a closed list
            # of physical quantities and drops anything else; features take
            # small whole numbers.
            "block_reads": _count(block_reads),
            "scan_interval_s": _count(scan_interval_s),
        },
        "errors": _count(read_failures),
    }

    # From the serial, the build year and week - the fields the CTC integration
    # sends, in the same shape. A week is shared by a whole production run, so
    # it does not point at a machine. The exact day stays local, and the
    # sequence number, the one part that identifies a unit, is never read here.
    if parsed is not None:
        payload["metrics"] = {"built_year": parsed.year, "built_week": parsed.iso_week}

    # A single string under "firmware". The shared stats.py passes only that
    # key through, so a "firmwares" object never left the house.
    version = firmware_value(firmware)
    if version is not None:
        payload["firmware"] = str(version)

    return payload
