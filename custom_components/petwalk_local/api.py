"""Client for the petWALK.control local API.

The API is documented at https://control.petwalk.solutions/doc/api/ (beta, 1.0.0).
It offers exactly four calls on port 8080:

* ``GET /states`` -> ``{"door": "open"|"closed", "system": "on"|"off"}``
* ``PUT /states`` with one or both fields, answered with ``202 Accepted``
* ``GET /modes`` -> five booleans, see :data:`MODES`
* ``PUT /modes`` with one or more of them, answered with ``202 Accepted``

The API is disabled by default and has to be enabled in the petWALK app. There is no
push channel, so callers have to poll.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout
from yarl import URL

from .const import DEFAULT_PORT, REQUEST_TIMEOUT

MODES: Final = ("brightnessSensor", "motion_in", "motion_out", "rfid", "time")

_DOOR_VALUES: Final = {"open": True, "closed": False}
_SYSTEM_VALUES: Final = {"on": True, "off": False}


class PetwalkError(Exception):
    """Base class for all errors talking to the door."""


class PetwalkConnectionError(PetwalkError):
    """The door could not be reached (offline, API disabled, timeout)."""


class PetwalkAuthError(PetwalkError):
    """The door rejected the request with 401 or 403."""


class PetwalkResponseError(PetwalkError):
    """The door answered, but not with what the API documents."""


@dataclass(frozen=True, slots=True)
class PetwalkData:
    """One snapshot of the door.

    ``None`` means the door did not report the value or reported one this
    integration does not know.
    """

    door_open: bool | None
    system_on: bool | None
    modes: Mapping[str, bool]
    raw: Mapping[str, Any] = field(default_factory=dict, compare=True)


def _parse_flag(value: Any, mapping: Mapping[str, bool]) -> bool | None:
    if not isinstance(value, str):
        return None
    return mapping.get(value.lower())


class PetwalkClient:
    """Talks to one door over the local API."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        port: int = DEFAULT_PORT,
    ) -> None:
        """Initialize the client; no request is made here."""
        self._session = session
        self._base_url = URL.build(scheme="http", host=host, port=port)
        self._timeout = ClientTimeout(total=REQUEST_TIMEOUT)

    @property
    def base_url(self) -> str:
        """Return the URL of the door's API root."""
        return str(self._base_url)

    async def async_get_data(self) -> PetwalkData:
        """Read states and modes."""
        states = await self._get("states")
        modes = await self._get("modes")
        return PetwalkData(
            door_open=_parse_flag(states.get("door"), _DOOR_VALUES),
            system_on=_parse_flag(states.get("system"), _SYSTEM_VALUES),
            modes={
                mode: value
                for mode in MODES
                if isinstance(value := modes.get(mode), bool)
            },
            raw={"states": states, "modes": modes},
        )

    async def async_set_door(self, open_door: bool) -> None:
        """Open or close the door leaf."""
        await self._put("states", {"door": "open" if open_door else "closed"})

    async def async_set_system(self, turn_on: bool) -> None:
        """Turn the door system on or off."""
        await self._put("states", {"system": "on" if turn_on else "off"})

    async def async_set_mode(self, mode: str, enabled: bool) -> None:
        """Enable or disable one of :data:`MODES`."""
        if mode not in MODES:
            raise ValueError(f"Unknown petWALK mode: {mode}")
        await self._put("modes", {mode: enabled})

    async def _get(self, path: str) -> dict[str, Any]:
        try:
            async with self._session.get(
                self._base_url / path, timeout=self._timeout
            ) as response:
                _raise_for_status(response)
                try:
                    payload = await response.json(content_type=None)
                except ValueError as err:
                    raise PetwalkResponseError(
                        f"GET /{path} did not return JSON"
                    ) from err
        except (ClientError, TimeoutError) as err:
            raise PetwalkConnectionError(f"GET /{path} failed: {err!r}") from err
        if not isinstance(payload, dict):
            raise PetwalkResponseError(f"GET /{path} did not return a JSON object")
        return payload

    async def _put(self, path: str, payload: dict[str, Any]) -> None:
        try:
            async with self._session.put(
                self._base_url / path, json=payload, timeout=self._timeout
            ) as response:
                _raise_for_status(response)
        except (ClientError, TimeoutError) as err:
            raise PetwalkConnectionError(f"PUT /{path} failed: {err!r}") from err


def _raise_for_status(response: ClientResponse) -> None:
    if response.status in (401, 403):
        raise PetwalkAuthError(f"The door rejected the request ({response.status})")
    if not 200 <= response.status < 300:
        raise PetwalkResponseError(f"Unexpected HTTP status {response.status}")
