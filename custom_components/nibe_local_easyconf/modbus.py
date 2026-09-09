"""Minimal async Modbus TCP client tuned for NIBE S-series heat pumps.

Why not pymodbus/async_modbus? Two NIBE-specific behaviours need explicit
handling, and getting them wrong is the root of most "integration keeps timing
out" reports:

1. NIBE answers exception code 01 (ILLEGAL FUNCTION) for registers that simply
   are not implemented on this unit, where the spec would say 02 (ILLEGAL DATA
   ADDRESS). So 01 must be read as "this address does not exist here", not as
   "this device does not speak Modbus".

2. A multi-register read succeeds only if *every* register in the span is
   implemented. One hole anywhere in the range fails the whole request. Reads
   must therefore be grouped into contiguous runs of known-live registers.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import struct

_LOGGER = logging.getLogger(__name__)

FC_READ_HOLDING = 3
FC_READ_INPUT = 4
FC_WRITE_SINGLE = 6
FC_WRITE_MULTIPLE = 16

#: Largest span NIBE reliably answers in a single request.
MAX_READ_COUNT = 125

EXCEPTION_NAMES = {
    1: "ILLEGAL_FUNCTION",
    2: "ILLEGAL_DATA_ADDRESS",
    3: "ILLEGAL_DATA_VALUE",
    4: "SERVER_FAILURE",
    5: "ACKNOWLEDGE",
    6: "SERVER_BUSY",
}

#: Exception codes that mean "this register does not exist on this unit".
#: NIBE uses 01 where the spec would use 02, so both are treated the same.
NOT_IMPLEMENTED_CODES = frozenset({1, 2})


class ModbusError(Exception):
    """A Modbus exception response was returned by the heat pump."""

    def __init__(self, code: int) -> None:
        self.code = code
        super().__init__(f"Modbus exception {code} ({EXCEPTION_NAMES.get(code, '?')})")

    @property
    def not_implemented(self) -> bool:
        """True when the code means the register is absent, not that we erred."""
        return self.code in NOT_IMPLEMENTED_CODES


class ModbusTransportError(Exception):
    """Connection-level failure: socket closed, timed out, malformed frame."""


class NibeModbusClient:
    """Serialised Modbus TCP client with a persistent, self-healing connection."""

    def __init__(
        self,
        host: str,
        port: int = 502,
        unit_id: int = 1,
        timeout: float = 5.0,
    ) -> None:
        self._host = host
        self._port = port
        self._unit_id = unit_id
        self._timeout = timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        # NIBE handles one outstanding transaction at a time; serialise access.
        self._lock = asyncio.Lock()
        self._tid = 0

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def unit_id(self) -> int:
        return self._unit_id

    async def connect(self) -> None:
        await self.close()
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port), timeout=self._timeout
            )
        except (OSError, TimeoutError) as err:
            raise ModbusTransportError(
                f"Could not connect to {self._host}:{self._port}: {err}"
            ) from err

    async def close(self) -> None:
        writer, self._writer, self._reader = self._writer, None, None
        if writer is None:
            return
        writer.close()
        with contextlib.suppress(OSError, TimeoutError):
            await writer.wait_closed()

    async def _transact(self, pdu: bytes) -> bytes:
        """Send one PDU and return the response PDU body (function code stripped)."""
        if self._writer is None or self._reader is None:
            await self.connect()
        assert self._reader is not None and self._writer is not None

        self._tid = (self._tid + 1) & 0xFFFF
        header = struct.pack(">HHHB", self._tid, 0, len(pdu) + 1, self._unit_id)
        try:
            self._writer.write(header + pdu)
            await self._writer.drain()
            head = await asyncio.wait_for(
                self._reader.readexactly(8), timeout=self._timeout
            )
            _tid, _proto, length, _unit, func = struct.unpack(">HHHBB", head)
            body = await asyncio.wait_for(
                self._reader.readexactly(max(length - 2, 0)), timeout=self._timeout
            )
        except (OSError, TimeoutError, asyncio.IncompleteReadError, struct.error) as err:
            # The stream is no longer trustworthy; force a reconnect next call.
            await self.close()
            raise ModbusTransportError(str(err)) from err

        if func & 0x80:
            raise ModbusError(body[0] if body else 0)
        return body

    async def read_registers(self, fc: int, address: int, count: int) -> list[int]:
        """Read `count` raw 16-bit words. Raises ModbusError on any hole in the span."""
        if not 1 <= count <= MAX_READ_COUNT:
            raise ValueError(f"count must be 1..{MAX_READ_COUNT}, got {count}")
        pdu = struct.pack(">BHH", fc, address, count)
        async with self._lock:
            body = await self._transact(pdu)
        byte_count = body[0]
        words = body[1 : 1 + byte_count]
        if len(words) != count * 2:
            raise ModbusTransportError(
                f"Short read: wanted {count * 2} bytes, got {len(words)}"
            )
        return list(struct.unpack(f">{count}H", words))

    async def write_register(self, address: int, value: int) -> None:
        """Write a single holding register (function 6)."""
        pdu = struct.pack(">BHH", FC_WRITE_SINGLE, address, value & 0xFFFF)
        async with self._lock:
            await self._transact(pdu)

    async def write_registers(self, address: int, values: list[int]) -> None:
        """Write consecutive holding registers (function 16), used for 32-bit values."""
        payload = struct.pack(f">{len(values)}H", *(v & 0xFFFF for v in values))
        pdu = (
            struct.pack(">BHHB", FC_WRITE_MULTIPLE, address, len(values), len(payload))
            + payload
        )
        async with self._lock:
            await self._transact(pdu)

    async def probe(self, fc: int, address: int, count: int) -> list[int] | None:
        """Read a span, returning None when the span contains an unimplemented register."""
        try:
            return await self.read_registers(fc, address, count)
        except ModbusError as err:
            if err.not_implemented:
                return None
            raise
