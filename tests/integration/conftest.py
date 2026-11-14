"""Fixtures: a fake heater served through aioclient_mock, and one config entry for it."""
from __future__ import annotations

import re
from urllib.parse import parse_qs

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMockResponse

from homeassistant.core import HomeAssistant

from tests.fake_heater import TOKEN, FakeHeater

HOST = "192.0.2.10"
DEVICE_ID = "900000000000001"
NAME = "Test Heater"
CLIMATE = "climate.test_heater"
TEMPERATURE = "sensor.test_heater_temperature"
POWER = "sensor.test_heater_power"
ENERGY = "sensor.test_heater_energy"
REPORTED_POW = "sensor.test_heater_reported_pow"
REPORTED_ENERG = "sensor.test_heater_reported_energ"
MAIN_ENTITIES = (CLIMATE, TEMPERATURE, POWER, ENERGY)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let HA load custom_components/adax_direct from this repository."""


@pytest.fixture
def fake() -> FakeHeater:
    return FakeHeater()


@pytest.fixture
def mock_heater(aioclient_mock, fake: FakeHeater):
    """Serve https://192.0.2.10 and 192.0.2.11 from the fake heater; no real socket is opened."""

    async def side_effect(method, url, data):
        query = parse_qs(url.query_string)
        command = query.get("command", [""])[0]
        value = query.get("value", [None])[0]
        status, ctype, body = fake.handle(command, value)
        return AiohttpClientMockResponse(
            method, url, status=status, response=body, headers={"Content-Type": ctype} if ctype else None
        )

    aioclient_mock.get(re.compile(r"^https://192\.0\.2\.1[01](:\d+)?/api"), side_effect=side_effect)
    return aioclient_mock


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain="adax_direct",
        unique_id=DEVICE_ID,
        title=NAME,
        data={"host": HOST, "token": TOKEN, "device_id": DEVICE_ID, "name": NAME},
        options={"rated_power_w": 1000},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def setup_entry(hass: HomeAssistant, mock_heater, config_entry: MockConfigEntry) -> MockConfigEntry:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


@pytest.fixture
def refresh(hass: HomeAssistant, config_entry: MockConfigEntry):
    """One poll right now (the entry's coordinator), then let the state machine settle."""

    async def _refresh() -> None:
        await config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    return _refresh
