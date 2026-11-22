"""The system switch and the five mode switches."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import PetwalkClient, PetwalkData
from .coordinator import PetwalkConfigEntry, PetwalkCoordinator
from .entity import PetwalkEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PetwalkSwitchDescription(SwitchEntityDescription):
    """How to read and write one switch."""

    value_fn: Callable[[PetwalkData], bool | None]
    set_fn: Callable[[PetwalkClient, bool], Awaitable[None]]


def _mode(key: str, api_field: str) -> PetwalkSwitchDescription:
    return PetwalkSwitchDescription(
        key=key,
        translation_key=key,
        value_fn=lambda data: data.modes.get(api_field),
        set_fn=lambda client, on: client.async_set_mode(api_field, on),
    )


SWITCHES: tuple[PetwalkSwitchDescription, ...] = (
    PetwalkSwitchDescription(
        key="system",
        translation_key="system",
        value_fn=lambda data: data.system_on,
        set_fn=lambda client, on: client.async_set_system(on),
    ),
    _mode("brightness_sensor", "brightnessSensor"),
    _mode("motion_in", "motion_in"),
    _mode("motion_out", "motion_out"),
    _mode("rfid", "rfid"),
    _mode("time_schedule", "time"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PetwalkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switches."""
    async_add_entities(
        PetwalkSwitch(entry.runtime_data, description) for description in SWITCHES
    )


class PetwalkSwitch(PetwalkEntity, SwitchEntity):
    """One on/off setting of the door."""

    entity_description: PetwalkSwitchDescription

    def __init__(
        self, coordinator: PetwalkCoordinator, description: PetwalkSwitchDescription
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the reported value, None if the door did not report it."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the setting on."""
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the setting off."""
        await self._async_set(False)

    async def _async_set(self, on: bool) -> None:
        await self._async_command(
            self.entity_description.set_fn(self.coordinator.client, on)
        )
        await self.coordinator.async_request_refresh()
