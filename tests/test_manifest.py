"""Tests for the static integration metadata."""

import json
from pathlib import Path

from custom_components.petwalk_local.const import DOMAIN

ROOT = Path(__file__).parent.parent
INTEGRATION = ROOT / "custom_components" / DOMAIN


def test_manifest_matches_domain_and_needs_no_requirements() -> None:
    """The manifest names the right domain and pulls in no third-party packages."""
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["domain"] == DOMAIN
    assert manifest["iot_class"] == "local_polling"
    assert manifest["config_flow"] is True
    assert manifest["requirements"] == []


def test_hacs_minimum_version_is_not_newer_than_tested_version() -> None:
    """HACS must not offer the integration to versions older than the tested one."""
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    requirements = (ROOT / "requirements_test.txt").read_text(encoding="utf-8")

    assert hacs["homeassistant"] == "2026.8.0"
    assert "pytest-homeassistant-custom-component==0.13.356" in requirements
