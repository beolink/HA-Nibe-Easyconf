"""Diagnostics dump: what was discovered, and what is being polled."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import NibeCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: NibeCoordinator = entry.runtime_data
    discovery = coordinator.discovery
    registers = coordinator.registers

    def detail(register: int) -> dict[str, Any]:
        meta = registers.get(register, {})
        return {
            "register": register,
            "title": meta.get("title"),
            "unit": meta.get("unit"),
            "size": meta.get("size"),
            "writable": bool(meta.get("write")),
            "value": (coordinator.data or {}).get(register),
        }

    return {
        "connection": {
            "host": coordinator.client.host,
            "port": coordinator.client.port,
            "unit_id": coordinator.client.unit_id,
            "scan_interval": coordinator.update_interval.total_seconds()
            if coordinator.update_interval
            else None,
        },
        "discovery": {
            "summary": discovery.summary(),
            "present": len(discovery.present),
            "reporting": len(discovery.reporting),
            "unavailable": sorted(discovery.unavailable),
            "absent": len(discovery.absent),
        },
        "polling": {
            "subscribed": len(coordinator._subscribed),
            "block_reads": len(coordinator._spans),
        },
        "reporting_registers": [detail(r) for r in sorted(discovery.reporting)],
    }
