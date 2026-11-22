"""Tests for the petWALK.control local API client."""

from typing import Any

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.petwalk_local.api import (
    MODES,
    PetwalkAuthError,
    PetwalkClient,
    PetwalkConnectionError,
    PetwalkData,
    PetwalkResponseError,
)

from .const import BASE_URL, HOST, MODES_OK, PORT, STATES_OK


@pytest.fixture
async def client(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> PetwalkClient:
    """Return a client bound to Home Assistant's mocked HTTP session."""
    return PetwalkClient(async_get_clientsession(hass), HOST, PORT)


def _mock_ok(aioclient_mock: AiohttpClientMocker, **states: Any) -> None:
    aioclient_mock.get(f"{BASE_URL}/states", json={**STATES_OK, **states})
    aioclient_mock.get(f"{BASE_URL}/modes", json=MODES_OK)


async def test_get_data_parses_documented_response(
    client: PetwalkClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """The documented example responses map onto PetwalkData."""
    _mock_ok(aioclient_mock)

    data = await client.async_get_data()

    assert data == PetwalkData(
        door_open=False,
        system_on=True,
        modes={
            "brightnessSensor": True,
            "motion_in": True,
            "motion_out": False,
            "rfid": True,
            "time": False,
        },
        raw={"states": STATES_OK, "modes": MODES_OK},
    )


@pytest.mark.parametrize(
    ("states", "door_open", "system_on"),
    [
        ({"door": "open", "system": "off"}, True, False),
        ({"door": "closed", "system": "on"}, False, True),
        ({"door": "OPEN", "system": "ON"}, True, True),
        ({"door": "half", "system": "standby"}, None, None),
        ({"door": None}, None, None),
        ({}, None, None),
    ],
)
async def test_unknown_or_missing_states_become_none(
    client: PetwalkClient,
    aioclient_mock: AiohttpClientMocker,
    states: dict[str, Any],
    door_open: bool | None,
    system_on: bool | None,
) -> None:
    """Values a future firmware might send must not crash the integration."""
    aioclient_mock.get(f"{BASE_URL}/states", json=states)
    aioclient_mock.get(f"{BASE_URL}/modes", json=MODES_OK)

    data = await client.async_get_data()

    assert (data.door_open, data.system_on) == (door_open, system_on)


async def test_modes_that_are_missing_or_not_boolean_are_left_out(
    client: PetwalkClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Only real booleans count; anything else is unknown."""
    aioclient_mock.get(f"{BASE_URL}/states", json=STATES_OK)
    aioclient_mock.get(
        f"{BASE_URL}/modes", json={"rfid": True, "time": "yes", "extra": True}
    )

    data = await client.async_get_data()

    assert data.modes == {"rfid": True}


@pytest.mark.parametrize(
    ("call", "path", "payload"),
    [
        (lambda c: c.async_set_door(True), "states", {"door": "open"}),
        (lambda c: c.async_set_door(False), "states", {"door": "closed"}),
        (lambda c: c.async_set_system(True), "states", {"system": "on"}),
        (lambda c: c.async_set_system(False), "states", {"system": "off"}),
        (
            lambda c: c.async_set_mode("motion_out", False),
            "modes",
            {"motion_out": False},
        ),
        (
            lambda c: c.async_set_mode("brightnessSensor", True),
            "modes",
            {"brightnessSensor": True},
        ),
    ],
)
async def test_commands_send_only_the_changed_field(
    client: PetwalkClient,
    aioclient_mock: AiohttpClientMocker,
    call: Any,
    path: str,
    payload: dict[str, Any],
) -> None:
    """A command must not touch any other setting of the door."""
    aioclient_mock.put(f"{BASE_URL}/{path}", status=202)

    await call(client)

    assert aioclient_mock.call_count == 1
    method, url, data, _ = aioclient_mock.mock_calls[0]
    assert (method, str(url), data) == ("PUT", f"{BASE_URL}/{path}", payload)


async def test_unknown_mode_is_rejected_before_any_request(
    client: PetwalkClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """A typo in a mode name must not reach the door."""
    with pytest.raises(ValueError, match="sleep"):
        await client.async_set_mode("sleep", True)

    assert aioclient_mock.call_count == 0


def test_modes_constant_matches_documentation() -> None:
    """The five modes of the official API, spelled as the door expects them."""
    assert MODES == ("brightnessSensor", "motion_in", "motion_out", "rfid", "time")


@pytest.mark.parametrize("exc", [ClientError(), TimeoutError()])
async def test_network_problems_raise_connection_error(
    client: PetwalkClient, aioclient_mock: AiohttpClientMocker, exc: Exception
) -> None:
    """Unreachable door, refused port (API disabled) or timeout."""
    aioclient_mock.get(f"{BASE_URL}/states", exc=exc)

    with pytest.raises(PetwalkConnectionError):
        await client.async_get_data()


async def test_network_problem_on_command_raises_connection_error(
    client: PetwalkClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Commands report network problems the same way."""
    aioclient_mock.put(f"{BASE_URL}/states", exc=ClientError())

    with pytest.raises(PetwalkConnectionError):
        await client.async_set_door(True)


@pytest.mark.parametrize("status", [401, 403])
async def test_rejected_credentials_raise_auth_error(
    client: PetwalkClient, aioclient_mock: AiohttpClientMocker, status: int
) -> None:
    """The door refusing access is distinct from the door being unreachable."""
    aioclient_mock.get(f"{BASE_URL}/states", status=status)

    with pytest.raises(PetwalkAuthError):
        await client.async_get_data()


@pytest.mark.parametrize(
    "response",
    [
        {"status": 500},
        {"status": 404},
        {"text": "not json"},
        {"json": ["a", "list"]},
    ],
)
async def test_unexpected_responses_raise_response_error(
    client: PetwalkClient,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
) -> None:
    """Server errors and payloads that are not a JSON object."""
    aioclient_mock.get(f"{BASE_URL}/states", **response)

    with pytest.raises(PetwalkResponseError):
        await client.async_get_data()


async def test_failed_command_raises_response_error(
    client: PetwalkClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """A command the door does not accept is an error, not silently ignored."""
    aioclient_mock.put(f"{BASE_URL}/modes", status=400)

    with pytest.raises(PetwalkResponseError):
        await client.async_set_mode("rfid", True)


async def test_ipv6_host_is_bracketed(hass: HomeAssistant) -> None:
    """IPv6 literals need brackets in a URL."""
    client = PetwalkClient(async_get_clientsession(hass), "2001:db8::1", 8080)

    assert client.base_url == "http://[2001:db8::1]:8080"
