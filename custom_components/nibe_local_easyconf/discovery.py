"""Find out which Modbus registers this particular heat pump actually answers.

NIBE publishes one register map per model, but an individual unit implements
only a subset of it: registers for absent accessories, extra compressor modules
or unfitted sensors are simply not there. Two different "not there" cases matter
and are deliberately kept apart:

* **absent**  - the register is not implemented; reading it returns a Modbus
  exception and, worse, poisons any block read that spans it.
* **unavailable** - the register exists but currently reports NIBE's
  sentinel for "no reading" (0x8000 for signed, 0xFFFF for unsigned).

Only registers that are present *and* reporting become entities.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging

from .codec import decode_raw, is_unavailable, word_count
from .modbus import (
    FC_READ_HOLDING,
    FC_READ_INPUT,
    MAX_READ_COUNT,
    ModbusTransportError,
    NibeModbusClient,
)

_LOGGER = logging.getLogger(__name__)


def function_code(register: int) -> int:
    """NIBE 3xxxx registers are input registers, 4xxxx are holding registers."""
    return FC_READ_INPUT if register // 10000 == 3 else FC_READ_HOLDING


def modbus_address(register: int) -> int:
    """Map a NIBE register number onto its zero-based Modbus address."""
    return (register % 10000) - 1


def is_sentinel(raw_words: list[int], size: str) -> bool:
    """True when the raw words carry NIBE's 'no reading' sentinel for this size."""
    return is_unavailable(size, decode_raw(size, raw_words))


@dataclass
class Span:
    """A contiguous, fully-implemented run of registers, safe to read in one request."""

    fc: int
    start: int
    count: int

    @property
    def end(self) -> int:
        return self.start + self.count - 1


@dataclass
class DiscoveryResult:
    present: set[int] = field(default_factory=set)
    """Registers the pump implements."""

    reporting: set[int] = field(default_factory=set)
    """Registers that implement *and* currently return a real reading."""

    absent: set[int] = field(default_factory=set)
    """Registers the pump does not implement at all."""

    raw: dict[int, list[int]] = field(default_factory=dict)
    """First-pass raw words, keyed by register number."""

    @property
    def unavailable(self) -> set[int]:
        return self.present - self.reporting

    def summary(self) -> str:
        return (
            f"{len(self.present)} present "
            f"({len(self.reporting)} reporting, {len(self.unavailable)} unavailable), "
            f"{len(self.absent)} absent"
        )


class RegisterDiscovery:
    """Adaptive prober that maps live registers with few round-trips.

    A block read succeeds only when every register in the span is implemented,
    which turns the whole request into a single "is this entire range live?"
    oracle. That makes divide-and-conquer far cheaper than probing address by
    address: a fully-live block of 125 registers costs one request instead of
    125, and only blocks that straddle a hole get split.
    """

    def __init__(self, client: NibeModbusClient, max_block: int = MAX_READ_COUNT) -> None:
        self._client = client
        self._max_block = max_block
        self.requests = 0

    async def _probe(self, fc: int, start: int, count: int) -> list[int] | None:
        self.requests += 1
        for attempt in range(3):
            try:
                return await self._client.probe(fc, start, count)
            except ModbusTransportError:
                if attempt == 2:
                    raise
                await asyncio.sleep(0.3 * (attempt + 1))
        return None

    async def _scan_range(
        self, fc: int, start: int, count: int, out: dict[int, int]
    ) -> None:
        """Recursively resolve [start, start+count) into live addresses."""
        while count > 0:
            block = min(count, self._max_block)
            words = await self._probe(fc, start, block)
            if words is not None:
                for offset, word in enumerate(words):
                    out[start + offset] = word
                start += block
                count -= block
                continue
            if block == 1:
                # Single address and it is not implemented.
                start += 1
                count -= 1
                continue
            # A hole sits somewhere in this block: split and recurse.
            half = block // 2
            await self._scan_range(fc, start, half, out)
            start += half
            count -= half

    async def run(
        self,
        registers: dict[int, dict],
        progress: callable | None = None,
    ) -> DiscoveryResult:
        """Probe every register in `registers` (a NIBE register-number -> metadata map)."""
        result = DiscoveryResult()

        by_fc: dict[int, list[int]] = {}
        for register in registers:
            by_fc.setdefault(function_code(register), []).append(register)

        for fc, regs in by_fc.items():
            # Build the address set, expanding 32-bit registers to both words.
            wanted: set[int] = set()
            for register in regs:
                address = modbus_address(register)
                for i in range(word_count(registers[register].get("size", "s16"))):
                    wanted.add(address + i)

            found: dict[int, int] = {}
            for span_start, span_count in _contiguous(sorted(wanted)):
                await self._scan_range(fc, span_start, span_count, found)
                if progress is not None:
                    progress(len(found), len(wanted))

            for register in regs:
                meta = registers[register]
                address = modbus_address(register)
                words = [
                    found[address + i]
                    for i in range(word_count(meta.get("size", "s16")))
                    if address + i in found
                ]
                if len(words) != word_count(meta.get("size", "s16")):
                    result.absent.add(register)
                    continue
                result.present.add(register)
                result.raw[register] = words
                if not is_sentinel(words, meta.get("size", "s16")):
                    result.reporting.add(register)

        _LOGGER.debug(
            "Register discovery finished in %s requests: %s",
            self.requests,
            result.summary(),
        )
        return result


def _contiguous(sorted_values: list[int]) -> list[tuple[int, int]]:
    """Collapse a sorted address list into (start, count) runs."""
    runs: list[tuple[int, int]] = []
    if not sorted_values:
        return runs
    start = prev = sorted_values[0]
    for value in sorted_values[1:]:
        if value != prev + 1:
            runs.append((start, prev - start + 1))
            start = value
        prev = value
    runs.append((start, prev - start + 1))
    return runs


def plan_spans(
    registers: dict[int, dict],
    wanted: set[int],
    present: set[int] | None = None,
    max_block: int = MAX_READ_COUNT,
    max_gap: int = 16,
) -> list[Span]:
    """Group the wanted registers into the fewest safe block reads.

    Every span must be contiguous and fully implemented, or the pump fails the
    whole request. Wanted registers are usually scattered, though, which would
    mean one round-trip each. Since a round-trip costs far more than a few extra
    words on the wire (~38 ms against ~0), spans are bridged across short gaps
    of registers we do not want - but only where every address in the gap is
    known to be implemented, so the read still cannot fail.

    `present` is the full set of implemented registers; without it no bridging
    happens and each run stands alone.
    """
    spans: list[Span] = []
    bridgeable = _address_set(registers, present) if present else {}

    by_fc: dict[int, set[int]] = {}
    for register in wanted:
        meta = registers.get(register, {})
        address = modbus_address(register)
        bucket = by_fc.setdefault(function_code(register), set())
        for i in range(word_count(meta.get("size", "s16"))):
            bucket.add(address + i)

    for fc, addresses in sorted(by_fc.items()):
        runs = _contiguous(sorted(addresses))
        merged = _bridge(runs, bridgeable.get(fc, set()), max_gap, max_block)
        for start, count in merged:
            while count > 0:
                block = min(count, max_block)
                spans.append(Span(fc=fc, start=start, count=block))
                start += block
                count -= block
    return spans


def _address_set(registers: dict[int, dict], present: set[int]) -> dict[int, set[int]]:
    """Implemented Modbus addresses per function code."""
    result: dict[int, set[int]] = {}
    for register in present:
        meta = registers.get(register, {})
        address = modbus_address(register)
        bucket = result.setdefault(function_code(register), set())
        for i in range(word_count(meta.get("size", "s16"))):
            bucket.add(address + i)
    return result


def _bridge(
    runs: list[tuple[int, int]],
    implemented: set[int],
    max_gap: int,
    max_block: int,
) -> list[tuple[int, int]]:
    """Merge runs separated by a short, fully-implemented gap."""
    if not runs:
        return []
    merged = [runs[0]]
    for start, count in runs[1:]:
        prev_start, prev_count = merged[-1]
        gap_start = prev_start + prev_count
        gap = start - gap_start
        combined = start + count - prev_start
        if (
            0 < gap <= max_gap
            and combined <= max_block
            and all(address in implemented for address in range(gap_start, start))
        ):
            merged[-1] = (prev_start, combined)
        else:
            merged.append((start, count))
    return merged
