"""The F-series: what the pump says it is, and what is shown by default.

Product messages and readings are the F1255-16 CU this was developed against,
read through a Waveshare ESP32-S3-RS485-CAN running esphome-nibe.
"""

from __future__ import annotations

import importlib

from nibe.heatpump import Model
import pytest

from .conftest import PACKAGE

fseries = importlib.import_module(f"{PACKAGE}.fseries")
names = importlib.import_module(f"{PACKAGE}.names")
registry = importlib.import_module(f"{PACKAGE}.registry")
stats_extra = importlib.import_module(f"{PACKAGE}.stats_extra")

#: The map as the integration builds it, which is the library's with the
#: registers NIBE leaves out of its published list added (see fseries.py).
F1255_MAP = registry.model_map("f1155_f1255")


# ------------------------------------------------------------ the product message


def test_the_development_unit_names_itself():
    product = fseries.identify_product("F1255-16 CU")
    assert product.model is Model.F1255
    assert (product.name, product.size, product.variant) == ("F1255", "16", "CU")
    assert product.key == "f1255"
    assert product.label == "NIBE F1255-16 CU"


@pytest.mark.parametrize(
    ("text", "model", "size", "variant"),
    [
        ("F1155-6", Model.F1155, "6", None),
        ("F1255-12 R PC EM", Model.F1255, "12", "R PC EM"),
        ("F750", Model.F750, None, None),
        ("SMO 40", Model.SMO40, None, None),
        ("VVM 320", Model.VVM320, None, None),
        ("  f1345-40 ", Model.F1345, "40", None),
    ],
)
def test_nibes_spellings_are_all_understood(text, model, size, variant):
    product = fseries.identify_product(text)
    assert product is not None, text
    assert (product.model, product.size, product.variant) == (model, size, variant)


@pytest.mark.parametrize("text", ["S1155-16", "SMO S40", "VVM S320", "", None, "EcoZenith i255"])
def test_anything_but_the_f_series_is_refused(text):
    """The S-series speaks Modbus TCP and has its own path through setup."""
    assert fseries.identify_product(text) is None


def test_every_f_series_model_has_a_label_and_a_report_slug():
    assert fseries.MODEL_LABELS["f1255"] == "NIBE F1255"
    assert fseries.MODEL_LABELS["smo40"] == "NIBE SMO 40"
    for key in fseries.MODEL_LABELS:
        assert stats_extra.model_slug(key) == key


# ------------------------------------------------------------ the gateway's name


@pytest.mark.parametrize(
    "hostname",
    [
        "nibe-06505916100001-gw",
        "nibe-06505916100001-gw.local.",
        "nibe-06505916100001-gw._esphomelib._tcp.local.",
        "NIBE-GW",
    ],
)
def test_the_gateway_is_recognised_by_its_name(hostname):
    assert fseries.is_gateway_hostname(hostname)


@pytest.mark.parametrize(
    "hostname", ["nibe-06544322034003", "NIBE-06544322034003", "nibe-gwx", "", None]
)
def test_a_pump_is_not_mistaken_for_a_gateway(hostname):
    """An S-series pump calls itself NIBE-<serial>; that must stay on the Modbus path."""
    assert not fseries.is_gateway_hostname(hostname)


# ------------------------------------------------------------ what is on by default


def test_every_default_title_exists_in_the_f1255_map():
    titles = {meta["title"] for meta in F1255_MAP.values()}
    missing = fseries.DEFAULT_TITLES - titles
    assert not missing, sorted(missing)


def test_every_default_register_gets_a_short_name():
    for title in fseries.DEFAULT_TITLES:
        assert names.short_name(title) is not None, title
        assert names.short_name(title, "en") is not None, title


def test_setup_reads_a_minute_and_a_halfs_worth_of_registers():
    """A register costs about a second through the gateway, and the scan runs
    while somebody waits at the dialog. The usual values are half of it; the
    other half is every flag that says whether an accessory is registered,
    which is read once and answers what the pump has."""
    registers = fseries.default_registers(F1255_MAP)
    assert 30 <= len(registers) <= 90
    assert registers == sorted(registers)
    assert 40004 in registers and 43005 in registers
    # The flags, whatever the pump answers: a pool it does not have is an
    # answer too.
    for flag in (48088, 48071, 47302, 47365, 48828, 47352):
        assert flag in registers


def test_a_register_without_a_reading_stays_off():
    """No room sensor on the development unit: BT50 reads NIBE's "no value"."""
    room = F1255_MAP[40033]
    assert fseries.is_default(room, reporting=True)
    assert not fseries.is_default(room, reporting=False)


def test_the_long_tail_stays_off_even_when_reporting():
    assert not fseries.is_default(F1255_MAP[49291], reporting=True)  # ground water pump speed


def test_dates_are_never_enabled():
    assert not fseries.is_default({**F1255_MAP[48044], "title": "Alarm"}, reporting=True)


# ------------------------------------------------------------ traits


def test_the_development_unit_is_a_ground_source_pump_with_hot_water():
    product = fseries.identify_product("F1255-16 CU")
    reporting = {"BT6 HW Load", "BT7 HW Top", "BT1 Outdoor Temperature"}
    assert fseries.traits_for(product, reporting) == {"ground_source", "hot_water"}


def test_an_exhaust_air_reading_does_not_make_a_ground_source_pump_exhaust_air():
    """The F1255-16 answered BT20 exhaust air with 23.3 °C and has no such module."""
    product = fseries.identify_product("F1255-16 CU")
    assert "exhaust_air" not in fseries.traits_for(product, {"BT20 Exhaust air temp. 1"})


def test_cooling_shows_up_only_when_its_sensor_reports():
    product = fseries.identify_product("F1155-12")
    assert "cooling" in fseries.traits_for(product, {"EQ1-BT64 Cool Supply Temp"})
    assert "cooling" not in fseries.traits_for(product, set())


def test_traits_stay_within_the_reports_closed_list():
    product = fseries.identify_product("F750")
    traits = fseries.traits_for(product, fseries.HOT_WATER_TITLES | fseries.COOLING_TITLES)
    assert traits <= set(stats_extra.TRAIT_SLUGS)


# ------------------------------------------------------------ words


def test_value_tables_read_in_swedish():
    labels = fseries.labels_for(F1255_MAP[43427], "sv")  # Compressor State EP14
    assert labels == {"20": "Stoppad", "40": "Startar", "60": "I drift", "100": "Stannar"}


def test_value_tables_keep_nibes_english_otherwise():
    assert fseries.labels_for(F1255_MAP[47041], "en") == {
        "0": "Economy", "1": "Normal", "2": "Luxury", "4": "Smart Control",
    }


def test_designations_in_labels_survive_capitalisation():
    labels = fseries.labels_for(F1255_MAP[47340], "en")  # Cooling with room sensor
    assert "BT50" in labels.values() and "RMU-BT50" in labels.values()


def test_a_register_without_a_table_has_no_labels():
    assert fseries.labels_for(F1255_MAP[40004], "sv") is None


def test_the_logset_switch_reads_as_what_it_does():
    assert fseries.labels_for(F1255_MAP[48889], "sv") == {
        "0": "Använd LOG.SET", "1": "Ignorera LOG.SET",
    }


official = importlib.import_module(f"{PACKAGE}.official")


def test_alarm_codes_are_not_read_from_the_s_series_list():
    """163 is a missing phase on the S-series and a hot condenser inlet here."""
    assert fseries.is_alarm_register(F1255_MAP[45001])
    assert fseries.alarm_text(163, "sv") == "Hög kondensor in"
    assert fseries.alarm_text(163, "en") == "High condensor in"
    assert fseries.alarm_text(163, "sv") != official.alarm_text(163, "sv")


def test_no_alarm_and_no_value():
    assert fseries.alarm_text(0, "sv") == "Inget larm"
    assert fseries.alarm_text(0, "en") == "No alarm"
    assert fseries.alarm_text(None) is None


def test_the_alarms_an_f1255_owner_meets_read_as_words():
    assert fseries.alarm_text(1, "sv") == "Givarfel BT1"
    assert fseries.alarm_text(50, "sv") == "Högtryckslarm"
    assert fseries.alarm_text(50, "en") == "High pressure alarm"
    assert fseries.alarm_text(183, "sv") == "Avfrostning"
    assert fseries.alarm_text(251, "en") == "Com. error ACC Modbus 40"


def test_a_number_nibe_gave_a_new_meaning_has_no_english_title():
    """150 was "High condensor out" in 2017 and a temporary HP alarm by 2020."""
    assert fseries.alarm_text(150, "sv") == "Tillfälligt HP larm"
    assert fseries.alarm_text(150, "en") == "Alarm 150"


def test_an_unlisted_number_still_reads_as_an_alarm():
    assert fseries.alarm_text(12345, "sv") == "Larm 12345"
    assert fseries.alarm_text(12345, "en") == "Alarm 12345"


def test_the_alarm_table_is_well_formed():
    assert len(fseries.ALARMS) >= 300
    for code, (swedish, english) in fseries.ALARMS.items():
        assert 0 < code < 1000, code
        assert swedish and swedish == swedish.strip(), code
        assert "  " not in swedish and "- " not in swedish.replace(" - ", ""), (code, swedish)
        assert english is None or (english and "  " not in english), (code, english)
        # A Home Assistant state holds at most 255 characters.
        assert len(swedish) <= 255 and len(english or "") <= 255, code


# --------------------------------------------------------------- accessories


def test_setup_reads_the_flags_that_say_which_accessories_are_fitted():
    """Every register answers through the gateway, so the pump has to be asked
    what it actually has before its accessories' registers mean anything."""
    flags = fseries.flag_registers(F1255_MAP)
    titles = {F1255_MAP[r]["title"] for r in flags}
    assert "FLM 1 accessory" in titles and "Pool 1 accessory" in titles
    assert set(flags) <= set(fseries.default_registers(F1255_MAP))


def test_an_exhaust_air_module_brings_its_own_registers():
    fitted = {r: "ON" for r in fseries.flag_registers(F1255_MAP)
              if F1255_MAP[r]["title"] == "FLM 1 accessory"}
    wanted = fseries.accessory_registers(F1255_MAP, fitted)
    titles = {F1255_MAP[r]["title"] for r in wanted}
    # The speed selector myUplink uses, which NIBE leaves out of its list.
    assert 47260 in wanted
    assert "Fan Mode" in titles
    assert "Exhaust Fan speed normal" in titles
    # Another module's registers are not read for this one.
    assert not any(title.startswith("FLM 2") for title in titles)
    # A pool the pump does not have stays unread.
    assert not any(title.startswith("Pool") for title in titles)


def test_nothing_extra_is_read_when_the_pump_has_no_accessories():
    none_fitted = {r: "OFF" for r in fseries.flag_registers(F1255_MAP)}
    assert fseries.accessory_registers(F1255_MAP, none_fitted) == []


def test_an_accessorys_register_is_switched_on_when_it_answered():
    """It is only read at all when its flag said the accessory is there."""
    fan = F1255_MAP[47260]
    assert fseries.is_default(fan, reporting=True)
    assert not fseries.is_default(fan, reporting=False)


def test_the_modules_fan_selector_is_a_choice_not_a_number():
    """49280 takes the same values 43108 reports, but the library gives it no
    labels, so it would have arrived as a number between nothing and nothing."""
    fan = F1255_MAP[49280]
    assert fan["mappings"] == F1255_MAP[43108]["mappings"]
    assert (fan["min"], fan["max"]) == (0, 4)
    assert fan["write"] is True
