"""Config and options flow: IP + token, validated by one `stat` GET."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import AdaxDirectApi, AdaxDirectError
from .const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_DUTY_BASE,
    CONF_DUTY_SLOPE,
    CONF_IDLE_OFFSET_K,
    CONF_NAME,
    CONF_RATED_POWER_W,
    CONF_SETTLE_MIN,
    CONF_TOKEN,
    DEFAULT_DUTY_BASE,
    DEFAULT_DUTY_SLOPE,
    DEFAULT_IDLE_OFFSET_K,
    DEFAULT_SETTLE_MIN,
    DOMAIN,
    MAX_DUTY_SLOPE,
    MAX_IDLE_OFFSET_K,
    MAX_RATED_POWER_W,
    MAX_SETTLE_MIN,
    MIN_IDLE_OFFSET_K,
    MIN_RATED_POWER_W,
)

_TOKEN = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
_POWER = vol.All(vol.Coerce(int), vol.Range(min=MIN_RATED_POWER_W, max=MAX_RATED_POWER_W))
_DUTY_BASE = vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0))
_DUTY_SLOPE = vol.All(vol.Coerce(float), vol.Range(min=0.0, max=MAX_DUTY_SLOPE))
_IDLE_OFFSET = vol.All(vol.Coerce(float), vol.Range(min=MIN_IDLE_OFFSET_K, max=MAX_IDLE_OFFSET_K))
_SETTLE = vol.All(vol.Coerce(int), vol.Range(min=0, max=MAX_SETTLE_MIN))


async def _can_connect(hass: Any, host: str, token: str) -> bool:
    api = AdaxDirectApi(async_get_clientsession(hass, verify_ssl=False), host, token)
    try:
        await api.async_stat()
    except AdaxDirectError:
        return False
    return True


class AdaxDirectConfigFlow(ConfigFlow, domain=DOMAIN):
    """One config entry per heater."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
            self._abort_if_unique_id_configured()
            if await _can_connect(self.hass, user_input[CONF_HOST], user_input[CONF_TOKEN]):
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={k: user_input[k] for k in (CONF_HOST, CONF_TOKEN, CONF_DEVICE_ID, CONF_NAME)},
                    options={CONF_RATED_POWER_W: user_input[CONF_RATED_POWER_W]},
                )
            errors["base"] = "cannot_connect"
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_TOKEN): _TOKEN,
                vol.Required(CONF_DEVICE_ID): str,
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_RATED_POWER_W, default=1000): _POWER,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=self.add_suggested_values_to_schema(schema, user_input), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AdaxDirectOptionsFlow()


class AdaxDirectOptionsFlow(OptionsFlow):
    """Host, token, rated power, the two duty-model parameters, the idle offset and its settle time; the entry reloads afterwards."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self.config_entry
        errors: dict[str, str] = {}
        if user_input is not None:
            if await _can_connect(self.hass, user_input[CONF_HOST], user_input[CONF_TOKEN]):
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_HOST: user_input[CONF_HOST], CONF_TOKEN: user_input[CONF_TOKEN]}
                )
                return self.async_create_entry(
                    data={
                        CONF_RATED_POWER_W: user_input[CONF_RATED_POWER_W],
                        CONF_DUTY_BASE: user_input[CONF_DUTY_BASE],
                        CONF_DUTY_SLOPE: user_input[CONF_DUTY_SLOPE],
                        CONF_IDLE_OFFSET_K: user_input[CONF_IDLE_OFFSET_K],
                        CONF_SETTLE_MIN: user_input[CONF_SETTLE_MIN],
                    }
                )
            errors["base"] = "cannot_connect"
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_TOKEN): _TOKEN,
                vol.Required(CONF_RATED_POWER_W): _POWER,
                vol.Required(CONF_DUTY_BASE, default=DEFAULT_DUTY_BASE): _DUTY_BASE,
                vol.Required(CONF_DUTY_SLOPE, default=DEFAULT_DUTY_SLOPE): _DUTY_SLOPE,
                vol.Required(CONF_IDLE_OFFSET_K, default=DEFAULT_IDLE_OFFSET_K): _IDLE_OFFSET,
                vol.Required(CONF_SETTLE_MIN, default=DEFAULT_SETTLE_MIN): _SETTLE,
            }
        )
        current = user_input or {
            CONF_HOST: entry.data[CONF_HOST],
            CONF_RATED_POWER_W: entry.options.get(CONF_RATED_POWER_W, 1000),
            CONF_DUTY_BASE: entry.options.get(CONF_DUTY_BASE, DEFAULT_DUTY_BASE),
            CONF_DUTY_SLOPE: entry.options.get(CONF_DUTY_SLOPE, DEFAULT_DUTY_SLOPE),
            CONF_IDLE_OFFSET_K: entry.options.get(CONF_IDLE_OFFSET_K, DEFAULT_IDLE_OFFSET_K),
            CONF_SETTLE_MIN: entry.options.get(CONF_SETTLE_MIN, DEFAULT_SETTLE_MIN),
        }
        return self.async_show_form(
            step_id="init", data_schema=self.add_suggested_values_to_schema(schema, current), errors=errors
        )
