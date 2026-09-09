"""Convert between NIBE register words and real values.

Sizes are the ones NIBE uses in its register maps. Note that s8/u8 still occupy
a full 16-bit register on the wire - the size only says how the value is
interpreted, not how much space it takes.

Each size has a reserved value meaning "no reading available". A sensor that is
not fitted, or a compressor module that is not installed, reports that sentinel
rather than failing the read, so it must be filtered out before the number
reaches a dashboard as a real -3276.8 °C.
"""

from __future__ import annotations

#: Words occupied on the wire, per size.
WORD_COUNT: dict[str, int] = {
    "u8": 1, "s8": 1, "u16": 1, "s16": 1, "u32": 2, "s32": 2,
}

SIGNED: frozenset[str] = frozenset({"s8", "s16", "s32"})

#: The value each size uses to say "not available".
SENTINEL: dict[str, int] = {
    "u8": 0xFF,
    "s8": -0x80,
    "u16": 0xFFFF,
    "s16": -0x8000,
    "u32": 0xFFFFFFFF,
    "s32": -0x80000000,
}


def word_count(size: str) -> int:
    return WORD_COUNT.get(size, 1)


def decode_raw(size: str, words: list[int]) -> int:
    """Decode register words into the raw integer, before any scaling.

    32-bit values are word-swapped on NIBE S-series: the low word comes first.
    """
    if word_count(size) == 2:
        if len(words) < 2:
            raise ValueError(f"{size} needs 2 words, got {len(words)}")
        raw_bytes = words[0].to_bytes(2, "little") + words[1].to_bytes(2, "little")
    else:
        raw_bytes = words[0].to_bytes(2, "little")
    return int.from_bytes(raw_bytes, "little", signed=size in SIGNED)


def encode_raw(size: str, value: int) -> list[int]:
    """Encode a raw integer back into register words."""
    count = word_count(size)
    raw_bytes = int(value).to_bytes(2 * count, "little", signed=size in SIGNED)
    return [
        int.from_bytes(raw_bytes[i : i + 2], "little", signed=False)
        for i in range(0, 2 * count, 2)
    ]


def is_unavailable(size: str, raw_value: int) -> bool:
    """True when the raw value is the size's 'no reading' sentinel."""
    return raw_value == SENTINEL.get(size)


def scale(raw_value: int, factor: int | float) -> float | int:
    """Apply the register's scaling factor."""
    if not factor or factor == 1:
        return raw_value
    return raw_value / factor


def unscale(value: float, factor: int | float) -> int:
    """Undo scaling, for writes."""
    if not factor or factor == 1:
        return round(value)
    return round(value * factor)


def decode(meta: dict, words: list[int]) -> float | int | None:
    """Decode words into a scaled value, or None when no reading is available."""
    size = meta.get("size", "s16")
    raw = decode_raw(size, words)
    if is_unavailable(size, raw):
        return None
    return scale(raw, meta.get("factor", 1))
