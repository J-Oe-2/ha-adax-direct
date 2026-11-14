"""I-01 ... I-04, I-18, I-19: the config flow and the options flow."""
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from tests.fake_heater import TOKEN
from tests.integration.conftest import DEVICE_ID, HOST, NAME

USER_INPUT = {"host": HOST, "token": TOKEN, "device_id": DEVICE_ID, "name": NAME, "rated_power_w": 1000}


async def start_flow(hass: HomeAssistant, user_input: dict = USER_INPUT):
    result = await hass.config_entries.flow.async_init("adax_direct", context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input)


async def test_user_flow_creates_entry(hass: HomeAssistant, mock_heater) -> None:
    with patch("custom_components.adax_direct.async_setup_entry", return_value=True):
        result = await start_flow(hass)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Heater"
    assert result["data"] == {"host": HOST, "token": TOKEN, "device_id": DEVICE_ID, "name": NAME}
    assert result["options"] == {"rated_power_w": 1000}


async def test_user_flow_already_configured(hass: HomeAssistant, mock_heater, config_entry) -> None:
    result = await start_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_heater.call_count == 0


async def test_user_flow_cannot_connect_http500(hass: HomeAssistant, mock_heater, fake) -> None:
    fake.mode = "http500"
    result = await start_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert hass.config_entries.async_entries("adax_direct") == []


async def test_user_flow_cannot_connect_timeout(hass: HomeAssistant, mock_heater, fake) -> None:
    fake.mode = "timeout"
    result = await start_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert hass.config_entries.async_entries("adax_direct") == []


async def test_options_flow_changes_host(hass: HomeAssistant, mock_heater, setup_entry: MockConfigEntry) -> None:
    entry = setup_entry
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"host": "192.0.2.11", "token": TOKEN, "rated_power_w": 1200, "duty_base": 0.2, "duty_slope": 0.4},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data["host"] == "192.0.2.11"
    assert entry.options == {"rated_power_w": 1200, "duty_base": 0.2, "duty_slope": 0.4,
                             "idle_offset_k": 1.5, "settle_min": 45}
    registry = er.async_get(hass)
    unique_ids = {e.unique_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)}
    assert unique_ids == {
        f"{DEVICE_ID}_{kind}" for kind in ("climate", "temperature", "power", "energy", "reported_pow", "reported_energ")
    }
    assert mock_heater.mock_calls[-1][1].host == "192.0.2.11"


async def test_options_flow_cannot_connect(hass: HomeAssistant, mock_heater, setup_entry: MockConfigEntry, fake) -> None:
    entry = setup_entry
    data_before, options_before = dict(entry.data), dict(entry.options)
    fake.mode = "http500"
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"host": "192.0.2.11", "token": TOKEN, "rated_power_w": 1200, "duty_base": 0.2, "duty_slope": 0.4},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert dict(entry.data) == data_before
    assert dict(entry.options) == options_before
