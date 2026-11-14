"""I-06, I-20 ... I-24: registry defaults, diagnostics, logging, headers, unload, retry."""
import json
import logging

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import get_diagnostics_for_config_entry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler

from tests.fake_heater import TOKEN
from tests.integration.conftest import REPORTED_ENERG, REPORTED_POW


async def test_reported_sensors_disabled(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    registry = er.async_get(hass)
    for entity_id in (REPORTED_POW, REPORTED_ENERG):
        entry = registry.async_get(entity_id)
        assert entry is not None, entity_id
        assert entry.disabled_by == RegistryEntryDisabler.INTEGRATION, entity_id


async def test_diagnostics_redacts_token(hass: HomeAssistant, hass_client, setup_entry: MockConfigEntry) -> None:
    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, setup_entry)
    dumped = json.dumps(diagnostics)
    assert TOKEN not in dumped
    assert "**REDACTED**" in dumped
    assert diagnostics["entry"]["data"]["host"] == "192.0.2.10"
    assert diagnostics["last_poll"]["raw"] == {"currTemp": 1632, "targTemp": 900, "energ": 0, "pow": 0}


async def test_token_never_logged(
    hass: HomeAssistant, setup_entry: MockConfigEntry, fake, refresh, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    fake.mode = "timeout"
    for _ in range(5):
        await refresh()
    assert TOKEN not in caplog.text
    assert "poll failure 5/5" in caplog.text


async def test_authorization_header(hass: HomeAssistant, mock_heater, setup_entry: MockConfigEntry) -> None:
    assert mock_heater.mock_calls
    for _method, url, _data, headers in mock_heater.mock_calls:
        assert headers == {"Authorization": "Basic " + TOKEN}
        assert url.query["command"] == "stat"
        assert int(url.query["time"]) > 0


async def test_unload(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    assert setup_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    await hass.async_block_till_done()
    assert setup_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry_when_unreachable(
    hass: HomeAssistant, mock_heater, config_entry: MockConfigEntry, fake
) -> None:
    fake.mode = "http500"
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
