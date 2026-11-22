"""Shared test data.

Only RFC 5737 documentation addresses are used here; see scripts/check_privacy.py.
"""

from typing import Any, Final

HOST: Final = "192.0.2.10"
PORT: Final = 8080
BASE_URL: Final = f"http://{HOST}:{PORT}"

# Responses as documented at https://control.petwalk.solutions/doc/api/, with two
# modes switched off so tests can tell the values apart.
STATES_OK: Final[dict[str, Any]] = {"door": "closed", "system": "on"}
MODES_OK: Final[dict[str, Any]] = {
    "brightnessSensor": True,
    "motion_in": True,
    "motion_out": False,
    "rfid": True,
    "time": False,
}
