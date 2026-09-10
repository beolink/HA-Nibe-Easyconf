"""Short entity names for the registers people actually see.

NIBE's own titles run to 78 characters ("Energy log - Used energy by additional
heater for hot water over the past hour"), and Home Assistant's device page
lays entities out in columns that cut a name off at roughly 25. Of the ~100
registers enabled by default, a quarter were over 30 characters and got
truncated into uselessness.

So the default set gets hand-written short names, kept to 24 characters. The
full NIBE title and the generated explanation are not lost: they stay on every
entity as the `nibe_title` and `description` attributes, one click away in the
entity's details.

Keyed on NIBE's title rather than the register number, because the same title
recurs across models at different addresses. Registers not listed here keep the
name `descriptions.friendly_name` builds - they are disabled by default, so the
people who meet them went looking and are better served by NIBE's full wording.
"""

from __future__ import annotations

#: NIBE title -> (svenska, English). Every entry is at most 24 characters.
SHORT_NAMES: dict[str, tuple[str, str]] = {
    # --- temperatures ---------------------------------------------------
    "Current outdoor temperature (BT1)": ("Utetemperatur", "Outdoor temperature"),
    "Average temperature (BT1)": ("Utetemperatur, medel", "Outdoor average"),
    "Supply line (BT2)": ("Framledning", "Supply line"),
    "Return line (BT3)": ("Returledning", "Return line"),
    "Hot water charging (BT6)": ("Varmvatten, laddning", "Hot water charging"),
    "Condenser sensor supply line (BT12)": ("Kondensor ut", "Condenser out"),
    "Condenser (BT12)": ("Kondensor ut", "Condenser out"),
    "Discharge (BT14)": ("Hetgas", "Hot gas"),
    "Liquid line (BT15)": ("Vätskeledning", "Liquid line"),
    "Suction gas (BT17)": ("Suggas", "Suction gas"),
    "Room average temp. clim. system 1 (BT50)": ("Rumstemperatur, medel", "Room average"),
    "Temperature: BT50": ("Rumstemperatur", "Room temperature"),
    "Supply temperature (BT64)": ("Kyla, framledning", "Cooling supply"),
    "Calculated supply climate system 1": ("Beräknad framledning", "Calculated supply"),
    # Per-module duplicates of the sensors above, as the compressor module
    # reports them. Named for what distinguishes them from the main sensor.
    "Return line (EB100-BT3)": ("Retur, kompressormodul", "Return, compressor"),
    "Brine in (EB100-BT10)": ("Köldbärare in", "Brine in"),
    "Brine out (EB100-BT11)": ("Köldbärare ut", "Brine out"),
    "Condenser (EB100-BT2)": ("Kondensor, modul", "Condenser, module"),
    "Discharge (EB100-BT14)": ("Hetgas, modul", "Hot gas, module"),
    "Liquid line (EB100-BT15)": ("Vätskeledning, modul", "Liquid line, module"),
    "Suction gas (EB100-BT17)": ("Suggas, modul", "Suction gas, module"),
    "Controlling hot water sensor (EB100-BT6)": ("Varmvatten, styrande", "Hot water, controlling"),
    "Supply temperature sensor (EB100-BT2)": ("Framledning, modul", "Supply, module"),
    "Evaporator 2 (EB100-EP15-BT16)": ("Förångare 2", "Evaporator 2"),
    "(EB100-EP15-BT16)": ("Förångare", "Evaporator"),
    # --- flow, pressure, current ---------------------------------------
    "Flow sensor (BF1)": ("Flöde", "Flow"),
    "Current (BE1)": ("Ström fas 1", "Current L1"),
    "Current (BE2)": ("Ström fas 2", "Current L2"),
    "Current (BE3)": ("Ström fas 3", "Current L3"),
    "Pressure sensor, condenser (EB100-EP14-BP4)": ("Högtryck", "High pressure"),
    "Pressure sensor, condenser (EB100-EP15-BP4)": ("Högtryck, krets 2", "High pressure 2"),
    "Low pressure (EB100-EP14-BP8)": ("Lågtryck", "Low pressure"),
    "Low pressure (EB100-EP15-BP8)": ("Lågtryck, krets 2", "Low pressure 2"),
    "BP4, unprocessed (EB100-EP14)": ("Högtryck, rå", "High pressure, raw"),
    "BP4, unprocessed (EB100-EP15)": ("Högtryck rå, krets 2", "High press. raw 2"),
    # --- compressor -----------------------------------------------------
    "Compressor frequency": ("Kompressorfrekvens", "Compressor frequency"),
    "Compressor frequency, current": ("Kompressorfrekv., nu", "Compressor freq. now"),
    "Requested compressor frequency": ("Begärd frekvens", "Requested frequency"),
    "Requested compressor frequency (EP15)": ("Begärd frekv., krets 2", "Requested freq. 2"),
    "Heat pump 1 requested compressor frequency": ("Begärd frekv., VP 1", "Requested freq. HP1"),
    "Max. compressor frequency, heating": ("Max frekvens, värme", "Max freq., heating"),
    "Compressor power input": ("Kompressoreffekt", "Compressor power"),
    "Compressor power input, average": ("Kompressoreffekt, medel", "Compressor power avg"),
    "Compressor status": ("Kompressorstatus", "Compressor status"),
    "Compressor status (EB100)": ("Kompressorstatus, modul", "Compressor status, mod."),
    "Compressor status (EB100-EP14)": ("Kompressor, krets 1", "Compressor, circuit 1"),
    "Compressor status (EB100-EP15)": ("Kompressor, krets 2", "Compressor, circuit 2"),
    "Operating mode compressor": ("Driftläge kompressor", "Compressor mode"),
    "Total run time compressor": ("Drifttid kompressor", "Compressor run time"),
    "Total run time compressor hot water": ("Drifttid, varmvatten", "Run time, hot water"),
    "Total run time compressor cooling": ("Drifttid, kyla", "Run time, cooling"),
    "Defrosting (EB100-EP14)": ("Avfrostning", "Defrosting"),
    "Defrosting (EB100-EP15)": ("Avfrostning, krets 2", "Defrosting 2"),
    "Fan speed (EB100-EP14)": ("Fläkt, krets 1", "Fan, circuit 1"),
    "Fan speed (EB100-EP15)": ("Fläkt, krets 2", "Fan, circuit 2"),
    "fan speed (EB100-EP14)": ("Fläkt, krets 1", "Fan, circuit 1"),
    "fan speed (EB100-EP15)": ("Fläkt, krets 2", "Fan, circuit 2"),
    # --- energy ---------------------------------------------------------
    "Energy log - Produced energy for heating over the past hour": (
        "Producerad värme, 1 h", "Heat produced, 1 h"),
    "Energy log - Produced energy for hot water over the past hour": (
        "Producerat VV, 1 h", "Hot water made, 1 h"),
    "Energy log - Produced energy for cooling over the past hour": (
        "Producerad kyla, 1 h", "Cooling produced, 1 h"),
    "Energy log - Used energy for heating over the past hour": (
        "Förbrukat, värme, 1 h", "Used, heating, 1 h"),
    "Energy log - Used energy for hot water over the past hour": (
        "Förbrukat, VV, 1 h", "Used, hot water, 1 h"),
    "Energy log - Used energy for cooling over the past hour": (
        "Förbrukat, kyla, 1 h", "Used, cooling, 1 h"),
    "Energy log - Used energy by additional heater for heating over the past hour": (
        "Elpatron, värme, 1 h", "Immersion, heat, 1 h"),
    "Energy log - Used energy by additional heater for hot water over the past hour": (
        "Elpatron, VV, 1 h", "Immersion, HW, 1 h"),
    "Energy log - Current power consumption": ("Effekt nu", "Power now"),
    "Energy log - Current power consumption, components": (
        "Effekt, komponenter", "Power, components"),
    "Instantaneous used power": ("Momentan effekt", "Instant power"),
    "Current power": ("Aktuell effekt", "Current power"),
    "Current power (EME 20)": ("Aktuell effekt", "Current power"),
    "Total energy": ("Total energi", "Total energy"),
    "Total energy (EME 20)": ("Total energi", "Total energy"),
    "Hot water, including int. add. heat": ("Varmvatten inkl. el", "Hot water incl. elec."),
    "Heating, including int. add. heat": ("Värme inkl. el", "Heating incl. elec."),
    # --- additional heat ------------------------------------------------
    "Power internal additional heat": ("Elpatron, effekt", "Immersion power"),
    "Operating mode internal add. heat": ("Elpatron, driftläge", "Immersion mode"),
    "Total run time additional heat": ("Elpatron, drifttid", "Immersion run time"),
    "Max. internal additional heat": ("Elpatron, max", "Immersion max"),
    "Permit additional heat, heating": ("Tillåt elpatron", "Allow immersion"),
    "Operating. mode shunt controlled additional heat": ("Shuntad tillsats", "Shunted add. heat"),
    # --- pumps and valves -----------------------------------------------
    "Heating medium pump speed (GP1)": ("VB-pump, varvtal", "HM pump speed"),
    "Operating mode heating medium pump": ("VB-pump, driftläge", "HM pump mode"),
    "Manual heating medium pump speed": ("VB-pump, manuellt", "HM pump, manual"),
    "Minimum permitted speed (EB100 GP1)": ("VB-pump, min varvtal", "HM pump, min speed"),
    "Diverter valve hot water (QN10)": ("Växelventil VV", "Diverter valve HW"),
    "Reversing valve hot water (QN10)": ("Växelventil VV", "Diverter valve HW"),
    # --- control and modes ---------------------------------------------
    "Degree minutes": ("Gradminuter", "Degree minutes"),
    "Priority": ("Prioritering", "Priority"),
    "Heating curve climate system 1": ("Värmekurva", "Heating curve"),
    "Heating offset climate system 1": ("Kurvförskjutning", "Curve offset"),
    "Hot water mode": ("Varmvattenläge", "Hot water mode"),
    "Hot water demand mode": ("Varmvattenläge", "Hot water mode"),
    "Current hot water mode controlled by": ("VV-läge styrs av", "HW mode set by"),
    "Temp. lux forces start of hot water demand": ("Tillfällig lyx", "Temporary lux"),
    "Operating mode": ("Driftläge", "Operating mode"),
    "Operating mode PV panels": ("Solceller, driftläge", "PV mode"),
    "BT12 offset": ("Justering BT12", "BT12 offset"),
    # --- alarms ---------------------------------------------------------
    "Alarm number": ("Larmkod", "Alarm code"),
    "Alarm number (EB100-EP14)": ("Larmkod, krets 1", "Alarm code, circuit 1"),
    "Alarm number (EB100-EP15)": ("Larmkod, krets 2", "Alarm code, circuit 2"),
    "Class 1 alarm": ("Larm klass 1", "Class 1 alarm"),
    "Reset alarm": ("Återställ larm", "Reset alarm"),
    "Alarm action, lower room temperature": ("Vid larm: sänk rum", "On alarm: lower room"),
    "Alarm action lower HW temperature": ("Vid larm: sänk VV", "On alarm: lower HW"),
}

MAX_LENGTH = 24


def short_name(title: str, language: str = "sv") -> str | None:
    """The curated short name for a title, or None if there is none."""
    names = SHORT_NAMES.get(title)
    if names is None:
        return None
    return names[0] if language.startswith("sv") else names[1]


def assign_names(
    registers: dict[int, dict],
    present: set[int],
    language: str,
    fallback,
) -> dict[int, str]:
    """A distinct name for every present register.

    NIBE reuses titles: on the development unit 308 of the 919 registers shared
    57 names between them, 21 of them titled just "Permit". Home Assistant would
    show those as identical rows, so a clash is resolved here, preferring the
    most meaningful distinction available:

    1. a component designation only some of the clashing titles carry
       (EP14 vs EP15 is the refrigerant circuit, and says so);
    2. the register being a setting rather than a reading, when exactly one of
       them is writable;
    3. the register number, which is always true when nothing else is known.
    """
    from collections import defaultdict
    import re

    code_re = re.compile(r"\b([A-Z]{2}\d{1,3})\b")
    setting = "inställning" if language.startswith("sv") else "setting"

    names: dict[int, str] = {}
    for register in present:
        meta = registers.get(register)
        if meta is None:
            continue
        title = meta.get("title", str(register))
        names[register] = short_name(title, language) or fallback(title, language)

    groups: dict[str, list[int]] = defaultdict(list)
    for register, name in names.items():
        groups[name].append(register)

    for name, clashing in groups.items():
        if len(clashing) < 2:
            continue
        codes = {
            r: set(code_re.findall(registers[r].get("title", ""))) for r in clashing
        }
        shared = set.intersection(*codes.values()) if codes else set()
        writable = [r for r in clashing if registers[r].get("write")]
        # With exactly one setting among them, marking that one is enough: the
        # readings keep the plain name, and step 3 only numbers what is still
        # ambiguous after that.
        one_setting = len(writable) == 1
        for register in clashing:
            distinct = sorted(codes[register] - shared)
            if distinct:
                names[register] = f"{name} ({distinct[-1]})"
            elif one_setting and register in writable:
                names[register] = f"{name}, {setting}"
            elif not one_setting:
                names[register] = f"{name} ({register})"

    # A designation can itself be shared by several clashing registers, and
    # several readings can remain beside one setting, so any name still
    # duplicated falls back to the register number.
    seen: dict[str, list[int]] = defaultdict(list)
    for register, name in names.items():
        seen[name].append(register)
    for name, clashing in seen.items():
        if len(clashing) > 1:
            for register in clashing:
                names[register] = f"{name} ({register})"
    return names
