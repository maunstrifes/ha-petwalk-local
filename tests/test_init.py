"""Tests for setting up, polling and unloading the integration."""

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.petwalk_local.const import DOMAIN, SCAN_INTERVAL

from .conftest import FakeDoor, get_state

ENTITIES = [
    "cover.petwalk_door",
    "switch.petwalk_system",
    "switch.petwalk_brightness_sensor",
    "switch.petwalk_motion_in",
    "switch.petwalk_motion_out",
    "switch.petwalk_rfid",
    "switch.petwalk_time_schedule",
]


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_setup_creates_one_device_with_all_entities(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """One door, one device, seven entities with stable unique IDs."""
    assert loaded_entry.state is ConfigEntryState.LOADED

    [device] = dr.async_entries_for_config_entry(device_registry, loaded_entry.entry_id)
    assert device.identifiers == {(DOMAIN, loaded_entry.entry_id)}
    assert (device.manufacturer, device.model) == ("petWALK", "petWALK.control")

    entries = er.async_entries_for_config_entry(entity_registry, loaded_entry.entry_id)
    assert sorted(entry.entity_id for entry in entries) == sorted(ENTITIES)
    for entry in entries:
        assert entry.unique_id.startswith(f"{loaded_entry.entry_id}_")
        assert entry.device_id == device.id


async def test_unreachable_door_at_startup_retries(
    hass: HomeAssistant, config_entry: MockConfigEntry, door: FakeDoor
) -> None:
    """A door that is offline (or has the API disabled) is retried by HA."""
    door.serve(exc=ClientError())
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_outage_makes_entities_unavailable_and_recovers(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    door: FakeDoor,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Entities follow the door's reachability without a restart."""
    assert get_state(hass, "switch.petwalk_system").state == STATE_ON

    door.serve(exc=TimeoutError())
    await _poll(hass, freezer)
    for entity_id in ENTITIES:
        assert get_state(hass, entity_id).state == STATE_UNAVAILABLE

    door.states["system"] = "off"
    door.serve()
    await _poll(hass, freezer)
    assert get_state(hass, "switch.petwalk_system").state == STATE_OFF


async def test_unexpected_answers_make_entities_unavailable(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    door: FakeDoor,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Server errors are treated like an outage, not as a crash."""
    door.serve(status=500)
    await _poll(hass, freezer)

    assert get_state(hass, "cover.petwalk_door").state == STATE_UNAVAILABLE


async def test_unload(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Unloading removes the entities' states cleanly."""
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()

    assert loaded_entry.state is ConfigEntryState.NOT_LOADED
