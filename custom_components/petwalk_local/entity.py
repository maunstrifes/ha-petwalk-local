"""Base entity shared by all platforms."""

from __future__ import annotations

from collections.abc import Awaitable

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import PetwalkError
from .const import DOMAIN
from .coordinator import PetwalkCoordinator


class PetwalkEntity(CoordinatorEntity[PetwalkCoordinator]):
    """An entity of one door.

    The API exposes no serial number, so the config entry ID identifies the door.
    That keeps entity IDs stable when the door gets a new IP address.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: PetwalkCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="petWALK",
            model="petWALK.control",
        )

    async def _async_command(self, command: Awaitable[None]) -> None:
        """Send a command, turning API errors into a message for the user."""
        try:
            await command
        except PetwalkError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
