"""Adax heaters on local control, set up from IP + token."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AdaxDirectApi
from .const import CONF_HOST, CONF_TOKEN
from .coordinator import AdaxDirectConfigEntry, AdaxDirectCoordinator

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AdaxDirectConfigEntry) -> bool:
    """Set up one heater; the first poll must succeed or the entry is retried."""
    api = AdaxDirectApi(async_get_clientsession(hass, verify_ssl=False), entry.data[CONF_HOST], entry.data[CONF_TOKEN])
    coordinator = AdaxDirectCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()      # raises ConfigEntryNotReady
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AdaxDirectConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: AdaxDirectConfigEntry) -> None:
    """Host, token or an option changed: reload the entry."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


