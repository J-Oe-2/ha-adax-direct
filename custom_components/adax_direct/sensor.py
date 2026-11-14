"""Sensors of one Adax heater: temperature, estimated power and energy, raw diagnostics."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfEnergy, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AdaxDirectConfigEntry, AdaxDirectCoordinator
from .entity import AdaxDirectEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: AdaxDirectConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        AdaxTemperature(coordinator),
        AdaxPower(coordinator),
        AdaxEnergy(coordinator),
    ]
    # the raw fields are only exposed if this heater model sends them (first successful stat)
    for key in ("pow", "energ"):
        if key in coordinator.data.raw:
            entities.append(AdaxReported(coordinator, key))
    async_add_entities(entities)


class AdaxTemperature(AdaxDirectEntity, SensorEntity):
    _attr_name = "Temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: AdaxDirectCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_temperature"

    @property
    def native_value(self) -> float:
        return self.coordinator.data.curr_c100 / 100


class AdaxPower(AdaxDirectEntity, SensorEntity):
    """Estimated: rated power x modelled duty (time-proportional control), else 0."""

    _attr_name = "Power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator: AdaxDirectCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_power"

    @property
    def native_value(self) -> int:
        return self.coordinator.data.power_w

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"duty": round(self.coordinator.data.duty, 3)}


class AdaxEnergy(AdaxDirectEntity, RestoreSensor):
    """Running total of the estimated power x time; the accumulation lives in the coordinator."""

    _attr_name = "Energy"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator: AdaxDirectCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_energy"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_sensor_data()
        if last is not None and isinstance(last.native_value, (int, float)):
            self.coordinator.energy_kwh = max(self.coordinator.energy_kwh, float(last.native_value))

    @property
    def native_value(self) -> float:
        return round(self.coordinator.energy_kwh, 6)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"last_poll": self.coordinator.data.poll_time.isoformat()}


class AdaxReported(AdaxDirectEntity, SensorEntity):
    """The raw `pow` / `energ` the heater reports (0 on every controller tested); disabled by default."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AdaxDirectCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"Reported {key}"
        self._attr_unique_id = f"{coordinator.device_id}_reported_{key}"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.raw.get(self._key)
