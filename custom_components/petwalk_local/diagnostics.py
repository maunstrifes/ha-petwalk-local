"""Diagnostics download.

Users attach this to public bug reports, so the door's address is redacted.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .coordinator import PetwalkConfigEntry

TO_REDACT = {CONF_HOST, CONF_PORT}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PetwalkConfigEntry
) -> dict[str, Any]:
    """Return the configuration and the door's last raw answers."""
    coordinator = entry.runtime_data
    return {
        "entry": {"data": async_redact_data(dict(entry.data), TO_REDACT)},
        "last_update_success": coordinator.last_update_success,
        "api": dict(coordinator.data.raw) if coordinator.data else None,
    }
