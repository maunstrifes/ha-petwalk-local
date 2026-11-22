"""Tests for the door cover."""

from datetime import timedelta

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.petwalk_local.const import SCAN_INTERVAL
from custom_components.petwalk_local.cover import TARGET_TIMEOUT

from .conftest import FakeDoor, get_state

DOOR = "cover.petwalk_door"


async def _call(hass: HomeAssistant, service: str) -> None:
    await hass.services.async_call(
        Platform.COVER, service, {ATTR_ENTITY_ID: DOOR}, blocking=True
    )


async def _advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_door_attributes(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """A door that can be opened and closed, without position control."""
    state = get_state(hass, DOOR)

    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.DOOR
    assert state.attributes["supported_features"] == (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    )


@pytest.mark.parametrize(
    ("reported", "expected"),
    [("open", CoverState.OPEN), ("closed", CoverState.CLOSED), ("ajar", STATE_UNKNOWN)],
)
async def test_door_state_follows_the_api(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    door: FakeDoor,
    freezer: FrozenDateTimeFactory,
    reported: str,
    expected: str,
) -> None:
    """open/closed map to the cover state, anything else is unknown."""
    door.states["door"] = reported
    door.serve()
    await _advance(hass, freezer, SCAN_INTERVAL)

    assert get_state(hass, DOOR).state == expected


async def test_open_sends_command_and_shows_opening_until_reported(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    door: FakeDoor,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The API answers 202 before the door moves; show that it is on its way."""
    await _call(hass, SERVICE_OPEN_COVER)

    assert door.puts == [("/states", {"door": "open"})]
    assert get_state(hass, DOOR).state == CoverState.OPENING

    door.states["door"] = "open"
    door.serve()
    await _advance(hass, freezer, SCAN_INTERVAL)

    assert get_state(hass, DOOR).state == CoverState.OPEN


async def test_close_shows_closing_until_reported(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    door: FakeDoor,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Closing works the same way as opening."""
    door.states["door"] = "open"
    door.serve()
    await _advance(hass, freezer, SCAN_INTERVAL)

    await _call(hass, SERVICE_CLOSE_COVER)

    assert door.puts == [("/states", {"door": "closed"})]
    assert get_state(hass, DOOR).state == CoverState.CLOSING

    door.states["door"] = "closed"
    door.serve()
    await _advance(hass, freezer, SCAN_INTERVAL)

    assert get_state(hass, DOOR).state == CoverState.CLOSED


async def test_transition_ends_after_timeout_if_door_never_moves(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    door: FakeDoor,
    freezer: FrozenDateTimeFactory,
) -> None:
    """If the door ignores the command, the UI must not show 'opening' forever."""
    await _call(hass, SERVICE_OPEN_COVER)
    assert get_state(hass, DOOR).state == CoverState.OPENING

    await _advance(hass, freezer, TARGET_TIMEOUT + timedelta(seconds=1))

    assert get_state(hass, DOOR).state == CoverState.CLOSED


async def test_new_command_replaces_pending_transition(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    door: FakeDoor,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Close right after open: the earlier timeout must not end the new one."""
    await _call(hass, SERVICE_OPEN_COVER)
    door.states["door"] = "open"
    door.serve()
    await _advance(hass, freezer, timedelta(seconds=10))

    await _call(hass, SERVICE_CLOSE_COVER)
    await _advance(hass, freezer, timedelta(seconds=6))

    assert get_state(hass, DOOR).state == CoverState.CLOSING


async def test_failed_command_raises_and_keeps_state(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, door: FakeDoor
) -> None:
    """The user gets an error, the UI does not pretend the door moves."""
    door.serve(exc=ClientError())

    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, SERVICE_OPEN_COVER)

    assert err.value.translation_key == "command_failed"
    assert get_state(hass, DOOR).state == CoverState.CLOSED


async def test_unload_cancels_pending_transition(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """No timer may fire into a removed entity."""
    await _call(hass, SERVICE_OPEN_COVER)

    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await _advance(hass, freezer, TARGET_TIMEOUT + timedelta(seconds=1))
