"""What a service and a button both do, written once."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN
from .storage import async_save


async def async_rescan(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Probe the pump again and reload it, so what was found gets entities.

    For a firmware update, or an accessory fitted since the last scan. The
    rescan_registers service and the button on the device both end up here.
    """
    coordinator = entry.runtime_data
    result = await coordinator.async_rescan()
    version = str((await async_get_integration(hass, DOMAIN)).version)
    await async_save(hass, entry.entry_id, result, version)
    # Newly discovered registers need entities, which are created at platform
    # setup, so the entry is reloaded to pick them up.
    hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))
