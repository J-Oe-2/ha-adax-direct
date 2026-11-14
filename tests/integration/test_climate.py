"""I-05, I-07 ... I-12, I-17: the climate entity and the write guard."""
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
)

from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.adax_direct.api import AdaxDirectApi
from tests.fake_heater import TOKEN
from tests.integration.conftest import CLIMATE, ENERGY, POWER, TEMPERATURE


async def call(hass: HomeAssistant, service: str, **data) -> None:
    await hass.services.async_call("climate", service, {"entity_id": CLIMATE, **data}, blocking=True)


async def test_initial_state(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    climate = hass.states.get(CLIMATE)
    assert climate.state == "heat"
    assert climate.attributes["temperature"] == 9.0
    assert climate.attributes["current_temperature"] == 16.3
    assert climate.attributes["hvac_action"] == "idle"
    temperature = hass.states.get(TEMPERATURE)
    assert temperature.state == "16.32"
    assert temperature.attributes["unit_of_measurement"] == "°C"
    power = hass.states.get(POWER)
    assert power.state == "0"
    assert power.attributes["duty"] == 0.0
    assert float(hass.states.get(ENERGY).state) == 0.0


async def test_turn_off(hass: HomeAssistant, setup_entry: MockConfigEntry, fake, refresh) -> None:
    await call(hass, "turn_off")
    await refresh()
    assert fake.log[-1] == 0
    climate = hass.states.get(CLIMATE)
    assert climate.state == "off"
    assert climate.attributes["temperature"] is None
    assert climate.attributes["hvac_action"] == "off"
    assert hass.states.get(TEMPERATURE).state == "16.32"


async def test_turn_on_remembered(hass: HomeAssistant, setup_entry: MockConfigEntry, fake, refresh) -> None:
    await call(hass, "turn_off")
    await refresh()
    assert hass.states.get(CLIMATE).state == "off"
    await call(hass, "turn_on")
    await refresh()
    assert fake.log[-1] == 900
    assert hass.states.get(CLIMATE).state == "heat"


async def test_set_temperature_with_heat_from_off(hass: HomeAssistant, mock_heater, config_entry, fake, refresh) -> None:
    fake.targTemp = 0
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await refresh()
    fake.log.clear()
    await call(hass, "set_temperature", temperature=16, hvac_mode="heat")
    await refresh()
    assert fake.log == [1600]
    climate = hass.states.get(CLIMATE)
    assert climate.state == "heat"
    assert climate.attributes["temperature"] == 16.0


async def test_set_temperature_with_off(hass: HomeAssistant, setup_entry: MockConfigEntry, fake, refresh) -> None:
    fake.log.clear()
    await call(hass, "set_temperature", temperature=16, hvac_mode="off")
    await refresh()
    assert fake.log == [0]
    assert hass.states.get(CLIMATE).state == "off"


async def test_set_temperature_below_min_rejected(hass: HomeAssistant, setup_entry: MockConfigEntry, fake) -> None:
    fake.log.clear()
    with pytest.raises(HomeAssistantError):
        await call(hass, "set_temperature", temperature=4)
    assert fake.log == []


async def test_write_guard(hass: HomeAssistant, mock_heater, fake) -> None:
    api = AdaxDirectApi(async_get_clientsession(hass), "192.0.2.10", TOKEN)
    for bad in (450, 499, 3501, -100, 1):
        calls_before = mock_heater.call_count
        with pytest.raises(ValueError):
            await api.async_set_target(bad)
        assert mock_heater.call_count == calls_before
    for good in (0, 500, 3500):
        await api.async_set_target(good)
    assert fake.log == [0, 500, 3500]


async def test_remembered_target_restored(hass: HomeAssistant, mock_heater, config_entry, fake) -> None:
    fake.targTemp = 0
    mock_restore_cache_with_extra_data(
        hass, [(State(CLIMATE, "off"), {"remembered_target": 18.0})]
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await call(hass, "turn_on")
    assert fake.log[-1] == 1800
