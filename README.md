# petWALK Local for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories/)
[![CI](https://github.com/maunstrifes/ha-petwalk-local/actions/workflows/ci.yml/badge.svg)](https://github.com/maunstrifes/ha-petwalk-local/actions/workflows/ci.yml)
[![Validate](https://github.com/maunstrifes/ha-petwalk-local/actions/workflows/validate.yml/badge.svg)](https://github.com/maunstrifes/ha-petwalk-local/actions/workflows/validate.yml)

Control a [petWALK](https://www.petwalk.at/) pet door from Home Assistant through the
**official local API** of the petWALK.control module. Everything stays in your
network: no cloud account, no reverse-engineered protocols, no extra Python packages.

> This is a community project. It is not affiliated with, sponsored or endorsed by
> petWALK. All product names and trademarks belong to their owners.

## What you get

One device per door with these entities:

| Entity | Type | What it does |
|---|---|---|
| `cover.petwalk_door` | Cover (door) | Shows whether the door leaf is open or closed; opens and closes it. |
| `switch.petwalk_system` | Switch | Main switch of the door system. |
| `switch.petwalk_brightness_sensor` | Switch | Enables the brightness sensor mode. Its sensitivity can only be set in the petWALK app. |
| `switch.petwalk_motion_in` | Switch | Enables the *motion in* mode (motion sensor for pets coming in). |
| `switch.petwalk_motion_out` | Switch | Enables the *motion out* mode (motion sensor for pets going out). |
| `switch.petwalk_rfid` | Switch | Enables the RFID mode (only registered pets). |
| `switch.petwalk_time_schedule` | Switch | Enables the time schedule configured in the petWALK app. |

Entity IDs depend on your language and on the name you give the device; the table
shows the English defaults. The mode names follow the API. Compare them with your
door's settings in the petWALK app to see how they map to your setup.

The mode switches are ordinary switches, so you can use them in automations, for
example to keep your cat inside at night (see [examples](#example-automations)).

### What this integration cannot do

The official API only exposes the door state, the system state and the five modes
above. It does **not** tell which pet went in or out, does not report events, battery,
firmware version or serial number, and cannot change schedules or RFID registrations.

Older integrations got pet presence by imitating the petWALK app against its cloud
and a private WebSocket. That broke with door firmware 5.x. This integration
deliberately sticks to the documented API so that it keeps working as long as petWALK
keeps the API.

## Requirements

- A petWALK door with the **petWALK.control** module. Tested with door firmware 5.2.
- Home Assistant **2026.8** or newer.
- The **REST API enabled** in the petWALK app: *your door → Advanced settings →
  REST API*. The app also shows the door's IP address there.
  **After a firmware update you may have to enable it again.**
- Recommended: a fixed IP address for the door (a DHCP reservation in your router).

> **Security note:** the local API has no authentication. Anyone who can reach port
> 8080 of the door in your network can open it. If that matters to you, put the door
> in a network segment that untrusted devices cannot reach.

## Installation

### HACS (recommended)

1. In HACS, open the menu (⋮) → **Custom repositories**.
2. Add `https://github.com/maunstrifes/ha-petwalk-local` with type **Integration**.
3. Search for **petWALK Local**, install it and restart Home Assistant.

### Manual

Copy `custom_components/petwalk_local` into the `custom_components` folder of your
Home Assistant configuration and restart Home Assistant.

## Configuration

1. **Settings → Devices & services → Add integration → petWALK Local.**
2. Enter the door's IP address or host name. Keep port `8080` unless you know better.

The integration checks that the door answers before it saves anything. If the door
gets a new address later, use **⋮ → Reconfigure** on the integration entry. Your
entities, their history and your automations stay as they are.

## How it behaves

- **Polling:** the API has no push channel, so the door is polled every 5 seconds.
  A door opening that lasts less than that can go unnoticed.
- **Commands:** the door accepts a command before it executes it. After *open* or
  *close*, the cover shows *opening*/*closing* until the door reports the new state,
  for at most 15 seconds.
- **Outages:** if the door is unreachable, its entities become *unavailable* and
  recover by themselves once it answers again. If it is unreachable while Home
  Assistant starts, Home Assistant keeps retrying.
- **Unknown values:** if a future firmware reports a value this integration does not
  know, the entity shows *unknown* instead of failing.

## Example automations

Keep pets inside at night by switching off the *motion out* mode:

```yaml
automation:
  - alias: "Pet door: no going out at night"
    triggers:
      - trigger: time
        at: "21:00:00"
    actions:
      - action: switch.turn_off
        target:
          entity_id: switch.petwalk_motion_out

  - alias: "Pet door: going out allowed in the morning"
    triggers:
      - trigger: time
        at: "07:00:00"
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.petwalk_motion_out
```

Get a notification if the door stays open:

```yaml
automation:
  - alias: "Pet door: open for too long"
    triggers:
      - trigger: state
        entity_id: cover.petwalk_door
        to: "open"
        for: "00:05:00"
    actions:
      - action: notify.notify
        data:
          message: "The pet door has been open for 5 minutes."
```

## Troubleshooting

| Symptom | What to check |
|---|---|
| *The door did not answer* during setup | Is the REST API enabled in the app? Is the address right? Can Home Assistant reach the door's network? |
| Entities became *unavailable* after a firmware update | Enable the REST API in the app again. |
| Entities are *unavailable* now and then | Wi-Fi reception at the door; the log shows the reason. |
| *The door rejected the request* | Your firmware may require authentication. Please open an issue. |

For a bug report, attach the diagnostics: **Settings → Devices & services → petWALK
Local → ⋮ → Download diagnostics**. They contain the door's last raw answers, and the
door's address is redacted.

## Migrating from hapetwalk or its forks

This integration uses its own domain (`petwalk_local`), so it can run next to
`petwalk` integrations while you switch. Entity IDs differ, so update your
automations and dashboards, then remove the old integration.

## Development

Home Assistant does not run on Windows, so the checks run in Docker:

```bash
bash scripts/test.sh                      # ruff, mypy, privacy check, all tests
bash scripts/test.sh tests/test_cover.py  # just some tests
```

On Linux or macOS you can also install `requirements_test.txt` into a Python 3.14
virtual environment and run `bash scripts/checks.sh`.

The test requirements pin Home Assistant through
`pytest-homeassistant-custom-component`; raising that pin is how this integration
moves to a newer Home Assistant.

### Keep personal data out

This integration is developed against real doors in real homes.
`scripts/check_privacy.py` runs in CI and fails on:

- private IPv4 addresses (`10.x`, `172.16–31.x`, `192.168.x`) and
- e-mail addresses other than GitHub noreply addresses and `example.com`-style domains

in the working tree (including files not committed yet), in every line ever added
to the history, and in commit messages. It also fails on commits whose author or
committer e-mail is not a noreply address, and when git itself fails, so that an
unchecked repository never looks clean. Run it locally with
`python scripts/check_privacy.py`.

Use the documentation ranges (`192.0.2.x`, `198.51.100.x`, `203.0.113.x`) in tests
and docs, and commit with your
[GitHub noreply address](https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-personal-account-on-github/managing-email-preferences/setting-your-commit-email-address).

## License

[MIT](LICENSE)
