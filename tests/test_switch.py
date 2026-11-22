"""Tests for the system and mode switches."""

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
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

from .conftest import FakeDoor, get_state

# entity_id, API field, value in MODES_OK / STATES_OK
MODE_SWITCHES = [
    ("switch.petwalk_brightness_sensor", "brightnessSensor", STATE_ON),
    ("switch.petwalk_motion_in", "motion_in", STATE_ON),
    ("switch.petwalk_motion_out", "motion_out", STATE_OFF),
    ("switch.petwalk_rfid", "rfid", STATE_ON),
    ("switch.petwalk_time_schedule", "time", STATE_OFF),
]


async def _switch(hass: HomeAssistant, service: str, entity_id: str) -> None:
    await hass.services.async_call(
        Platform.SWITCH, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )


@pytest.mark.parametrize(("entity_id", "field", "expected"), MODE_SWITCHES)
async def test_mode_switch_state(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_id: str,
    field: str,
    expected: str,
) -> None:
    """Each mode switch shows its own field."""
    assert get_state(hass, entity_id).state == expected


@pytest.mark.parametrize(("entity_id", "field", "expected"), MODE_SWITCHES)
@pytest.mark.parametrize(
    ("service", "value"), [(SERVICE_TURN_ON, True), (SERVICE_TURN_OFF, False)]
)
async def test_mode_switch_sends_only_its_field(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    door: FakeDoor,
    entity_id: str,
    field: str,
    expected: str,
    service: str,
    value: bool,
) -> None:
    """Switching a mode must leave the other modes alone."""
    await _switch(hass, service, entity_id)

    assert door.puts == [("/modes", {field: value})]


async def test_system_switch(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, door: FakeDoor
) -> None:
    """The system switch reads and writes the 'system' state."""
    assert get_state(hass, "switch.petwalk_system").state == STATE_ON

    await _switch(hass, SERVICE_TURN_OFF, "switch.petwalk_system")
    await _switch(hass, SERVICE_TURN_ON, "switch.petwalk_system")

    assert door.puts == [("/states", {"system": "off"}), ("/states", {"system": "on"})]


async def test_switch_refreshes_after_command(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, door: FakeDoor
) -> None:
    """The new value shows up without waiting for the next poll."""
    door.modes["rfid"] = False
    door.serve()

    await _switch(hass, SERVICE_TURN_OFF, "switch.petwalk_rfid")

    assert get_state(hass, "switch.petwalk_rfid").state == STATE_OFF


async def test_missing_mode_is_unknown(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    door: FakeDoor,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A firmware that drops a mode must not crash the other switches."""
    del door.modes["time"]
    door.serve()
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert get_state(hass, "switch.petwalk_time_schedule").state == STATE_UNKNOWN
    assert get_state(hass, "switch.petwalk_rfid").state == STATE_ON


async def test_failed_switch_command_raises(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, door: FakeDoor
) -> None:
    """A command the door does not take is reported to the user."""
    door.serve(exc=ClientError())

    with pytest.raises(HomeAssistantError) as err:
        await _switch(hass, SERVICE_TURN_OFF, "switch.petwalk_motion_out")

    assert err.value.translation_key == "command_failed"
