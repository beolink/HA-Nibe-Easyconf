"""Put the entity list with explanations in front of the user, without asking.

Two things are registered when the first pump is set up:

* **A sidebar panel, "NIBE".** This is what makes it automatic. A custom
  integration cannot create a dashboard cleanly: Home Assistant keeps the
  dashboards collection in a local variable inside the Lovelace component and
  never exposes it, so doing so means reaching into internals that move between
  releases. `panel_custom` is the public way to add a page - it is how HACS puts
  itself in the sidebar - and it needs nothing from the user.

* **The card itself as a Lovelace resource**, for anyone who wants it on their
  own dashboard as `custom:nibe-easyconf-card`. Registered the way the EMS
  integration does it: best effort on storage-mode Lovelace, with a version in
  the URL so browsers pick up a new card after an update. YAML-mode users add
  the resource by hand.

Neither ever edits an existing dashboard.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CARD_URL = f"/{DOMAIN}/nibe-easyconf-card.js"
CARD_FILE = Path(__file__).parent / "www" / "nibe-easyconf-card.js"
PANEL_URL_PATH = "nibe-easyconf"
PANEL_ELEMENT = "nibe-easyconf-panel"

_REGISTERED = f"{DOMAIN}_frontend_registered"


async def async_register_frontend(hass: HomeAssistant, version: str) -> None:
    """Serve the card, add it as a resource, and add the sidebar panel. Once."""
    if hass.data.get(_REGISTERED):
        return
    hass.data[_REGISTERED] = True
    versioned = f"{CARD_URL}?v={version}"

    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, str(CARD_FILE), False)]
        )
    except (RuntimeError, ValueError) as err:
        # Already served from an earlier load in this process.
        _LOGGER.debug("Static path for the card not registered: %s", err)

    await _async_register_resource(hass, versioned)

    try:
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=PANEL_URL_PATH,
            webcomponent_name=PANEL_ELEMENT,
            sidebar_title="NIBE",
            sidebar_icon="mdi:heat-pump",
            module_url=versioned,
            require_admin=False,
        )
    except ValueError as err:
        # A panel already sits at this path - from a reload, or another
        # integration. Leave it alone rather than overwrite it.
        _LOGGER.debug("Sidebar panel not registered: %s", err)


async def _async_register_resource(hass: HomeAssistant, versioned: str) -> None:
    """Add or refresh the card's Lovelace resource on storage-mode dashboards."""
    try:
        lovelace = hass.data.get("lovelace")
        resources = getattr(lovelace, "resources", None)
        if resources is None or not hasattr(resources, "async_create_item"):
            return  # YAML mode: documented as a manual step
        if not resources.loaded:
            await resources.async_load()
        existing = next(
            (
                item
                for item in resources.async_items()
                if item.get("url", "").startswith(CARD_URL)
            ),
            None,
        )
        if existing is None:
            await resources.async_create_item({"res_type": "module", "url": versioned})
            _LOGGER.info("Registered Lovelace resource %s", versioned)
        elif existing.get("url") != versioned:
            # Bump the cache-busting version so browsers load the new card.
            await resources.async_update_item(existing["id"], {"url": versioned})
            _LOGGER.info("Updated Lovelace resource to %s", versioned)
    except Exception as err:  # best effort: a resource is a convenience
        _LOGGER.debug("Lovelace resource auto-registration skipped: %s", err)


def async_unregister_frontend(hass: HomeAssistant) -> None:
    """Remove the sidebar panel once no pump is left to show."""
    if not hass.data.pop(_REGISTERED, False):
        return
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
