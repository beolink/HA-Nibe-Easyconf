"""The written explanations, and that they reach the right registers.

The titles below are the ones the two pumps this was built against actually
report: the S1155 over Modbus TCP and the F1255-16 CU through the gateway. The
two series word the same register differently, which is the whole reason the
explanations are matched by pattern rather than by register number.
"""

from __future__ import annotations

import importlib

from .conftest import PACKAGE

descriptions = importlib.import_module(f"{PACKAGE}.descriptions")
explanations = importlib.import_module(f"{PACKAGE}.explanations")

#: (S-series title, F-series title) for the values a person actually uses.
SAME_THING = [
    ("Heating curve, climate system 1", "Heat Curve S1"),
    ("Heating offset climate system 1", "Heat Offset S1"),
    ("Degree minutes", "Degree Minutes (16 bit)"),
    ("Hot water demand mode", "Hot water comfort mode"),
    ("Permit additional heat (heating)", "Allow add. heat"),
    ("Operating mode", "Operational mode"),
    ("Reset alarm", "Alarm Reset"),
    ("Max internal additional heat", "Max int add. power"),
    ("Current outdoor temperature (BT1)", "BT1 Outdoor Temperature"),
    ("Supply line (BT2)", "BT2 Supply temp S1"),
    ("Return line (BT3)", "EB100-EP14-BT3 Return temp"),
    ("Hot water charging (BT6)", "BT6 HW Load"),
    ("Brine in (BT10)", "EB100-EP14-BT10 Brine In Temp"),
    ("Brine out (BT11)", "EB100-EP14-BT11 Brine Out Temp"),
    ("Discharge (BT14)", "EB100-EP14-BT14 Hot Gas Temp"),
    ("Compressor frequency", "Compressor Frequency, Actual"),
    ("Tot. production", "Heat Meter - Heat Cpr and Add EP14"),
]


def test_both_series_get_the_same_explanation():
    for s_series, f_series in SAME_THING:
        first = explanations.explain(s_series)
        second = explanations.explain(f_series)
        assert first, f"ingen förklaring för {s_series!r}"
        assert first == second, f"{s_series!r} och {f_series!r} förklaras olika"


def test_an_explanation_says_what_changing_it_does():
    curve = explanations.explain("Heating curve")
    assert "kurva" in curve.lower()
    # A layperson is told what to do with it, not just what it is.
    assert "vänta ett dygn" in curve
    assert "one step at a time" in explanations.explain("Heating curve", "en")


def test_the_explanation_replaces_the_built_text_but_keeps_the_register_facts():
    text = descriptions.describe(
        "Heating curve", 47007, {"write": True, "min": 0, "max": 15, "size": "u8"}
    )
    assert text.startswith("Kurvan bestämmer")
    # What the register itself says is still there.
    assert "Inställbar mellan 0 och 15" in text


def test_a_register_nobody_wrote_about_keeps_its_built_text():
    text = descriptions.describe("Defrosting time (41078)", 41078, {"size": "u8"})
    assert explanations.explain("Defrosting time (41078)") is None
    assert "41078" in text or "Defrosting" in text


def test_a_setting_is_not_given_a_status_explanation():
    """"Defrosting (EB100-EP14)" is whether it is defrosting now; "Defrosting
    time (FLM 2)" is a setting in hours, and neither text fits the other."""
    assert "avfrostar just nu" in explanations.explain("Defrosting (EB100-EP14)")
    setting = explanations.explain("Defrosting time (FLM 2)")
    assert "avfrostar just nu" not in setting
    assert "Kortaste tiden mellan två avfrostningar" in setting


def test_the_pumps_own_readings_are_not_confused_with_its_pumps():
    """"Operating mode" is the pump's mode; "operating mode brine medium pump"
    is a circulation pump, and they must not get each other's text."""
    mode = explanations.explain("Operating mode")
    brine = explanations.explain("Operating mode brine medium pump")
    speed = explanations.explain("Supply Pump Speed EP14")
    assert "Auto" in mode
    assert "köldbärarpumpen" in brine
    assert "värmebärarpumpen" in speed


def test_this_integrations_own_entities_are_explained():
    for key in ("heating_mode", "hot_water_boost", "cop_day", "cop_year", "manufactured"):
        assert explanations.explain_own(key), key
        assert explanations.explain_own(key, "en")
    assert "blockerad" in explanations.explain_own("heating_mode")
    assert "kilowattimme" in explanations.explain_own("cop_day")


def test_a_language_nobody_wrote_gets_the_english_text():
    german = explanations.explain("Heating curve", "de")
    assert german == explanations.explain("Heating curve", "en")


def test_an_accessory_nobody_here_owns_is_explained_all_the_same():
    """A user's pool, ERS module or eighth climate system should arrive with
    its values explained, although no pump in this project has one."""
    for title in (
        "Pool 1 start temperature",
        "Blocking actions (ERS 3)",
        "Room sensor factor climate system 8",
        "Zone 3 affected by ECS2",
        "Energy price 04:00 - 05:00",
        "Floor drying period 2",
        "Return time fan 4",
        "Cooling (SG Ready)",
        "Supp. air curve SAM, outd. temp. (T3)",
        "Superheat EEV (EB101)",
    ):
        text = explanations.explain(title)
        assert text and len(text) > 60, title


def test_both_series_spellings_of_the_same_setting_agree():
    """The S-series writes "FLM 1 defrost", the F-series "Defrosting time
    (FLM 1)"; both should say something about defrosting the module."""
    for swedish_title, word in (
        ("FLM 1 defrost", "frånluft"),
        ("Defrosting time (FLM 1)", "avfrost"),
        ("FLM 2 speed 3", "fläkthastighet"),
        ("Exhaust air fan speed 3", "hastighet"),
    ):
        text = explanations.explain(swedish_title)
        assert text and word in text.lower(), swedish_title


def test_what_cannot_be_explained_is_not_invented():
    """A service value from the pump's own electronics says it is one, rather
    than being given a purpose nobody verified."""
    text = explanations.explain("AA23-BE5 Voltage1 4")
    assert text and "servicevärde" in text.lower()
    assert "felsökning" in text.lower()
