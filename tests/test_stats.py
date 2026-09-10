"""What the optional daily report may contain.

The point of these is not that the numbers are right, it is that nothing but
the agreed fields can ever leave the house. stats_extra.py is deliberately free
of Home Assistant imports so this can be checked without installing HA.
"""

from __future__ import annotations

import importlib

from .conftest import PACKAGE

stats_extra = importlib.import_module(f"{PACKAGE}.stats_extra")


def _extra(**kwargs):
    args = {
        "traits": {"ground_source", "hot_water"},
        "registers_present": 919,
        "registers_reporting": 882,
        "registers_absent": 303,
        "entities_enabled": 96,
        "block_reads": 58,
        "scan_interval_s": 60,
        "read_failures": 0,
    }
    args.update(kwargs)
    return stats_extra.build_extra("s1155", **args)


# ------------------------------------------------------------------ models


def test_known_models_become_slugs():
    assert stats_extra.model_slug("s1155") == "s1155"
    assert stats_extra.model_slug("S1255") == "s1255"
    assert stats_extra.model_slug("smos40") == "smos40"


def test_unknown_model_never_leaks_its_name():
    # "other" is a real choice in the config flow, and the name field is free
    # text the user typed. Neither may reach the database as itself.
    assert stats_extra.model_slug("other") == "other"
    assert stats_extra.model_slug("Villagatan 4") == "other"
    assert stats_extra.model_slug("S1155; DROP TABLE") == "other"
    assert stats_extra.model_slug(None) == "unknown"
    assert stats_extra.model_slug("") == "unknown"


# ----------------------------------------------------------------- payload


def test_report_holds_only_the_agreed_keys():
    extra = _extra()
    assert set(extra) == {"models", "features", "errors"}
    assert set(extra["features"]) == {
        "ground_source", "exhaust_air", "hot_water", "cooling",
        "registers_present", "registers_reporting", "registers_absent",
        "entities_enabled", "block_reads", "scan_interval_s",
    }


def test_report_carries_no_free_text():
    extra = _extra()
    assert extra["models"] == ["s1155"]
    for value in extra["features"].values():
        assert isinstance(value, (bool, int))


def test_which_registers_were_found_is_never_sent():
    """A register number is harmless alone; the set of them fingerprints the
    installation. Only counts go out."""
    extra = _extra()
    assert extra["features"]["registers_present"] == 919
    assert "registers" not in extra
    assert "30002" not in repr(extra)


def test_traits_are_reported_as_a_closed_set_of_flags():
    extra = _extra(traits={"ground_source", "hot_water"})
    assert extra["features"]["ground_source"] is True
    assert extra["features"]["hot_water"] is True
    assert extra["features"]["exhaust_air"] is False
    assert extra["features"]["cooling"] is False


def test_an_unexpected_trait_cannot_add_a_field():
    extra = _extra(traits={"ground_source", "occupant_name"})
    assert "occupant_name" not in extra["features"]


def test_negative_counts_can_not_appear():
    extra = _extra(registers_present=-5, read_failures=-7, entities_enabled=-1)
    assert extra["features"]["registers_present"] == 0
    assert extra["features"]["entities_enabled"] == 0
    assert extra["errors"] == 0


def test_payload_omits_what_is_not_known():
    extra = stats_extra.build_extra("s1155")
    assert "metrics" not in extra
    assert "firmware" not in extra
    assert extra["models"] == ["s1155"]


# ---------------------------------------------------------------- firmware


def test_firmware_is_a_plain_number():
    assert stats_extra.firmware_value(1036) == 1036
    assert stats_extra.firmware_value("1036") == 1036


def test_firmware_rejects_anything_else():
    # The sentinel for an absent register, and any string from the wire.
    assert stats_extra.firmware_value(0) is None
    assert stats_extra.firmware_value(999999) is None
    assert stats_extra.firmware_value("v2.1") is None
    assert stats_extra.firmware_value(None) is None


def test_firmware_reaches_the_report_when_known():
    # One board, so a single string under "firmware" rather than CTC's
    # per-board "firmwares" object.
    extra = _extra(firmware=1036)
    assert extra["firmware"] == "1036"
    assert "firmwares" not in extra


# ----------------------------------------------------------- error counter


def test_error_counter_reports_the_change_since_last_time():
    counter = stats_extra.ErrorCounter()
    assert counter.delta(0) == 0
    assert counter.delta(3) == 3
    assert counter.delta(3) == 0
    assert counter.delta(10) == 7


def test_error_counter_survives_a_reload():
    # A reload starts the coordinator's counter over at zero. Without this the
    # report would carry a negative number of failures.
    counter = stats_extra.ErrorCounter()
    counter.delta(12)
    assert counter.delta(2) == 2


# --------------------------------------------------------------------- COP


def test_cop_figures_reach_the_report():
    extra = _extra(cop_day=3.9, cop_year=3.98, cop_lifetime=4.18)
    assert extra["metrics"] == {"cop_day": 3.9, "cop_year": 3.98, "cop_lifetime": 4.18}


def test_an_impossible_cop_is_not_sent():
    """A counter reset, or a day with almost no consumption, divides to nonsense."""
    extra = _extra(cop_day=0.1, cop_year=42.0, cop_lifetime=4.18)
    assert extra["metrics"] == {"cop_lifetime": 4.18}


def test_a_missing_cop_is_left_out():
    extra = _extra(cop_lifetime=4.18)
    assert set(extra["metrics"]) == {"cop_lifetime"}
