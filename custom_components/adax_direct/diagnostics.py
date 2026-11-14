"""Diagnostics download; the token is redacted."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN
from .coordinator import AdaxDirectConfigEntry

TO_REDACT = {CONF_TOKEN}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: AdaxDirectConfigEntry) -> dict[str, Any]:
    data = entry.runtime_data.data
    return {
        "entry": async_redact_data({"data": dict(entry.data), "options": dict(entry.options)}, TO_REDACT),
        "last_poll": {
            "raw": data.raw,
            "action": data.action,
            "power_w": data.power_w,
            "poll_time": data.poll_time.isoformat(),
        },
        "energy_kwh": entry.runtime_data.energy_kwh,
    }
