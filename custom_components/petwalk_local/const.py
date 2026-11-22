"""Constants for the petWALK Local integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "petwalk_local"

DEFAULT_PORT: Final = 8080
SCAN_INTERVAL: Final = timedelta(seconds=5)
REQUEST_TIMEOUT: Final = 10
