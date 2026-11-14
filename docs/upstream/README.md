# Suggestions for the official Adax integration

These four documents are offered to the maintainers of Home Assistant's official `adax` integration, for adoption when and if they want it. Each one describes a gap in the integration as it is today, what this project does about it (with a link to the code), the smallest change we would suggest for core, how to test it, and what it would cost. Each can be read on its own. Nothing here is a pull request and nothing here is a request for support; the maintainers decide.

| Document | Suggestion | Filed |
|---|---|---|
| [01-modelled-energy.md](01-modelled-energy.md) | Modelled power and energy sensors for local entries | comment on the existing request: https://github.com/home-assistant/feature-requests/discussions/1962#discussioncomment-19613900 |
| [02-unavailable-debounce.md](02-unavailable-debounce.md) | A debounce before local entities become unavailable, and failures that really fail | https://github.com/orgs/home-assistant/discussions/5554 |
| [03-write-guard.md](03-write-guard.md) | Never send a target between 0 and 5 °C | https://github.com/orgs/home-assistant/discussions/5555 |
| [04-laptop-ble-setup.md](04-laptop-ble-setup.md) | A manual "IP address + token" local step, so heaters paired elsewhere can be added | https://github.com/orgs/home-assistant/discussions/5556 |

The "Filed" column is updated when a suggestion has been filed, with the link. Home Assistant core takes feature requests as discussions in the home-assistant organisation, one per suggestion; a defect found in the Adax-local library (see 04) belongs on that library's own issue tracker.

Adax-local library defect (`urllib.parse`): https://github.com/Danielhiversen/pyAdaxLocal/issues/24
