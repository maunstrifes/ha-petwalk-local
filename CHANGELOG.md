# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-11-22

### Added

- Door cover with opening/closing state until the door reports the new position.
- Switches for the door system and the five modes of the local API: brightness
  sensor, motion in, motion out, RFID and time schedule.
- Config flow that checks the door before saving, and a reconfigure flow to change
  its address without losing entities.
- Diagnostics download with the door's address redacted.
- English and German translations.
