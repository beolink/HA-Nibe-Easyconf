"""Regenerate alarms_fseries.json from NIBE's alarm lists for products with the Emmy display.

    pip install pypdf
    python tools/extract_nibe_alarms_fseries.py LARMLISTA_SV.pdf [ALARM_LIST_EN.pdf]

The F-series (F1145 up to the VVM 500) uses a different alarm list from the
S-series, so these texts are kept apart from alarms.json. Both documents are
NIBE's and are not redistributed here:

* "Larmlista, NIBE-produkter med Emmy-display", version 5, 2020-10-26, Swedish:
  https://headless.nibe.eu/download/18.9a97aba184a9b5f272c66/1669796147755/Larms%C3%B6k%20Emmy%202044-5.pdf
* "Alarm list" for the same products, 1747-1, 2017-11-23, English:
  https://installer.nibe.eu/download/18.17fb7f4e185eab8ed4027e7/1676466235274/Alarm%20list%20Emmy%201747-1.pdf

The Swedish list is three years newer and decides which codes exist; the
English one supplies the English title where it has the code. Only the alarm
titles are taken, as for the S-series: the cause and the pump's reaction stay in
NIBE's document.

What shapes the script, much as for the S-series list:

* pypdf's layout mode keeps the table's columns apart, but splits words and
  numbers with stray spaces ("Givar fel BT 2", "10  0"). Its plain mode spaces
  words correctly but loses the columns. So each title is cut out of the layout
  text by column, then located, ignoring whitespace, in the plain text of the
  same page, and taken from there.
* A title cell can hold one text per product family ("Bergvärme: ... Frånluft:
  ..."); those become one title joined with " / ", as do codes NIBE lists twice.
* NIBE has given some codes a new meaning between the two editions: 150 is
  "High condensor out" in the English list of 2017 and a temporary high
  pressure alarm in the Swedish list of 2020. An English title is therefore
  kept only when it agrees with the Swedish one on everything checkable -
  component designations, numbers, the inverter alarm type, and the key terms
  in CONCEPTS - and otherwise left out, so the code reads as "Alarm 150"
  rather than as the wrong alarm.
"""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re
import sys

from pypdf import PdfReader

OUT = (
    Path(__file__).resolve().parents[1]
    / "custom_components" / "nibe_local_easyconf" / "alarms_fseries.json"
)

#: Header rows, squashed: the Swedish and the English table.
HEADERS = {"sv": "LarmnrLarmOrsakLarmtyp", "en": "NrAlarmCauseHeatpumpoperation"}

#: Family prefixes that start a second text inside one title cell.
VARIANT_PREFIX = re.compile(
    r"(?<=\S)\s*(?=(?:Bergvärme|Frånluft|Övriga|Ground source|Exhaust air|Others)\s*:)"
)


#: Swedish term -> the English it has to come with. A pattern, lower case.
CONCEPTS: dict[str, str] = {
    r"givar": r"sensor",
    r"kompressor": r"compressor",
    r"\bfas|fasfel|fasföljd": r"phase",
    r"högtryck|\bhp\b": r"high pressure|\bhp\b",
    r"lågtryck|\blp\b": r"low pressure|\blp\b",
    r"hetgas": r"hot gas",
    r"kondensor": r"condens",
    r"kondensvatten": r"condensation",
    r"frysskydd": r"freez",
    r"avfrost": r"defrost",
    r"förång": r"evaporat",
    r"komm": r"com",
    r"inverter": r"inverter",
    r"fläkt": r"\bfan\b",
    r"filter": r"filter",
    r"\bpool": r"pool",
    r"\bsol\b": r"solar",
    r"motorskydd": r"motor protection",
    r"laddpump": r"charge pump",
    r"blockerad": r"block",
    r"externt": r"external",
    r"elanod": r"anode",
    r"effektvakt": r"load monitor",
    r"förvärm": r"preheat",
    r"uteluft": r"outdoor air",
    r"frånluft": r"exhaust air",
    r"tilluft": r"supply air",
    r"luftflöde": r"air flow",
    r"serienummer": r"serial",
    r"pressostat": r"pressure switch",
    r"mjukstart": r"softstart",
    r"rumsenhet": r"room unit",
    r"\bslav": r"slave",
    r"grundvatten": r"ground ?water",
    r"grundkort": r"base card",
    r"ingångskort": r"input card",
    r"värmesystem": r"heating system",
    r"klimatsystem": r"climate system",
    r"temperaturbegräns": r"temperature limiter",
    r"\bkb\b|köldbärar": r"htf|brine",
}

#: Plain misprints in NIBE's English list.
MISPRINTS = {"Sensro": "Sensor"}

DESIGNATION = re.compile(r"\b[A-Z]{2}\d{1,3}\b")
ROMAN = re.compile(r"\b(?:I{1,3}|IV)\b")


def squash(text: str) -> str:
    return re.sub(r"\s+", "", text)


def tidy(title: str) -> str:
    """Undo what the PDF's line breaks and cell wrapping left in a title."""
    title = re.sub(r"(?<=[a-zåäö])\s?-\s(?=[a-zåäö])", "", title)  # "com- pressor"
    title = re.sub(r"-\s*/\s*", "-/", title)  # "kyla-/värmegivare" stays one word
    title = re.sub(r"(?<=[^\s-])\s*/\s*(?=\S)", " / ", title)  # "Fram/ returledning"
    return re.sub(r"\s{2,}", " ", title).strip()


def _numbers(text: str) -> set[str]:
    spaced = re.sub(r"(?<=[a-zåäö])(?=\d)", " ", text)  # "värmesystem2" -> "värmesystem 2"
    return set(re.findall(r"(?<![A-Z])\b\d+\b", spaced))


def agrees(swedish: str, english: str) -> bool:
    """Whether an English title plausibly names the same alarm as the Swedish one.

    A shared component designation settles it: "Givarfel: BT10 köldbärare in"
    and "Sensor fault: BT10" are the same alarm, however much more one says.
    """
    designations = set(DESIGNATION.findall(swedish))
    if designations != set(DESIGNATION.findall(english)):
        return False
    if _numbers(swedish) != _numbers(english):
        return False
    if set(ROMAN.findall(swedish)) != set(ROMAN.findall(english)):
        return False
    if designations:
        return True
    sv, en = swedish.lower(), english.lower()
    return all(
        re.search(english_term, en)
        for swedish_term, english_term in CONCEPTS.items()
        if re.search(swedish_term, sv)
    )


class Page:
    """One page's plain text, searchable while ignoring whitespace."""

    def __init__(self, plain: str) -> None:
        self.plain = plain
        self.index = [i for i, ch in enumerate(plain) if not ch.isspace()]
        self.squashed = "".join(plain[i] for i in self.index)

    def respace(self, fragment: str) -> str:
        """The fragment as the plain text spaces it, or collapsed if not found."""
        target = squash(fragment)
        if not target:
            return ""
        at = self.squashed.find(target)
        if at < 0:
            return " ".join(fragment.split())
        start, end = self.index[at], self.index[at + len(target) - 1] + 1
        return " ".join(self.plain[start:end].split())


def _columns(header: str) -> list[int]:
    """Where each column starts: at every run of two or more spaces."""
    return [match.start() for match in re.finditer(r"(?:^|(?<=\s\s))\S", header)]


def extract(pdf: Path, language: str) -> dict[int, list[str]]:
    """Alarm number -> the titles found for it, in document order."""
    reader = PdfReader(str(pdf))
    titles: dict[int, list[str]] = defaultdict(list)
    for page in reader.pages:
        plain = Page(page.extract_text())
        lines = page.extract_text(extraction_mode="layout").splitlines()
        header_at = next(
            (i for i, line in enumerate(lines) if squash(line).startswith(HEADERS[language])),
            None,
        )
        if header_at is None:
            continue
        starts = _columns(lines[header_at])
        # A cell's text can sit a character or two left of its heading.
        title_from, title_to = starts[1] - 2, starts[2] - 2

        rows: list[tuple[int, list[str]]] = []
        for line in lines[header_at + 1 :]:
            code_cell = squash(line[:title_from])
            title_cell = line[title_from:title_to].strip()
            if code_cell.isdigit() and title_cell:
                rows.append((int(code_cell), [title_cell]))
            elif code_cell.isdigit():
                continue  # the page number in the footer
            elif rows and title_cell and not code_cell:
                rows[-1][1].append(title_cell)

        for code, parts in rows:
            title = " ".join(plain.respace(part) for part in parts)
            title = VARIANT_PREFIX.sub(" / ", title).strip(" /")
            title = tidy(re.sub(r"\s*:\s*", ": ", title))
            for wrong, right in MISPRINTS.items():
                title = re.sub(rf"\b{wrong}\b", right, title)
            if title and title not in titles[code]:
                titles[code].append(title)
    return titles


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3):
        print(__doc__)
        return 2
    swedish = extract(Path(argv[1]), "sv")
    english = extract(Path(argv[2]), "en") if len(argv) == 3 else {}
    table: dict[str, list[str | None]] = {}
    disagreeing = []
    for code in sorted(swedish):
        sv = " / ".join(swedish[code])
        en = " / ".join(english.get(code, [])) or None
        if en is not None and not agrees(sv, en):
            disagreeing.append(f"{code}: {sv!r} / {en!r}")
            en = None
        table[str(code)] = [sv, en]
    OUT.write_text(json.dumps(table, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    missing = sum(1 for _sv, en in table.values() if en is None)
    print(f"Wrote {len(table)} alarms to {OUT} ({missing} without an English title)")
    for line in disagreeing:
        print(f"English title left out, it names another alarm: {line}")
    only_english = sorted(set(english) - set(swedish))
    if only_english:
        print(f"In the English list only, left out: {only_english}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
