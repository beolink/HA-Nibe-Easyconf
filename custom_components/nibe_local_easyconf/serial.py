"""Decode a NIBE serial number into model, size and date of manufacture.

The serial is not readable over Modbus. On the development unit every one of
the 919 implemented registers was checked, 16-bit and 32-bit in both word
orders, for any digit group of the known serial: none matched. What the pump
does do is put it in its network name, `NIBE-<serial>`, which reaches Home
Assistant through DHCP and can also be recovered by reverse DNS.

NIBE documents the format for everything except NIBE SPLIT and NIBE Aria:

    digits  1-6   article number   -> which product, and which size of it
    digits  7-8   year of manufacture
    digits  9-11  day of that year (1-366, not a week number as CTC uses)
    digits 12-14  internal sequence number

    https://www.nibe.eu/sv-se/support/vanliga-fragor/faq-items/vad-betyder-siffrorna-i-serienumret-pa-en-nibe-produkt

The sequence number is the only part that identifies one machine; the rest is
shared by a whole production day of one variant. It is kept on the device in
Home Assistant, where the user can see it, and never goes into the anonymous
report.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import re

#: The hostname NIBE gives its pumps on the network.
_HOSTNAME_RE = re.compile(r"^nibe-(\d{14})(?:\b|\.|$)", re.I)

#: Article number -> (model key in registry.MODEL_LABELS, size label or None).
#:
#: Only numbers that could be corroborated are listed. Retailer listings turned
#: out to mix NIBE's real article numbers with their own SKUs and Swedish RSK
#: numbers (a seven-digit "6249382" for an S1256 is an RSK number, not NIBE's),
#: so an entry needed to normalise to NIBE's six-digit 06xxxx form and fit the
#: range its siblings occupy. Anything missing still decodes its date; the
#: anonymous report carries the article number, and the fleet fills this in.
ARTICLES: dict[str, tuple[str, str | None]] = {
    # S1155 - ground source, no integrated hot water tank
    "065438": ("s1155", None),
    "065439": ("s1155", "12"),
    "065440": ("s1155", None),
    "065443": ("s1155", "16"),
    "065446": ("s1155", None),
    "065447": ("s1155", None),
    "065448": ("s1155", None),
    "065506": ("s1155", None),
    # S1255 - ground source with integrated hot water tank
    "065452": ("s1255", "12"),
    "065454": ("s1255", "12"),
    "065460": ("s1255", "16"),
    "065462": ("s1255", "16"),
    "065464": ("s1255", "16"),
    "065465": ("s1255", "6"),
    "065467": ("s1255", "6"),
    "065472": ("s1255", "6"),
    # S1256
    "065710": ("s1256", "13"),
    # Indoor and control modules
    "069206": ("vvms320", None),
    "067654": ("smos40", None),
}


@dataclass(frozen=True)
class NibeSerial:
    serial: str
    article: str
    year: int
    day_of_year: int
    sequence: str

    @property
    def manufactured(self) -> date | None:
        """The day it was built, or None if the day number is impossible."""
        try:
            first = date(self.year, 1, 1)
        except ValueError:
            return None
        built = first + timedelta(days=self.day_of_year - 1)
        return built if built.year == self.year else None

    @property
    def iso_week(self) -> int | None:
        built = self.manufactured
        return built.isocalendar()[1] if built else None

    @property
    def model_key(self) -> str | None:
        entry = ARTICLES.get(self.article)
        return entry[0] if entry else None

    @property
    def size(self) -> str | None:
        entry = ARTICLES.get(self.article)
        return entry[1] if entry else None


def parse_serial(serial: str | None) -> NibeSerial | None:
    """Split a 14-digit NIBE serial, or return None if it is not one.

    Rejected unless the year and day make a real date, so a serial in some
    other format cannot be read as a date that never existed.
    """
    if not serial:
        return None
    digits = str(serial).strip()
    if not re.fullmatch(r"\d{14}", digits):
        return None
    year = 2000 + int(digits[6:8])
    day = int(digits[8:11])
    if not 1 <= day <= 366:
        return None
    parsed = NibeSerial(
        serial=digits,
        article=digits[:6],
        year=year,
        day_of_year=day,
        sequence=digits[11:],
    )
    return parsed if parsed.manufactured else None


def serial_from_hostname(hostname: str | None) -> str | None:
    """Pull the serial out of a `NIBE-<serial>` network name."""
    if not hostname:
        return None
    match = _HOSTNAME_RE.match(hostname.strip())
    return match.group(1) if match else None
