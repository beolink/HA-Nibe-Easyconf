"""Turn NIBE's terse register titles into text a human can act on.

NIBE labels registers with service-manual component designations. Roughly a
third of them carry no prose at all - register 31624 on an S735 is titled
exactly "(EB100-EP15-BT28)" - and only a handful of registers ship value
mappings, so even readable titles like "Hot water mode" leave 0/1/2/4
unexplained.

The glossary below decodes those designations. It was cross-checked against the
titles NIBE itself uses across all published model maps: where one model spells
a code out ("Supply air (AZ2-BT22)") and another gives only the code, the
spelled-out form pins the meaning. Codes that could not be pinned that way are
deliberately absent - an unknown code degrades to a structural description
("temperature sensor BT91, compressor module EB100-EP15") rather than a guess.
"""

from __future__ import annotations

import re

Bilingual = tuple[str, str]  # (svenska, English)

#: Designation prefix -> what kind of thing it is.
COMPONENT_TYPES: dict[str, Bilingual] = {
    "AA": ("kretskort", "circuit board"),
    "AZ": ("tillbehörsmodul", "accessory module"),
    "BE": ("strömgivare", "current sensor"),
    "BF": ("flödesgivare", "flow sensor"),
    "BM": ("givare", "sensor"),
    "BP": ("tryckgivare", "pressure sensor"),
    "BS": ("luftflödesgivare", "air flow sensor"),
    "BT": ("temperaturgivare", "temperature sensor"),
    "CL": ("pool", "pool"),
    "CM": ("expansionskärl", "expansion vessel"),
    "EB": ("värmepump-/elmodul", "heat pump / electrical unit"),
    "EM": ("extern modul", "external module"),
    "EP": ("system-/köldmediekrets", "system or refrigerant circuit"),
    "EQ": ("kylsystem", "cooling system"),
    "FD": ("temperaturbegränsare", "temperature limiter"),
    "FL": ("säkerhetsventil", "safety valve"),
    "FR": ("offeranod", "sacrificial anode"),
    "GP": ("pump eller fläkt", "pump or fan"),
    "GQ": ("fläkt", "fan"),
    "HQ": ("filter", "filter"),
    "KA": ("relä", "relay"),
    "QM": ("ventil", "valve"),
    "QN": ("styrventil", "motorised valve"),
    "RM": ("backventil", "check valve"),
    "XL": ("röranslutning", "pipe connection"),
}

#: Exact designation -> what that specific component measures or does.
COMPONENTS: dict[str, Bilingual] = {
    # --- temperatures ---------------------------------------------------
    "BT1": ("utetemperatur", "outdoor temperature"),
    "BT2": (
        "framledning, ut till värmesystemet",
        "supply line, out to the heating system",
    ),
    "BT3": (
        "returledning, tillbaka från värmesystemet",
        "return line, back from the heating system",
    ),
    "BT5": ("varmvatten, starttemperatur", "hot water start temperature"),
    "BT6": ("varmvatten, laddtemperatur", "hot water charging temperature"),
    "BT7": ("varmvatten, topptemperatur i tanken", "hot water temperature at the top of the tank"),
    "BT10": ("köldbärare in (från borrhål/kollektor)", "brine in (from borehole or collector)"),
    "BT11": ("köldbärare ut (till borrhål/kollektor)", "brine out (to borehole or collector)"),
    "BT12": ("kondensor, framledning", "condenser out"),
    "BT13": ("kondensor, returledning", "condenser return"),
    "BT14": ("hetgas efter kompressorn", "hot gas after the compressor"),
    "BT15": ("vätskeledning", "liquid line"),
    "BT16": ("förångare", "evaporator"),
    "BT17": ("sugas före kompressorn", "suction gas before the compressor"),
    "BT20": ("frånluft, luften som sugs ut ur huset", "exhaust air, drawn out of the house"),
    "BT21": ("avluft, efter värmeåtervinning", "vented air, after heat recovery"),
    "BT22": ("tilluft, in i huset", "supply air, into the house"),
    "BT23": ("uteluft in till ventilationen", "outdoor air into the ventilation"),
    "BT25": ("extern framledning", "external supply line"),
    "BT26": ("kollektor in", "collector in"),
    "BT27": ("kollektor ut", "collector out"),
    "BT28": (
        "utetemperatur (givare i kompressormodulen)",
        "outdoor temperature (sensor in the compressor module)",
    ),
    "BT29": ("kompressorns oljetemperatur", "compressor oil temperature"),
    "BT38": ("varmvatten ut", "hot water out"),
    "BT50": ("rumsgivare", "room sensor"),
    "BT51": ("pooltemperatur", "pool temperature"),
    "BT52": ("pann-/ackumulatortemperatur", "boiler or buffer tank temperature"),
    "BT53": ("solfångarpanel", "solar panel"),
    "BT54": ("solvärmeladdning", "solar charging"),
    "BT57": ("kollektor in", "collector in"),
    "BT58": ("kollektor ut", "collector out"),
    "BT61": ("framledning radiator", "radiator supply line"),
    "BT62": ("returledning radiator", "radiator return line"),
    "BT63": ("framledning efter tillsatsvärme", "supply line after additional heat"),
    "BT64": ("kylframledning", "cooling supply line"),
    "BT65": ("kylreturledning", "cooling return line"),
    "BT68": ("tillsatsvärme, framledning", "additional heat, supply line"),
    "BT69": ("tillsatsvärme, returledning", "additional heat, return line"),
    "BT70": ("varmvatten ut till tappstället", "hot water out to the tap"),
    "BT71": ("extern returledning", "external return line"),
    "BT74": ("rumsgivare, medelvärde", "room sensor, average"),
    "BT75": ("värmedumpstemperatur", "heat dump temperature"),
    "BT76": ("avfrostningsgivare", "defrosting sensor"),
    "BT77": ("inkommande luft", "incoming air"),
    "BT81": ("injektionsgas (EVI)", "injection gas (EVI)"),
    "BT82": ("varmvattencirkulation, retur", "hot water circulation return"),
    "BT83": (
        "varmvattenberedare, komfort",
        "hot water comfort cylinder",
    ),
    "BT84": ("förångartemperatur", "evaporator temperature"),
    # --- pressures ------------------------------------------------------
    "BP4": ("högtryck vid kondensorn", "high pressure at the condenser"),
    "BP8": ("lågtryck", "low pressure"),
    "BP9": ("högtryck", "high pressure"),
    "BP11": ("injektionstryck (EVI)", "injection pressure (EVI)"),
    "BP16": ("luftflödestryck", "air flow pressure"),
    # --- electrical -----------------------------------------------------
    "BE1": ("ström, fas 1", "current, phase 1"),
    "BE2": ("ström, fas 2", "current, phase 2"),
    "BE3": ("ström, fas 3", "current, phase 3"),
    "BE6": ("extern energimätare", "external energy meter"),
    "BE7": ("extern energimätare", "external energy meter"),
    "BE11": ("extern energimätare", "external energy meter"),
    "FD1": ("temperaturbegränsare, elpatron", "temperature limiter, immersion heater"),
    "FR1": ("elektrisk anod i varmvattenberedaren", "electrical anode in the hot water cylinder"),
    # --- pumps, fans and valves ----------------------------------------
    "GP1": ("värmebärarpump", "heat medium pump"),
    "GP2": ("köldbärarpump", "brine pump"),
    "GP6": ("värmebärarpump", "heat medium pump"),
    "GP8": ("laddpump", "charge pump"),
    "GP9": ("poolventil", "pool valve"),
    "GP10": ("extern värmebärarpump", "external heat medium pump"),
    "GP11": ("varmvattencirkulationspump (VVC)", "hot water circulation pump"),
    "GP12": ("intern laddpump", "internal charge pump"),
    "GP13": ("passiv kylpump", "passive cooling pump"),
    "QN10": ("växelventil värme/varmvatten", "diverter valve, heating vs hot water"),
    "QN12": ("ACS-ventil", "ACS valve"),
    "QN19": ("poolventil", "pool valve"),
    "QN35": ("varmvattenshunt", "hot water shunt"),
    "QN41": ("köldbärarshunt", "brine shunt"),
    "BF1": ("flöde i värmebärarkretsen", "flow in the heat medium circuit"),
    "BM1": ("luftfuktighet/tryck", "humidity or pressure"),
}

#: Module designations that scope a reading to a particular part of the machine.
MODULES: dict[str, Bilingual] = {
    "EB100": ("värmepumpen", "the heat pump"),
    "EB101": ("kompressormodul 1", "compressor module 1"),
    "EB102": ("kompressormodul 2", "compressor module 2"),
    "EB103": ("kompressormodul 3", "compressor module 3"),
    "EB104": ("kompressormodul 4", "compressor module 4"),
    "EB105": ("kompressormodul 5", "compressor module 5"),
    "EB106": ("kompressormodul 6", "compressor module 6"),
    "EB107": ("kompressormodul 7", "compressor module 7"),
    "EB108": ("kompressormodul 8", "compressor module 8"),
    "EP14": ("köldmediekretsen", "the refrigerant circuit"),
    "EP15": ("kompressormodulen", "the compressor module"),
    "EP21": ("klimatsystem 2", "climate system 2"),
    "EP22": ("klimatsystem 3", "climate system 3"),
    "EP23": ("klimatsystem 4", "climate system 4"),
    "EP44": ("klimatsystem 5", "climate system 5"),
    "EP45": ("klimatsystem 6", "climate system 6"),
    "EP46": ("klimatsystem 7", "climate system 7"),
    "EP47": ("klimatsystem 8", "climate system 8"),
    "EQ1": ("kylsystemet", "the cooling system"),
    "AZ2": ("tilluftsmodulen (SAM)", "the supply air module (SAM)"),
    "AZ10": ("frånluftsmodulen (F135)", "the exhaust air module (F135)"),
    "AZ30": ("ventilationstillbehöret (ERS)", "the ventilation accessory (ERS)"),
}

#: Concepts worth a sentence of their own, matched on words in the title.
CONCEPTS: list[tuple[re.Pattern, Bilingual]] = [
    (
        re.compile(r"\bdegree.?minute|\bgradminut", re.I),
        (
            "Gradminuter är pumpens värmeunderskott: det summerade avståndet mellan "
            "önskad och verklig framledningstemperatur. Talet sjunker när huset behöver "
            "värme och startar kompressorn när det når startgränsen (ofta -60).",
            "Degree minutes accumulate the gap between the wanted and the actual supply "
            "temperature. The value falls while the house needs heat and starts the "
            "compressor once it reaches the start threshold (often -60).",
        ),
    ),
    (
        re.compile(r"\bcompressor frequency|\bfrequency.*compressor|\bcpr.*freq", re.I),
        (
            "Kompressorns varvtal. En inverterstyrd pump moduleras mellan min och max "
            "istället för att slå av och på - låg frekvens under lång tid ger högre "
            "verkningsgrad än korta högvarviga pass.",
            "Compressor speed. An inverter-driven pump modulates between min and max "
            "instead of cycling on and off; running slowly for longer is more efficient "
            "than short bursts at high speed.",
        ),
    ),
    (
        re.compile(r"\bEEV\b|expansion valve", re.I),
        (
            "Elektronisk expansionsventil som styr hur mycket köldmedium som släpps in "
            "i förångaren. Öppningsgraden reglerar överhettningen.",
            "Electronic expansion valve controlling how much refrigerant enters the "
            "evaporator. Its opening degree regulates superheat.",
        ),
    ),
    (
        re.compile(r"\bEVI\b|injection", re.I),
        (
            "EVI (Enhanced Vapour Injection) sprutar in köldmedium mitt i kompressorn "
            "för att hålla kapaciteten uppe när det är kallt ute.",
            "EVI (Enhanced Vapour Injection) injects refrigerant midway through the "
            "compressor to sustain capacity in cold weather.",
        ),
    ),
    (
        re.compile(r"\bsuperheat|överhettning", re.I),
        (
            "Överhettning: hur många grader över förångningstemperaturen gasen är när "
            "den lämnar förångaren. För lågt värde riskerar vätska in i kompressorn.",
            "Superheat: how many degrees above evaporating temperature the gas is when "
            "it leaves the evaporator. Too low risks liquid entering the compressor.",
        ),
    ),
    (
        re.compile(r"\bdefrost|avfrost", re.I),
        (
            "Avfrostning smälter is på förångaren genom att tillfälligt vända "
            "köldmedieflödet. Under tiden levereras ingen värme till huset.",
            "Defrosting melts ice off the evaporator by briefly reversing the "
            "refrigerant flow. No heat reaches the house while it runs.",
        ),
    ),
    (
        re.compile(r"\bheat.?curve|\bkurva|\bcurve slope", re.I),
        (
            "Värmekurvan bestämmer hur varm framledningen ska vara vid en given "
            "utetemperatur. Högre kurva ger varmare hus men högre förbrukning.",
            "The heat curve sets how warm the supply line should be at a given outdoor "
            "temperature. A higher curve means a warmer house and higher consumption.",
        ),
    ),
    (
        re.compile(r"\bsmart price|\bprice adaption|\benergy price", re.I),
        (
            "Smart prisanpassning flyttar värme- och varmvattenproduktion till "
            "timmar med lägre elpris.",
            "Smart price adaption shifts heating and hot water production towards "
            "hours with a lower electricity price.",
        ),
    ),
    (
        re.compile(r"\bpriority|\bprioritering", re.I),
        (
            "Visar vad pumpen arbetar med just nu - värme, varmvatten, pool eller "
            "kyla. Bara en sak i taget.",
            "Shows what the pump is working on right now - heating, hot water, pool or "
            "cooling. Only one at a time.",
        ),
    ),
    (
        re.compile(r"\baddition|\btillsats|\bimmersion heater|\belpatron", re.I),
        (
            "Tillsatsvärme (elpatron) kopplas in när kompressorn inte räcker till. "
            "Den är dyr att använda - höga värden här syns direkt på elräkningen.",
            "Additional heat (immersion heater) kicks in when the compressor cannot "
            "keep up. It is expensive to run - high values here show up on the bill.",
        ),
    ),
]


#: Common English phrases NIBE uses in titles, and their Swedish equivalent.
#: Applied longest-first so "hot water top" wins over "hot water".
TITLE_PHRASES: dict[str, str] = {
    "current outdoor temperature": "utetemperatur",
    "outdoor temperature": "utetemperatur",
    "degree minutes": "gradminuter",
    "calculated supply temperature": "beräknad framledning",
    "calculated supply climate system": "beräknad framledning, klimatsystem",
    "compressor frequency": "kompressorfrekvens",
    "compressor status": "kompressorstatus",
    "compressor state": "kompressortillstånd",
    "compressor starts": "kompressorstarter",
    "total operating time": "total drifttid",
    "operating time": "drifttid",
    "number of starts": "antal starter",
    "hot water top": "varmvatten topp",
    "hot water charging": "varmvattenladdning",
    "hot water load temp.": "varmvatten laddtemperatur",
    "hot water mode": "varmvattenläge",
    "hot water demand": "varmvattenbehov",
    "hot water": "varmvatten",
    "supply line": "framledning",
    "return line": "returledning",
    "supply air": "tilluft",
    "exhaust air": "frånluft",
    "extract air": "frånluft",
    "vented air": "avluft",
    "exh. air": "frånluft",
    "supp. air": "tilluft",
    "room temp": "rumstemperatur",
    "room sensor": "rumsgivare",
    "fan speed": "fläktvarvtal",
    "min fan speed": "lägsta fläktvarvtal",
    "max fan speed": "högsta fläktvarvtal",
    "pump speed": "pumpvarvtal",
    "heating medium pump speed": "värmebärarpumpens varvtal",
    "brine pump speed": "köldbärarpumpens varvtal",
    "low pressure": "lågtryck",
    "high pressure": "högtryck",
    "hi press": "högtryck",
    "hot gas": "hetgas",
    "liquid line": "vätskeledning",
    "suction gas": "sugas",
    "suction": "sugas",
    "condensor out": "kondensor ut",
    "condenser out": "kondensor ut",
    "evaporator": "förångare",
    "brine in": "köldbärare in",
    "brine out": "köldbärare ut",
    "defrosting": "avfrostning",
    "additional heat": "tillsatsvärme",
    "add. heat": "tillsatsvärme",
    "internal electrical addition": "intern eltillsats",
    "electrical addition": "eltillsats",
    "priority": "prioritering",
    "heat curve": "värmekurva",
    "curve slope": "kurvlutning",
    "offset": "förskjutning",
    "energy price": "elpris",
    "current": "ström",
    "power": "effekt",
    "flow": "flöde",
    "humidity": "luftfuktighet",
    "temperature": "temperatur",
    "temp.": "temperatur",
    "status": "status",
    "average": "medelvärde",
    "setpoint": "börvärde",
    "set point": "börvärde",
    "degree of opening": "öppningsgrad",
    "heating": "värme",
    "cooling": "kyla",
    "pool": "pool",
    "ventilation": "ventilation",
    "alarm": "larm",
    "week": "vecka",
    "day": "dag",
    "night": "natt",
}

def _swedish_phrase(text: str) -> str | None:
    """Translate a title to Swedish only when the whole phrase is recognised.

    Substring substitution was tried first and rejected: it produced hybrids
    like "Kyla start at over temp", which are harder to read than the English
    NIBE ships. A partial match returns None so the original title survives.
    """
    return TITLE_PHRASES.get(text.lower().strip(" ,.-"))


_CODE_RE = re.compile(r"\b([A-Z]{2}\d{1,3})\b")


def _pick(text: Bilingual, language: str) -> str:
    return text[0] if language.startswith("sv") else text[1]


def _prose(title: str) -> str:
    """The human-readable part of a title, with designations stripped out."""
    without_groups = re.sub(r"\s*\([^)]*\)\s*", " ", title)
    without_codes = _CODE_RE.sub("", without_groups)
    return re.sub(r"\s{2,}", " ", without_codes).strip(" ,-")


def _sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    text = text[0].upper() + text[1:]
    return text if text.endswith(".") else text + "."


def _join(parts: list[str]) -> str:
    return " ".join(_sentence(p) for p in parts if p and p.strip())


def _scope_phrase(codes: list[str], language: str) -> str:
    """"in the compressor module, climate system 2" for the module codes present."""
    names = [_pick(MODULES[c], language) for c in codes if c in MODULES]
    if not names:
        return ""
    joined = ", ".join(names)
    return f" i {joined}" if language.startswith("sv") else f" in {joined}"


def describe(title: str, register: int, meta: dict, language: str = "sv") -> str:
    """Build a human-readable explanation of one register."""
    sv = language.startswith("sv")
    codes = _CODE_RE.findall(title)
    prose = _prose(title)
    measured = next((c for c in codes if c in COMPONENTS), None)
    scope = [c for c in codes if c in MODULES]
    sentences: list[str] = []

    # 1. Lead with whatever NIBE actually wrote, translated when we recognise it.
    if prose:
        sentences.append((_swedish_phrase(prose) if sv else None) or prose)

    # 2. Decode the designations into what is physically being measured.
    if measured:
        what = _pick(COMPONENTS[measured], language)
        where = _scope_phrase(scope, language)
        if prose:
            already_said = sentences and sentences[0].lower().strip(" .") == what.lower()
            if already_said and not where:
                # "Utetemperatur. Mäter utetemperatur (BT1)." adds nothing but
                # the designation, so just append that to the lead instead.
                sentences[0] = f"{sentences[0]} ({measured})"
            else:
                lead = "Mäter" if sv else "Measures"
                sentences.append(f"{lead} {what}{where} ({measured})")
        else:
            sentences.append(f"{what}{where} ({measured})")
    else:
        unknown = [c for c in codes if c not in MODULES]
        if unknown:
            code = unknown[0]
            kind = COMPONENT_TYPES.get(code[:2])
            kind_text = _pick(kind, language) if kind else ("komponent" if sv else "component")
            where = _scope_phrase(scope, language)
            tail = (
                " - NIBE dokumenterar inte närmare vad den mäter"
                if sv
                else " - NIBE does not document further what it measures"
            )
            sentences.append(f"{kind_text} {code}{where}{tail}")
        elif scope:
            where = ", ".join(_pick(MODULES[c], language) for c in scope)
            sentences.append(f"Avser {where}" if sv else f"Relates to {where}")

    # 3. Explain the underlying concept, when the title touches one.
    for pattern, text in CONCEPTS:
        if pattern.search(title):
            sentences.append(_pick(text, language))
            break

    # 4. How the value behaves.
    if meta.get("write"):
        lo, hi = meta.get("min"), meta.get("max")
        unit = meta.get("unit") or ""
        factor = meta.get("factor", 1) or 1
        if _is_full_type_range(meta.get("size", "s16"), lo, hi):
            # NIBE fills unbounded settings with the datatype's limits; quoting
            # "between -2147483648 and 2147483647" would be noise.
            lo = hi = None
        if lo is not None and hi is not None:
            lo_s = _fmt(lo / factor if factor != 1 else lo)
            hi_s = _fmt(hi / factor if factor != 1 else hi)
            sentences.append(
                f"Inställbar mellan {lo_s} och {hi_s} {unit}".rstrip()
                 if sv else
                 f"Writable, between {lo_s} and {hi_s} {unit}".rstrip()
            )
        else:
            sentences.append("Inställbar" if sv else "Writable")

    if meta.get("mappings"):
        pairs = ", ".join(
            f"{k} = {v}" for k, v in sorted(meta["mappings"].items(), key=_numeric)
        )
        sentences.append(f"Värden: {pairs}" if sv else f"Values: {pairs}")

    return _join(sentences)


#: Datatype limits NIBE writes into min/max when a setting is effectively unbounded.
_TYPE_RANGES: dict[str, tuple[float, float]] = {
    "u8": (0, 0xFF),
    "s8": (-0x80, 0x7F),
    "u16": (0, 0xFFFF),
    "s16": (-0x8000, 0x7FFF),
    "u32": (0, 0xFFFFFFFF),
    "s32": (-0x80000000, 0x7FFFFFFF),
}


def _is_full_type_range(size: str, lo, hi) -> bool:
    limits = _TYPE_RANGES.get(size)
    if limits is None or lo is None or hi is None:
        return False
    return lo <= limits[0] and hi >= limits[1]


def _numeric(item: tuple[str, str]) -> tuple[int, str]:
    try:
        return (int(item[0]), "")
    except (TypeError, ValueError):
        return (0, str(item[0]))


def _fmt(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def friendly_name(title: str, language: str = "sv") -> str:
    """A readable entity name for a register."""
    sv = language.startswith("sv")
    prose = _prose(title)
    if prose:
        translated = _swedish_phrase(prose) if sv else None
        name = translated or prose
        return name[0].upper() + name[1:]

    # The title was nothing but designations, e.g. "(EB100-EP15-BT28)".
    codes = _CODE_RE.findall(title)
    known = next((c for c in codes if c in COMPONENTS), None)
    if known:
        name = _pick(COMPONENTS[known], language)
        return f"{name[0].upper()}{name[1:]} ({known})"
    unknown = [c for c in codes if c not in MODULES]
    if unknown:
        code = unknown[0]
        kind = COMPONENT_TYPES.get(code[:2])
        if kind:
            name = _pick(kind, language)
            return f"{name[0].upper()}{name[1:]} {code}"
        return code
    return title.strip("() ").strip() or "Register"
