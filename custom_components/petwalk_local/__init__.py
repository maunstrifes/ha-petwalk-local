"""The petWALK Local integration.

Controls a petWALK pet door through the official local API of the petWALK.control
module. See README.md for what the API offers and what it does not.
"""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PetwalkClient
from .coordinator import PetwalkConfigEntry, PetwalkCoordinator

PLATFORMS = [Platform.COVER, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: PetwalkConfigEntry) -> bool:
    """Connect to the door and set up its entities."""
    client = PetwalkClient(
        async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_PORT]
    )
    coordinator = PetwalkCoordinator(hass, entry, client)
    # Raises ConfigEntryNotReady if the door cannot be reached; HA retries.
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PetwalkConfigEntry) -> bool:
    """Unload the entities."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
