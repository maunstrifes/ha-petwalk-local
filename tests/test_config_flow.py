"""Tests for the config flow (setup and reconfigure)."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.petwalk_local.api import (
    PetwalkAuthError,
    PetwalkConnectionError,
    PetwalkResponseError,
)
from custom_components.petwalk_local.const import DOMAIN

from .const import HOST, PORT

OTHER_HOST = "192.0.2.20"
GET_DATA = "custom_components.petwalk_local.config_flow.PetwalkClient.async_get_data"


async def test_user_flow_creates_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Host and port are checked against the door and stored."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(GET_DATA) as get_data:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
        )

    get_data.assert_awaited_once()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "petWALK"
    assert result["data"] == {CONF_HOST: HOST, CONF_PORT: PORT}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_port_defaults_to_8080(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Most users only need to enter the host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(GET_DATA):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST}
        )

    assert result["data"] == {CONF_HOST: HOST, CONF_PORT: 8080}


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (PetwalkConnectionError, "cannot_connect"),
        (PetwalkAuthError, "invalid_auth"),
        (PetwalkResponseError, "invalid_response"),
        (RuntimeError, "unknown"),
    ],
)
async def test_user_flow_errors_and_recovers(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    exc: type[Exception],
    error: str,
) -> None:
    """Each failure gets its own message; fixing it lets the user continue."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(GET_DATA, side_effect=exc):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    with patch(GET_DATA):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_same_door_cannot_be_added_twice(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_setup_entry: AsyncMock
) -> None:
    """The API has no serial number, so host and port identify a door."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(GET_DATA) as get_data:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    get_data.assert_not_awaited()


async def test_reconfigure_changes_host(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_setup_entry: AsyncMock
) -> None:
    """A new IP address keeps the entry and all entities."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(GET_DATA):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: OTHER_HOST, CONF_PORT: PORT}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {CONF_HOST: OTHER_HOST, CONF_PORT: PORT}


async def test_reconfigure_keeping_the_same_host_is_allowed(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_setup_entry: AsyncMock
) -> None:
    """Re-checking the current address must not count as a duplicate."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)

    with patch(GET_DATA):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
        )

    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_rejects_address_of_another_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_setup_entry: AsyncMock
) -> None:
    """Two entries must never point at the same door."""
    config_entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: OTHER_HOST, CONF_PORT: PORT}
    ).add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)

    with patch(GET_DATA):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: OTHER_HOST, CONF_PORT: PORT}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_error_keeps_old_data(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_setup_entry: AsyncMock
) -> None:
    """An unreachable new address is not saved."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)

    with patch(GET_DATA, side_effect=PetwalkConnectionError):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: OTHER_HOST, CONF_PORT: PORT}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert config_entry.data == {CONF_HOST: HOST, CONF_PORT: PORT}
