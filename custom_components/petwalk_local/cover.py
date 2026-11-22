"""The door leaf as a cover entity."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Final

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .coordinator import PetwalkConfigEntry, PetwalkCoordinator
from .entity import PetwalkEntity

# The API accepts a command (202) before the door moves. Until polling reports the
# requested state, the door shows as opening/closing, but never longer than this.
TARGET_TIMEOUT: Final = timedelta(seconds=15)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PetwalkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the door cover."""
    async_add_entities([PetwalkDoor(entry.runtime_data)])


class PetwalkDoor(PetwalkEntity, CoverEntity):
    """Opens and closes the door leaf."""

    _attr_device_class = CoverDeviceClass.DOOR
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    _attr_translation_key = "door"

    def __init__(self, coordinator: PetwalkCoordinator) -> None:
        """Initialize the door."""
        super().__init__(coordinator, "door")
        self._target_open: bool | None = None
        self._cancel_target: CALLBACK_TYPE | None = None

    @property
    def is_closed(self) -> bool | None:
        """Return whether the door is closed, None if unknown."""
        door_open = self.coordinator.data.door_open
        return None if door_open is None else not door_open

    @property
    def is_opening(self) -> bool:
        """Return whether an open command is still on its way."""
        return self._target_open is True

    @property
    def is_closing(self) -> bool:
        """Return whether a close command is still on its way."""
        return self._target_open is False

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the door."""
        await self._async_move(open_door=True)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the door."""
        await self._async_move(open_door=False)

    async def _async_move(self, *, open_door: bool) -> None:
        await self._async_command(self.coordinator.client.async_set_door(open_door))
        self._set_target(open_door)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    def _set_target(self, open_door: bool | None) -> None:
        if self._cancel_target is not None:
            self._cancel_target()
            self._cancel_target = None
        self._target_open = open_door
        if open_door is not None:
            self._cancel_target = async_call_later(
                self.hass, TARGET_TIMEOUT, self._target_timed_out
            )

    @callback
    def _target_timed_out(self, _now: datetime) -> None:
        self._cancel_target = None
        self._target_open = None
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        if (
            self._target_open is not None
            and self.coordinator.data.door_open is self._target_open
        ):
            self._set_target(None)
        super()._handle_coordinator_update()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel a pending timeout."""
        self._set_target(None)
        await super().async_will_remove_from_hass()
