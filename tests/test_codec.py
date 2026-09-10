"""Value decoding, including NIBE's per-datatype 'no reading' sentinels."""

import importlib

import pytest

from .conftest import PACKAGE

codec = importlib.import_module(f"{PACKAGE}.codec")


@pytest.mark.parametrize(
    ("size", "words", "expected"),
    [
        ("s16", [0x008C], 140),
        ("s16", [0xFFFF], -1),
        ("u16", [0xFFFE], 65534),
        ("s8", [0xFFFF], -1),
        ("u8", [0x0005], 5),
        # 32-bit values arrive low word first on S-series.
        ("u32", [0x11A7, 0x0000], 4519),
        ("s32", [0xFFFF, 0xFFFF], -1),
    ],
)
def test_decode_raw(size, words, expected):
    assert codec.decode_raw(size, words) == expected


def test_word_order_is_low_word_first():
    """The wrong order turns 4519 compressor starts into 296 million."""
    assert codec.decode_raw("u32", [0x11A7, 0x0000]) == 4519
    assert codec.decode_raw("u32", [0x0000, 0x11A7]) == 0x11A70000


@pytest.mark.parametrize(
    ("size", "words"),
    [
        ("s16", [0x8000]),
        ("u16", [0xFFFF]),
        ("s8", [0xFF80]),
        ("u8", [0x00FF]),
        ("s32", [0x0000, 0x8000]),
        ("u32", [0xFFFF, 0xFFFF]),
    ],
)
def test_sentinels_are_recognised(size, words):
    """Every size has its own 'not available' value; none may reach a dashboard."""
    assert codec.decode({"size": size, "factor": 1}, words) is None


def test_sentinel_is_size_specific():
    """-128 means 'no reading' for s8, but is an ordinary value for s16."""
    assert codec.is_unavailable("s8", -128)
    assert not codec.is_unavailable("s16", -128)


def test_scaling():
    assert codec.decode({"size": "s16", "factor": 10}, [0x008C]) == 14.0
    assert codec.decode({"size": "s16", "factor": 1}, [0x008C]) == 140


def test_encode_round_trip():
    for size in ("s16", "u16", "s32", "u32"):
        for value in (0, 1, -1 if size.startswith("s") else 2, 4519):
            words = codec.encode_raw(size, value)
            assert codec.decode_raw(size, words) == value


def test_unscale_rounds_to_the_nearest_raw_count():
    assert codec.unscale(14.04, 10) == 140
    assert codec.unscale(-25.0, 10) == -250
    assert codec.unscale(7, 1) == 7


def test_word_count():
    assert codec.word_count("s16") == 1
    assert codec.word_count("s8") == 1  # 8-bit values still occupy a full register
    assert codec.word_count("u32") == 2
