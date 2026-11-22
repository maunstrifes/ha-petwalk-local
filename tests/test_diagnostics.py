"""Tests for the diagnostics download."""

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.petwalk_local.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .const import HOST, MODES_OK, STATES_OK


async def test_diagnostics_contain_raw_answers_but_no_address(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Users attach this to public issues, so the address must be redacted."""
    diagnostics = await async_get_config_entry_diagnostics(hass, loaded_entry)

    assert diagnostics == {
        "entry": {"data": {"host": "**REDACTED**", "port": "**REDACTED**"}},
        "last_update_success": True,
        "api": {"states": STATES_OK, "modes": MODES_OK},
    }
    assert HOST not in repr(diagnostics)
