"""Persist what discovery found, so a restart does not re-probe the pump.

A full scan is around 900 Modbus round-trips and takes the better part of a
minute. The register layout only changes when firmware is updated or an
accessory is fitted, so the result is cached and refreshed on demand through
the rescan service.

The heating mode select keeps its own small file beside it: the mode last
chosen and the offset that is normal for the house (see heating_mode.py).
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .discovery import DiscoveryResult

STORAGE_VERSION = 1


def _store(hass: HomeAssistant, entry_id: str) -> Store:
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.discovery")


def heating_mode_store(hass: HomeAssistant, entry_id: str) -> Store:
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.heating_mode")


async def async_load(hass: HomeAssistant, entry_id: str) -> DiscoveryResult | None:
    data = await _store(hass, entry_id).async_load()
    if not data:
        return None
    probed = data.get("probed")
    return DiscoveryResult(
        present=set(data.get("present", [])),
        reporting=set(data.get("reporting", [])),
        absent=set(data.get("absent", [])),
        probed=None if probed is None else set(probed),
    )


async def async_save(hass: HomeAssistant, entry_id: str, result: DiscoveryResult) -> None:
    data = {
        "present": sorted(result.present),
        "reporting": sorted(result.reporting),
        "absent": sorted(result.absent),
    }
    if result.probed is not None:
        data["probed"] = sorted(result.probed)
    await _store(hass, entry_id).async_save(data)


async def async_remove(hass: HomeAssistant, entry_id: str) -> None:
    await _store(hass, entry_id).async_remove()
    await heating_mode_store(hass, entry_id).async_remove()
