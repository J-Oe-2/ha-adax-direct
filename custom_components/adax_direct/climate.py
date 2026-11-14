"""Climate entity of one Adax heater."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from .api import AdaxDirectError
from .const import DEFAULT_REMEMBERED_TARGET_C, TARGET_OFF
from .coordinator import HEATING, IDLE, AdaxDirectConfigEntry, AdaxDirectCoordinator
from .entity import AdaxDirectEntity

_ACTIONS = {HEATING: HVACAction.HEATING, IDLE: HVACAction.IDLE}


@dataclass
class RememberedTarget(ExtraStoredData):
    """The last non-zero target, kept across restarts."""

    value: float

    def as_dict(self) -> dict[str, Any]:
        return {"remembered_target": self.value}


async def async_setup_entry(
    hass: HomeAssistant, entry: AdaxDirectConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([AdaxDirectClimate(entry.runtime_data)])


class AdaxDirectClimate(AdaxDirectEntity, ClimateEntity, RestoreEntity):
    _attr_name = None
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
    )
    _attr_min_temp = 5
    _attr_max_temp = 35
    _attr_target_temperature_step = 1
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: AdaxDirectCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_climate"
        self._remembered_c = DEFAULT_REMEMBERED_TARGET_C
        self._note_target()

    def _note_target(self) -> None:
        """Remember the last non-zero target seen on a poll."""
        if self.coordinator.data and self.coordinator.data.targ_c100 > TARGET_OFF:
            self._remembered_c = self.coordinator.data.targ_c100 / 100

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_extra_data()) is not None:
            value = last.as_dict().get("remembered_target")
            if isinstance(value, (int, float)) and value > 0:
                self._remembered_c = float(value)
        self._note_target()          # a fresh poll wins over the restored value

    @property
    def extra_restore_state_data(self) -> RememberedTarget:
        return RememberedTarget(self._remembered_c)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._note_target()
        super()._handle_coordinator_update()

    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.OFF if self.coordinator.data.targ_c100 == TARGET_OFF else HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        return _ACTIONS.get(self.coordinator.data.action, HVACAction.OFF)

    @property
    def current_temperature(self) -> float:
        return self.coordinator.data.curr_c100 / 100

    @property
    def target_temperature(self) -> float | None:
        targ = self.coordinator.data.targ_c100
        return None if targ == TARGET_OFF else targ / 100

    async def _write(self, value_c100: int) -> None:
        try:
            await self.coordinator.api.async_set_target(value_c100)
        except AdaxDirectError as err:
            raise HomeAssistantError(f"{self.coordinator.device_name}: write failed ({err})") from err
        if value_c100 > TARGET_OFF:
            self._remembered_c = value_c100 / 100
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        await self._write(TARGET_OFF)

    async def async_turn_on(self) -> None:
        await self._write(round(self._remembered_c * 100))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        elif hvac_mode == HVACMode.HEAT:
            await self.async_turn_on()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """HA forwards `hvac_mode` here as a kwarg; one write only, never a transient low value."""
        if kwargs.get(ATTR_HVAC_MODE) == HVACMode.OFF:
            await self._write(TARGET_OFF)
        elif (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self._write(round(temperature * 100))
        elif kwargs.get(ATTR_HVAC_MODE) == HVACMode.HEAT:
            await self.async_turn_on()
