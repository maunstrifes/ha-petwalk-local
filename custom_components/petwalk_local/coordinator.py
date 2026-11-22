"""Polls the door and shares the result with all entities."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PetwalkClient, PetwalkData, PetwalkError
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__package__)

type PetwalkConfigEntry = ConfigEntry[PetwalkCoordinator]


class PetwalkCoordinator(DataUpdateCoordinator[PetwalkData]):
    """Fetches states and modes every few seconds."""

    config_entry: PetwalkConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: PetwalkConfigEntry, client: PetwalkClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> PetwalkData:
        try:
            return await self.client.async_get_data()
        except PetwalkError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
