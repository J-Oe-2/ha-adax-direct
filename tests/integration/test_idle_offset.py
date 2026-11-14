"""I-25 ... I-33: the idle-offset correction (options, settle time, raw passthrough, restart and recovery)."""
from datetime import timedelta

import pytest
import voluptuous as vol
from pytest_homeassistant_custom_component.common import MockConfigEntry, mock_restore_cache

from homeassistant.core import HomeAssistant, State
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util

from tests.fake_heater import TOKEN
from tests.integration.conftest import CLIMATE, ENERGY, HOST, POWER, TEMPERATURE


async def start(hass: HomeAssistant, entry: MockConfigEntry, **options) -> None:
    hass.config_entries.async_update_entry(entry, options={"rated_power_w": 1000, **options})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def attrs(hass: HomeAssistant) -> dict:
    return hass.states.get(TEMPERATURE).attributes


async def test_default_offset_settling(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """I-25: an entry without the options is inside its settle time right after the start."""
    state = hass.states.get(TEMPERATURE)
    assert state.state == "16.32"
    assert state.attributes["raw_temperature"] == 16.32
    assert state.attributes["idle_offset_active"] is False
    assert state.attributes["last_heated"] == hass.states.get(ENERGY).attributes["last_poll"]


async def test_offset_after_settle(
    hass: HomeAssistant, freezer, mock_heater, config_entry: MockConfigEntry, fake, refresh
) -> None:
    """I-26"""
    fake.currTemp, fake.targTemp = 1500, 0
    t0 = dt_util.utcnow()
    await start(hass, config_entry, idle_offset_k=1.6, settle_min=45)
    assert hass.states.get(TEMPERATURE).state == "15.0"
    assert attrs(hass)["idle_offset_active"] is False
    assert attrs(hass)["last_heated"] == t0.isoformat()
    freezer.tick(timedelta(minutes=44))
    await refresh()
    assert hass.states.get(TEMPERATURE).state == "15.0"
    assert attrs(hass)["idle_offset_active"] is False
    freezer.tick(timedelta(minutes=1))
    await refresh()
    assert hass.states.get(TEMPERATURE).state == "16.6"
    assert attrs(hass)["idle_offset_active"] is True
    assert attrs(hass)["raw_temperature"] == 15.0
    assert hass.states.get(CLIMATE).attributes["current_temperature"] == 16.6


async def settled(hass, freezer, mock_heater, config_entry, fake, refresh, **options) -> None:
    fake.currTemp, fake.targTemp = 1500, 0
    await start(hass, config_entry, **(options or {"idle_offset_k": 1.6, "settle_min": 45}))
    freezer.tick(timedelta(minutes=45))
    await refresh()
    assert attrs(hass)["idle_offset_active"] is True


async def test_heating_suspends_offset(
    hass: HomeAssistant, freezer, mock_heater, config_entry: MockConfigEntry, fake, refresh
) -> None:
    """I-27"""
    await settled(hass, freezer, mock_heater, config_entry, fake, refresh)
    fake.targTemp = 2000
    await refresh()
    assert hass.states.get(TEMPERATURE).state == "15.0"
    assert attrs(hass)["idle_offset_active"] is False
    assert hass.states.get(CLIMATE).attributes["hvac_action"] == "heating"
    fake.targTemp = 0
    freezer.tick(timedelta(minutes=30))
    await refresh()
    assert hass.states.get(TEMPERATURE).state == "15.0"
    assert attrs(hass)["idle_offset_active"] is False
    freezer.tick(timedelta(minutes=15))
    await refresh()
    assert hass.states.get(TEMPERATURE).state == "16.6"
    assert attrs(hass)["idle_offset_active"] is True


async def test_raw_zero_passthrough(
    hass: HomeAssistant, mock_heater, config_entry: MockConfigEntry, fake
) -> None:
    """I-28: a raw 0.0 is a sensor fault and is never offset."""
    fake.currTemp, fake.targTemp = 0, 0
    await start(hass, config_entry, idle_offset_k=1.6, settle_min=0)
    assert hass.states.get(TEMPERATURE).state == "0.0"
    assert attrs(hass)["raw_temperature"] == 0.0
    assert attrs(hass)["idle_offset_active"] is False


async def test_corrected_zero_guard(
    hass: HomeAssistant, mock_heater, config_entry: MockConfigEntry, fake
) -> None:
    """I-29: raw + offset = 0.00 is published as -0.01, never as an exact 0."""
    fake.currTemp, fake.targTemp = -160, 0
    await start(hass, config_entry, idle_offset_k=1.6, settle_min=0)
    assert hass.states.get(TEMPERATURE).state == "-0.01"
    assert attrs(hass)["idle_offset_active"] is True


async def test_duty_uses_raw(
    hass: HomeAssistant, mock_heater, config_entry: MockConfigEntry, fake
) -> None:
    """I-30: duty, power and hvac_action come from the raw reading."""
    fake.currTemp, fake.targTemp = 2080, 2000
    await start(hass, config_entry, idle_offset_k=-1.0, settle_min=0)
    assert hass.states.get(POWER).state == "0"
    assert hass.states.get(POWER).attributes["duty"] == 0.0
    assert hass.states.get(CLIMATE).attributes["hvac_action"] == "idle"
    assert hass.states.get(TEMPERATURE).state == "19.8"
    assert attrs(hass)["raw_temperature"] == 20.8
    assert attrs(hass)["idle_offset_active"] is True


async def test_reload_and_restart_assume_heated(
    hass: HomeAssistant, freezer, mock_heater, config_entry: MockConfigEntry, fake, refresh
) -> None:
    """I-31 (a): an options change reloads the entry and the settle time starts again."""
    await settled(hass, freezer, mock_heater, config_entry, fake, refresh)
    hass.config_entries.async_update_entry(config_entry, options={"rated_power_w": 1000, "idle_offset_k": 1.5, "settle_min": 45})
    await hass.async_block_till_done()
    await refresh()
    assert hass.states.get(TEMPERATURE).state == "15.0"
    assert attrs(hass)["idle_offset_active"] is False
    freezer.tick(timedelta(minutes=45))
    await refresh()
    assert hass.states.get(TEMPERATURE).state == "16.5"
    assert attrs(hass)["idle_offset_active"] is True


async def test_restart_restores_nothing(
    hass: HomeAssistant, freezer, mock_heater, config_entry: MockConfigEntry, fake
) -> None:
    """I-31 (b): a settled state in the restore cache is ignored; the anchor is the setup time."""
    mock_restore_cache(
        hass,
        [State(TEMPERATURE, "16.6", {"idle_offset_active": True, "last_heated": "2026-01-01T00:00:00+00:00"})],
    )
    fake.currTemp, fake.targTemp = 1500, 0
    setup_time = dt_util.utcnow()
    await start(hass, config_entry, idle_offset_k=1.6, settle_min=45)
    assert hass.states.get(TEMPERATURE).state == "15.0"
    assert attrs(hass)["idle_offset_active"] is False
    assert attrs(hass)["last_heated"] == setup_time.isoformat()


async def test_recovery_resets_settle(
    hass: HomeAssistant, freezer, mock_heater, config_entry: MockConfigEntry, fake, refresh
) -> None:
    """I-32: coming back from unavailable starts the settle time again."""
    await settled(hass, freezer, mock_heater, config_entry, fake, refresh)
    fake.mode = "timeout"
    for _ in range(4):
        await refresh()
    assert hass.states.get(TEMPERATURE).state == "16.6"
    await refresh()
    assert hass.states.get(TEMPERATURE).state == "unavailable"
    fake.mode = "ok"
    await refresh()
    assert hass.states.get(TEMPERATURE).state == "15.0"
    assert attrs(hass)["idle_offset_active"] is False
    freezer.tick(timedelta(minutes=45))
    await refresh()
    assert hass.states.get(TEMPERATURE).state == "16.6"
    assert attrs(hass)["idle_offset_active"] is True


async def options_input(hass: HomeAssistant, entry: MockConfigEntry, **extra):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"host": HOST, "token": TOKEN, "rated_power_w": 1000, "duty_base": 0.23, "duty_slope": 0.3, **extra},
    )


async def test_options_flow_offset_fields(hass: HomeAssistant, mock_heater, setup_entry: MockConfigEntry) -> None:
    """I-33: the two fields are stored, range-checked by the schema, and the boundaries are accepted."""
    entry = setup_entry
    result = await options_input(hass, entry, idle_offset_k=1.6, settle_min=45)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    expected = {"rated_power_w": 1000, "duty_base": 0.23, "duty_slope": 0.3, "idle_offset_k": 1.6, "settle_min": 45}
    assert entry.options == expected
    for bad in ({"idle_offset_k": -5.1}, {"idle_offset_k": 5.1}, {"settle_min": -1}, {"settle_min": 181}):
        with pytest.raises(vol.Invalid):
            await options_input(hass, entry, **{"idle_offset_k": 1.6, "settle_min": 45, **bad})
        assert entry.options == expected
    for good in ({"idle_offset_k": -5.0}, {"idle_offset_k": 5.0}, {"settle_min": 0}, {"settle_min": 180}):
        values = {"idle_offset_k": 1.6, "settle_min": 45, **good}
        result = await options_input(hass, entry, **values)
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options == {**expected, **values}
