"""Regenerate alarms.json from NIBE's published S-series alarm list.

    pip install pypdf
    python tools/extract_nibe_alarms.py path/to/alarmlist.pdf

The PDF is "Larmlista S-serien" from professional.nibe.eu -> Tjänster ->
Verktyg -> Kommunikation -> NIBE Modbus. It is NIBE's document and is not
redistributed here; download it from there.

Two things about the PDF shape this script:

* The English and Swedish titles share a line with nothing between them but
  whitespace, and either can contain wide internal gaps. pypdf's layout mode
  keeps the columns apart but clips the right-hand (Swedish) column at the page
  edge; plain mode keeps every character but loses the columns. So the English
  column is taken from layout mode, matched character by character (ignoring
  spaces) against the complete plain-mode line, and whatever follows it is the
  Swedish title.

* NIBE lists some codes more than once with different meanings - 237 is a short
  running time in hot water/heating, in the compressor, or in cooling - so every
  distinct meaning is kept, joined with " / ".
"""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re
import sys

from pypdf import PdfReader

#: The Swedish column starts at character 113-129 on every page; the English
#: column never reaches past ~100.
SV_COLUMN = 110

_CLASS = r"\d\s*/\s*[A-Z]\s*/\s*[A-Za-z]+\s+light"
LAYOUT_ROW = re.compile(rf"^(\s*(\d{{1,4}})\s+{_CLASS}\s+)(.*)$")
PLAIN_ROW = re.compile(rf"^\s*(\d{{1,4}})\s+({_CLASS})\s+(.*)$")

OUT = (
    Path(__file__).resolve().parents[1]
    / "custom_components" / "nibe_local_easyconf" / "alarms.json"
)


def _tidy(text: str) -> str:
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\b([A-Z]{1,3}) (\d)", r"\1\2", text)  # "BT 1" -> "BT1"
    return text.strip(" -\u2013")  # NIBE uses en dashes as well as hyphens


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text)


def extract(pdf: Path) -> dict[int, tuple[str, str]]:
    reader = PdfReader(str(pdf))

    english: list[tuple[int, str]] = []
    for page in reader.pages:
        for line in (page.extract_text(extraction_mode="layout") or "").splitlines():
            match = LAYOUT_ROW.match(line)
            if not match:
                continue
            base = len(match.group(1))
            segments = [
                (base + seg.start(), seg.group())
                for seg in re.finditer(r"\S+(?: \S+)*", line[base:])
            ]
            english.append(
                (int(match.group(2)), " ".join(t for pos, t in segments if pos < SV_COLUMN))
            )

    complete: list[tuple[int, str]] = []
    for page in reader.pages:
        for line in (page.extract_text() or "").splitlines():
            match = PLAIN_ROW.match(line)
            if match:
                complete.append((int(match.group(1)), match.group(3).strip()))

    if [code for code, _ in english] != [code for code, _ in complete]:
        raise SystemExit("Row order differs between the two extractions; not trusting it.")

    variants: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for (code, english_column), (_, rest) in zip(english, complete, strict=True):
        target = _squash(english_column)
        i = j = 0
        while i < len(rest) and j < len(target):
            if rest[i].isspace():
                i += 1
                continue
            if rest[i] != target[j]:
                break
            i += 1
            j += 1
        matched = bool(target) and j == len(target)
        en = _tidy(rest[:i]) if matched else _tidy(rest)
        sv = _tidy(rest[i:]) if matched else ""
        # A few rows have no Swedish title in NIBE's list; English stands in.
        variants[code].append((sv or en, en))

    def join(texts):
        seen: list[str] = []
        for text in texts:
            if text not in seen:
                seen.append(text)
        return " / ".join(seen)

    return {
        code: (join(sv for sv, _ in rows), join(en for _, en in rows))
        for code, rows in sorted(variants.items())
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    alarms = extract(Path(sys.argv[1]))
    OUT.write_text(
        json.dumps({str(k): v for k, v in alarms.items()}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(alarms)} alarm codes to {OUT}")


if __name__ == "__main__":
    main()
