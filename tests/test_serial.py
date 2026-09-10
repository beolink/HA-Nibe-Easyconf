"""Decoding the NIBE serial number, and keeping its identifying part at home."""

from __future__ import annotations

from datetime import date
import importlib

from .conftest import PACKAGE

serial = importlib.import_module(f"{PACKAGE}.serial")
stats_extra = importlib.import_module(f"{PACKAGE}.stats_extra")

#: The development unit: an S1155-16 built on 3 February 2022.
REAL = "06544322034003"


def test_serial_comes_out_of_the_network_name():
    assert serial.serial_from_hostname("NIBE-06544322034003") == REAL
    assert serial.serial_from_hostname("NIBE-06544322034003.localdomain") == REAL
    assert serial.serial_from_hostname("nibe-06544322034003") == REAL


def test_other_hostnames_are_not_serials():
    assert serial.serial_from_hostname("homeassistant.local") is None
    assert serial.serial_from_hostname("NIBE-12345") is None  # too short
    assert serial.serial_from_hostname("NIBE-065443220340031") is None  # too long
    assert serial.serial_from_hostname(None) is None


def test_the_documented_fields():
    parsed = serial.parse_serial(REAL)
    assert parsed.article == "065443"
    assert parsed.year == 2022
    assert parsed.day_of_year == 34
    assert parsed.sequence == "003"


def test_day_of_year_is_a_day_not_a_week():
    """NIBE writes the day of the year where CTC writes a week number."""
    parsed = serial.parse_serial(REAL)
    assert parsed.manufactured == date(2022, 2, 3)
    assert parsed.iso_week == 5


def test_article_number_names_the_model_and_size():
    parsed = serial.parse_serial(REAL)
    assert parsed.model_key == "s1155"
    assert parsed.size == "16"


def test_an_unknown_article_still_decodes_its_date():
    parsed = serial.parse_serial("06999922100001")
    assert parsed.model_key is None
    assert parsed.manufactured == date(2022, 4, 10)


def test_an_impossible_day_is_not_a_build_date():
    assert serial.parse_serial("06544322000003") is None  # day 0
    assert serial.parse_serial("06544322367003") is None  # past any year's end
    assert serial.parse_serial("06544323366003") is None  # 2023 had no day 366
    assert serial.parse_serial("06544324366003") is not None  # 2024 did


def test_non_serials_are_rejected():
    assert serial.parse_serial("0654432203400") is None
    assert serial.parse_serial("06544322O34003") is None  # letter O
    assert serial.parse_serial("") is None
    assert serial.parse_serial(None) is None


# ------------------------------------------------ what reaches the report


def _report(serial_number):
    return stats_extra.build_extra("s1155", serial=serial_number)


def test_report_carries_article_and_build_week():
    report = _report(REAL)
    # In the model list, where it is kept verbatim; see test_backend_contract.
    assert report["models"] == ["s1155", "065443"]
    assert report["metrics"] == {"built_year": 2022, "built_week": 5}


def test_the_sequence_number_never_leaves():
    """Digits 12-14 are the only part that identifies one machine."""
    report = repr(_report(REAL))
    assert REAL not in report
    assert "22034003" not in report
    assert "'003'" not in report and ": 3," not in report


def test_the_exact_day_never_leaves():
    """A week is as fine-grained as anything in the report gets."""
    metrics = _report(REAL)["metrics"]
    assert "day_of_year" not in metrics
    assert "built_day" not in metrics
    assert 34 not in metrics.values()


def test_no_serial_means_no_serial_fields():
    report = _report(None)
    assert report["models"] == ["s1155"]
    assert "metrics" not in report
