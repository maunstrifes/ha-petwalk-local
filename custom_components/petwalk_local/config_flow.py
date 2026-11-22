"""Config flow: set up a door by host and port, or change its address later."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import (
    PetwalkAuthError,
    PetwalkClient,
    PetwalkConnectionError,
    PetwalkResponseError,
)
from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__package__)

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
    }
)


class PetwalkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the setup of a petWALK door."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the door's address and check that the API answers."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            errors = await self._async_validate(user_input)
            if not errors:
                return self.async_create_entry(title="petWALK", data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address of an existing door, keeping its entities."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            for other in self._async_current_entries(include_ignore=False):
                if other.entry_id != entry.entry_id and (
                    other.data.get(CONF_HOST),
                    other.data.get(CONF_PORT),
                ) == (user_input[CONF_HOST], user_input[CONF_PORT]):
                    return self.async_abort(reason="already_configured")
            errors = await self._async_validate(user_input)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )

    async def _async_validate(self, user_input: dict[str, Any]) -> dict[str, str]:
        client = PetwalkClient(
            async_get_clientsession(self.hass),
            user_input[CONF_HOST],
            user_input[CONF_PORT],
        )
        try:
            await client.async_get_data()
        except PetwalkConnectionError:
            return {"base": "cannot_connect"}
        except PetwalkAuthError:
            return {"base": "invalid_auth"}
        except PetwalkResponseError:
            return {"base": "invalid_response"}
        except Exception:
            _LOGGER.exception("Unexpected error while checking the door")
            return {"base": "unknown"}
        return {}
