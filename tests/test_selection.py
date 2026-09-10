"""Which registers become entities, and on which platform."""

import importlib

from .conftest import PACKAGE

const = importlib.import_module(f"{PACKAGE}.const")


def test_writable_registers_become_controls():
    assert const.platform_for({"write": True, "unit": "°C", "min": 0, "max": 100}) == "number"
    assert const.platform_for({"write": True, "min": 0, "max": 1}) == "switch"
    assert const.platform_for({"write": True, "mappings": {"0": "Off"}}) == "select"


def test_read_only_registers_become_sensors():
    assert const.platform_for({"unit": "°C"}) == "sensor"
    assert const.platform_for({"mappings": {"0": "Off"}}) == "sensor"
    assert const.platform_for({"min": 0, "max": 1}) == "binary_sensor"


def test_a_unit_keeps_a_zero_to_one_register_numeric():
    """0-100 % scaled to 0..1 is a measurement, not a flag."""
    assert const.platform_for({"min": 0, "max": 1, "unit": "%"}) == "sensor"


def test_core_registers_are_the_ones_worth_showing():
    for title in (
        "Current outdoor temperature (BT1)",
        "Supply line (BT2)",
        "Degree minutes",
        "Compressor status",
        "Alarm number",
        "Heating curve climate system 1",
    ):
        assert const.is_core_register(title, {}), title


def test_hardware_most_homes_do_not_have_stays_off_by_default():
    """The pump answers for these whether or not the hardware exists."""
    for title in (
        "Fan rpm (EB105-EP14)",
        "Heat pump 6 requested compressor frequency",
        "Supply line (EP22-BT2)",
        "Zone 11 affected by ECS1",
        "Solar panel temp (BT53)",
        "Pool 1 temp (BT51)",
        "Floor drying temp. 6",
    ):
        assert not const.is_core_register(title, {}), title


def test_the_tariff_configuration_is_not_a_default_dashboard():
    """Around 75 registers of price and tariff settings, none of them urgent."""
    for title in (
        "Energy price 18:00 - 19:00",
        "El. price, fixed, smart energy source",
        "Start month tariff, shunt additional heat smart energy source",
        "Prim. factor, smart energy source",
    ):
        assert not const.is_core_register(title, {}), title
