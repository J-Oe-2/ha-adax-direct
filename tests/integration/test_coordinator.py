"""I-13 ... I-16: failure debounce, duty model, energy accumulation and restore."""
from datetime import timedelta

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
)

from homeassistant.core import HomeAssistant, State

from tests.integration.conftest import CLIMATE, ENERGY, MAIN_ENTITIES, POWER


@pytest.mark.parametrize("mode", ["timeout", "http500", "garbage"])
async def test_unavailable_after_five_failures(
    hass: HomeAssistant, setup_entry: MockConfigEntry, fake, refresh, caplog, mode: str
) -> None:
    before = {entity: hass.states.get(entity).state for entity in MAIN_ENTITIES}
    assert before[CLIMATE] == "heat"
    fake.mode = mode
    for attempt in range(1, 5):
        await refresh()
        for entity in MAIN_ENTITIES:
            assert hass.states.get(entity).state == before[entity], (attempt, entity)
    assert "poll failure 4/5" in caplog.text
    await refresh()
    for entity in MAIN_ENTITIES:
        assert hass.states.get(entity).state == "unavailable", entity
    fake.mode = "ok"
    await refresh()
    assert hass.states.get(CLIMATE).state == "heat"


async def test_duty_model(hass: HomeAssistant, mock_heater, config_entry: MockConfigEntry, fake, refresh) -> None:
    hass.config_entries.async_update_entry(
        config_entry, options={"rated_power_w": 1000, "duty_base": 0.26, "duty_slope": 0.34}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    cases = [
        (2000, 2000, "260", 0.26, "heating"),
        (1900, 2000, "600", 0.6, "heating"),
        (1700, 2000, "1000", 1.0, "heating"),
        (2100, 2000, "0", 0.0, "idle"),
        (1900, 0, "0", 0.0, "off"),
    ]
    for curr, targ, power, duty, action in cases:
        fake.currTemp, fake.targTemp = curr, targ
        await refresh()
        assert hass.states.get(POWER).state == power, (curr, targ)
        assert hass.states.get(POWER).attributes["duty"] == duty, (curr, targ)
        assert hass.states.get(CLIMATE).attributes["hvac_action"] == action, (curr, targ)

    hass.config_entries.async_update_entry(
        config_entry, options={"rated_power_w": 1000, "duty_base": 0.5, "duty_slope": 0.25}
    )
    await hass.async_block_till_done()
    fake.currTemp, fake.targTemp = 1900, 2000
    await refresh()
    assert hass.states.get(POWER).state == "750"
    assert hass.states.get(POWER).attributes["duty"] == 0.75
    assert hass.states.get(CLIMATE).attributes["hvac_action"] == "heating"


async def test_energy_accumulation(
    hass: HomeAssistant, freezer, mock_heater, config_entry: MockConfigEntry, fake, refresh
) -> None:
    fake.currTemp, fake.targTemp = 1632, 2000          # duty 1 -> 1000 W
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    def energy() -> float:
        return float(hass.states.get(ENERGY).state)

    for _ in range(4):
        freezer.tick(timedelta(seconds=60))
        await refresh()
    assert energy() == pytest.approx(0.066667, abs=1e-6)
    freezer.tick(timedelta(seconds=600))
    await refresh()
    assert energy() == pytest.approx(0.116667, abs=1e-6)         # dt capped at 180 s
    fake.mode = "http500"
    freezer.tick(timedelta(seconds=60))
    await refresh()
    assert energy() == pytest.approx(0.116667, abs=1e-6)         # nothing booked
    fake.mode = "ok"
    freezer.tick(timedelta(seconds=60))
    await refresh()
    assert energy() == pytest.approx(0.15, abs=1e-6)             # 120 s booked


async def test_energy_restored(
    hass: HomeAssistant, freezer, mock_heater, config_entry: MockConfigEntry, fake, refresh
) -> None:
    fake.currTemp, fake.targTemp = 1632, 2000
    mock_restore_cache_with_extra_data(
        hass,
        [(State(ENERGY, "1.5"), {"native_value": 1.5, "native_unit_of_measurement": "kWh"})],
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert float(hass.states.get(ENERGY).state) == pytest.approx(1.5, abs=1e-6)
    freezer.tick(timedelta(seconds=60))
    await refresh()
    assert float(hass.states.get(ENERGY).state) == pytest.approx(1.516667, abs=1e-6)
