"""Tests for the static integration metadata."""

import json
from pathlib import Path

from awesomeversion import AwesomeVersion
from homeassistant.const import __version__ as HA_VERSION  # noqa: N812

from custom_components.petwalk_local.const import DOMAIN

ROOT = Path(__file__).parent.parent
INTEGRATION = ROOT / "custom_components" / DOMAIN


def _json(path: Path) -> dict[str, object]:
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return data


def test_manifest_matches_domain_and_needs_no_requirements() -> None:
    """The manifest names the right domain and pulls in no third-party packages."""
    manifest = _json(INTEGRATION / "manifest.json")

    assert manifest["domain"] == DOMAIN
    assert manifest["iot_class"] == "local_polling"
    assert manifest["config_flow"] is True
    assert manifest["requirements"] == []


def test_hacs_minimum_version_is_covered_by_the_tests() -> None:
    """HACS must not offer the integration to versions older than the tested one."""
    minimum = _json(ROOT / "hacs.json")["homeassistant"]

    assert isinstance(minimum, str)
    assert AwesomeVersion(minimum) <= AwesomeVersion(HA_VERSION)


def test_translations_cover_every_string() -> None:
    """English and German must offer the same texts as strings.json."""

    def keys(node: object, prefix: str = "") -> set[str]:
        if not isinstance(node, dict):
            return {prefix}
        return set().union(*(keys(v, f"{prefix}.{k}") for k, v in node.items()))

    expected = keys(_json(INTEGRATION / "strings.json"))
    for language in ("en", "de"):
        assert (
            keys(_json(INTEGRATION / "translations" / f"{language}.json")) == expected
        )
