"""NIBE's own documentation, turned into data the entities can use.

Two things come from the documents NIBE publishes for installers at
professional.nibe.eu -> Tjänster -> Verktyg -> Kommunikation -> NIBE Modbus:

* **Alarm texts**, from "Larmlista S-serien" (the class A alarm list). An alarm
  register reports a bare number; this turns 163 into "Fel fasföljd alt. saknad
  fas har uppmätts." NIBE reuses some codes for more than one alarm - 237 means
  a short running time in hot water/heating, in the compressor, or in cooling,
  depending on the unit - so those carry every meaning the list gives them
  rather than whichever happened to be listed last.

* **Value labels**, from the register table in "Modbus S-serien" (M12676SV,
  2026-02-19). The `nibe` register maps carry value tables for only four of the
  1222 registers on an S735, and label the hot water diverter valve "Off/On"
  where NIBE's own table says 0 = heating, 1 = hot water. Only rows that were
  unambiguous in the source are here: that table also carries a per-model
  compatibility matrix, and rows parsed from it are left out.

The alarm table is generated from the PDF into alarms.json; see tools/. The value labels
were read and transcribed by hand.

This module has no Home Assistant imports, so the tests can check it offline.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

Bilingual = tuple[str, str]  # (svenska, English)

NO_ALARM: Bilingual = ("Inget larm", "No alarm")

#: Alarm number -> (svenska, English). Class A alarms only: that is the list
#: NIBE publishes for the S-series. Generated from the PDF by
#: tools/extract_nibe_alarms.py, and kept as data rather than code so it can be
#: regenerated wholesale when NIBE revises the list.
ALARMS: dict[int, Bilingual] = {
    int(code): (texts[0], texts[1])
    for code, texts in json.loads(
        (Path(__file__).parent / "alarms.json").read_text(encoding="utf-8")
    ).items()
}

_ALARM_TITLE = re.compile(r"^(alarm number|larmnummer)\b", re.I)


def is_alarm_register(title: str) -> bool:
    """True for registers whose value is an alarm number from the list above.

    Deliberately narrow: "Inverter alarm code" numbers belong to the inverter's
    own list, and "Class 1 alarm" is a flag, so neither is translated here.
    """
    return bool(_ALARM_TITLE.match(title.strip()))


def alarm_text(code: int | float | None, language: str = "sv") -> str | None:
    """The text for an alarm number, in the viewer's language."""
    if code is None:
        return None
    number = int(code)
    index = 0 if language.startswith("sv") else 1
    if number == 0:
        return NO_ALARM[index]
    known = ALARMS.get(number)
    if known is not None:
        return known[index]
    return f"Larm {number}" if index == 0 else f"Alarm {number}"


OFF: Bilingual = ('av', 'off')
ON: Bilingual = ('på', 'on')
HEATING_HOT_WATER: dict[int, Bilingual] = {0: ("värme", "heating"), 1: ("varmvatten", "hot water")}
OFF_OPENING_CLOSING: dict[int, Bilingual] = {
    10: ("av", "off"), 20: ("öppnar", "opening"), 30: ("stänger", "closing"),
}
AUX_RELAY: dict[int, Bilingual] = {
    0: ("larmutgång", "alarm output"),
    1: ("grundvattenpump", "groundwater pump"),
    2: ("kyllägesindikering", "cooling mode indication"),
    3: ("varmvattencirkulation", "hot water circulation"),
    4: ("extern värmebärarpump", "external heating medium pump"),
    5: ("ej använd", "not used"),
    6: ("extern varmvattenväxelventil", "external hot water diverter valve"),
    10: ("aktiv kyla 4-rör", "active cooling, 4-pipe"),
    11: ("spa", "spa"),
    12: ("summalarm", "common alarm"),
    13: ("semester", "holiday"),
    14: ("veddockning", "wood-burner docking"),
    15: ("avfrostning", "defrosting"),
    16: ("solel", "solar power"),
    17: ("uteluftsspjäll", "outdoor air damper"),
    18: ("bortaläge", "away mode"),
    19: ("ventil tilluft", "supply air valve"),
    20: ("kyllägesindikering med fördröjning", "cooling mode indication, delayed"),
    22: ("EB102-QN10", "EB102-QN10"),
}

#: Register -> value -> (svenska, English), as NIBE's register table has them.
LABELS: dict[int, dict[int, Bilingual]] = {
    # --- readings --------------------------------------------------------
    31101: {0: OFF, 1: ON},                               # Kompressorstatus
    32197: HEATING_HOT_WATER,                              # Växelventil QN10
    31822: HEATING_HOT_WATER,                              # Växelventil QN35
    31035: {10: ("av", "off"), 20: ("aktiv", "active"), 30: ("passiv", "passive"),
            40: ("öppnar", "opening"), 50: ("stänger", "closing")},  # Shuntventil QN11
    31806: {0: ("av", "off"), 1: ("aktiv", "active"), 2: ("passiv", "passive")},  # Avfrostning
    31792: {0: ("av", "off"), 1: ("aktiv", "active"), 2: ("passiv", "passive")},
    31778: {0: ("av", "off"), 1: ("aktiv", "active"), 2: ("passiv", "passive")},
    31029: {10: ("av", "off"), 20: ("varmvatten", "hot water"), 30: ("värme", "heating"),
            40: ("pool", "pool"), 60: ("kyla", "cooling")},  # Driftprioritering
    32196: {0: ("inget larm", "no alarm"), 1: ("aktivt larm", "alarm active")},  # Aktivt larm
    31067: {0: OFF, 1: ON},                               # Extern VB-pump GP10
    31064: {0: OFF, 1: ON},                               # Varmvattencirkulation GP11
    31836: {0: OFF, 1: ON},                               # Cirkulationspump GP3
    31033: {0: ("inaktiv", "inactive"), **OFF_OPENING_CLOSING},  # Shunt klimatsystem 2
    32411: {0: ("stängd", "closed"), 1: ("öppen", "open")},  # Shuntstyrd köldbärare QN41
    31834: {0: OFF, 1: ON},                               # Passiv kylapump GP13
    31135: {0: ("stängd mot pool", "closed to pool"), 1: ("öppen mot pool", "open to pool")},
    31829: {0: OFF, 1: ON},                               # Cirkulationspump GP9/GP16
    31570: OFF_OPENING_CLOSING,                            # Värmedump QN36
    31571: OFF_OPENING_CLOSING,                            # Shuntventil QN18
    31831: {0: ("stängd", "closed"), 1: ("öppen", "open")},  # Växelventil QN12
    31832: {0: OFF, 1: ON},                               # ACS EQ1-GP14
    31569: {3: ("passiv", "passive"), 7: ("aktiv", "active")},  # Status ACS45
    # --- settings ----------------------------------------------------------
    40057: {0: ("litet", "small"), 1: ("medel", "medium"), 2: ("stort", "large"),
            3: ("används inte", "not used"), 4: ("smart control", "smart control")},
    40238: {0: ("auto", "auto"), 1: ("manuellt", "manual"),
            2: ("endast tillsats", "additional heat only")},  # Driftläge
    40097: {10: ("intermittent", "intermittent"), 20: ("kontinuerlig", "continuous"),
            30: ("10 dagar kontinuerlig", "10 days continuous")},  # Driftläge köldbärarpump
    40854: {0: ("auto", "auto"), 1: ("manuellt", "manual")},  # Driftläge värmebärarpump
    41320: {0: ("auto", "auto"), 1: ("manuellt", "manual")},  # Driftläge köldbärarpump
    40217: AUX_RELAY,                                      # AUX-relä AUX10
    40225: AUX_RELAY,                                      # AUX-relä AUX11
}


def labels_for(register: int, language: str = "sv") -> dict[str, str] | None:
    """The value labels for a register in one language, keyed as the maps key."""
    table = LABELS.get(register)
    if table is None:
        return None
    index = 0 if language.startswith("sv") else 1
    # First letter only: str.capitalize() would turn "EB102-QN10" into "Eb102-qn10".
    return {str(value): pair[index][:1].upper() + pair[index][1:] for value, pair in table.items()}
