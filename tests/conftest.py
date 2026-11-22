"""Shared fixtures for the petWALK Local tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, State
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.petwalk_local.const import DOMAIN

from .const import BASE_URL, HOST, MODES_OK, PORT, STATES_OK


def get_state(hass: HomeAssistant, entity_id: str) -> State:
    """Return an entity's state, failing the test if the entity does not exist."""
    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    return state


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components/."""


class FakeDoor:
    """Serves the door's API through Home Assistant's mocked HTTP session."""

    def __init__(self, aioclient_mock: AiohttpClientMocker) -> None:
        """Start with the documented example responses."""
        self._mock = aioclient_mock
        self.states: dict[str, Any] = dict(STATES_OK)
        self.modes: dict[str, Any] = dict(MODES_OK)
        self.serve()

    def serve(self, exc: Exception | None = None, status: int = 200) -> None:
        """(Re)register the responses; with ``exc`` the door is unreachable."""
        self._mock.clear_requests()
        if exc is not None:
            self._mock.get(f"{BASE_URL}/states", exc=exc)
            self._mock.put(f"{BASE_URL}/states", exc=exc)
            self._mock.put(f"{BASE_URL}/modes", exc=exc)
            return
        self._mock.get(f"{BASE_URL}/states", json=self.states, status=status)
        self._mock.get(f"{BASE_URL}/modes", json=self.modes, status=status)
        self._mock.put(f"{BASE_URL}/states", status=202)
        self._mock.put(f"{BASE_URL}/modes", status=202)

    @property
    def puts(self) -> list[tuple[str, Any]]:
        """Return (path, payload) of every PUT request so far."""
        return [
            (str(url).removeprefix(BASE_URL), data)
            for method, url, data, _ in self._mock.mock_calls
            if method == "PUT"
        ]


@pytest.fixture
def door(aioclient_mock: AiohttpClientMocker) -> FakeDoor:
    """Return a reachable fake door."""
    return FakeDoor(aioclient_mock)


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a config entry for the fake door."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="petWALK",
        data={CONF_HOST: HOST, CONF_PORT: PORT},
    )


@pytest.fixture
async def loaded_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry, door: FakeDoor
) -> MockConfigEntry:
    """Return a config entry that is set up against the fake door."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Keep config flow tests from setting up the integration."""
    with patch(
        "custom_components.petwalk_local.async_setup_entry", return_value=True
    ) as mock:
        yield mock
