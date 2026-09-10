"""Turning NIBE's service-manual shorthand into something readable."""

import importlib

from .conftest import PACKAGE

descriptions = importlib.import_module(f"{PACKAGE}.descriptions")


def test_a_title_that_is_only_a_designation_still_gets_a_name():
    """Register 31624 on a real pump is titled exactly "(EB100-EP15-BT28)"."""
    title = "(EB100-EP15-BT28)"
    name = descriptions.friendly_name(title)
    assert "BT28" in name
    assert "temperatur" in name.lower()

    text = descriptions.describe(title, 31624, {"size": "s16", "factor": 10})
    assert "kompressormodulen" in text
    assert text.endswith(".")


def test_unknown_designations_are_not_guessed_at():
    """A code we cannot pin down gets a structural description, not an invention."""
    text = descriptions.describe("(EB100-BT99)", 31000, {"size": "s16"})
    assert "BT99" in text
    assert "temperaturgivare" in text.lower()
    assert "dokumenterar inte" in text


def test_known_designation_is_decoded():
    text = descriptions.describe("Current outdoor temperature (BT1)", 30002, {"factor": 10})
    assert "BT1" in text
    assert "utetemperatur" in text.lower()


def test_prose_is_never_half_translated():
    """Substring translation produced hybrids like "Kyla start at over temp",
    which read worse than NIBE's English. Only whole phrases are translated."""
    assert descriptions.friendly_name("Cooling start at over temp.") == "Cooling start at over temp."
    assert descriptions.friendly_name("Current outdoor temperature (BT1)") == "Utetemperatur"


def test_writable_range_is_reported_in_engineering_units():
    text = descriptions.describe(
        "Auto mode, additional heat stop temperature",
        40186,
        {"size": "s16", "factor": 10, "unit": "°C", "min": -250.0, "max": 400.0, "write": True},
    )
    assert "-25" in text and "40" in text


def test_datatype_limits_are_not_presented_as_a_setting_range():
    """NIBE fills unbounded settings with the datatype's limits."""
    text = descriptions.describe(
        "Energy price 18:00 - 19:00",
        46051,
        {
            "size": "s32", "factor": 1, "write": True,
            "min": -2147483648.0, "max": 2147483647.0,
        },
    )
    assert "2147483647" not in text
    assert "Inställbar" in text


def test_value_mappings_are_spelled_out():
    text = descriptions.describe(
        "Hot water mode",
        40057,
        {
            "size": "s8", "factor": 1, "write": True, "min": 0, "max": 4,
            "mappings": {"0": "Small", "1": "Medium", "2": "Large", "4": "Smart Control"},
        },
    )
    assert "0 = Small" in text and "4 = Smart Control" in text


def test_concepts_get_an_explanation():
    text = descriptions.describe("Degree minutes", 40012, {"size": "s16", "factor": 10})
    assert "gradminut" in text.lower()
    assert "kompressorn" in text


def test_english_output_is_available():
    text = descriptions.describe(
        "Current outdoor temperature (BT1)", 30002, {"factor": 10}, language="en"
    )
    assert "outdoor temperature" in text.lower()
    assert "utetemperatur" not in text.lower()
