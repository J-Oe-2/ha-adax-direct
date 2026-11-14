"""Polling coordinator for one Adax heater: failure debounce, duty-cycle model, energy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import AdaxDirectApi, AdaxDirectError
from .const import (
    CONF_DEVICE_ID,
    CONF_DUTY_BASE,
    CONF_DUTY_SLOPE,
    CONF_IDLE_OFFSET_K,
    CONF_NAME,
    CONF_RATED_POWER_W,
    CONF_SETTLE_MIN,
    DEFAULT_DUTY_BASE,
    DEFAULT_DUTY_SLOPE,
    DEFAULT_IDLE_OFFSET_K,
    DEFAULT_SETTLE_MIN,
    DOMAIN,
    ENERGY_DT_CAP_S,
    MAX_CONSECUTIVE_FAILURES,
    SCAN_INTERVAL,
    TARGET_OFF,
)

_LOGGER = logging.getLogger(__name__)

HEATING = "heating"
IDLE = "idle"
OFF = "off"

type AdaxDirectConfigEntry = ConfigEntry[AdaxDirectCoordinator]


@dataclass(frozen=True)
class HeaterData:
    """The last good poll, plus what is derived from it."""

    curr_c100: int
    targ_c100: int
    action: str                  # heating | idle | off  (inferred from the duty model)
    duty: float                  # modelled on-share 0..1 (0 when off)
    power_w: int                 # estimated: rated power x duty, whole W
    poll_time: datetime          # when this poll succeeded (UTC)
    raw: dict[str, Any]          # the full `stat` JSON as the heater sent it
    display_c100: int            # the published reading: raw, or raw + idle offset once settled
    offset_active: bool          # True when display_c100 carries the idle offset
    last_heated: datetime        # the last poll that saw heating (or the start / recovery assumption)


class AdaxDirectCoordinator(DataUpdateCoordinator[HeaterData]):
    """Owns the failure counter, the duty-model parameters and the running energy total."""

    def __init__(self, hass: HomeAssistant, entry: AdaxDirectConfigEntry, api: AdaxDirectApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.data[CONF_NAME]}",
            update_interval=SCAN_INTERVAL,
        )
        self.api = api
        self.device_name: str = entry.data[CONF_NAME]
        self.device_id: str = entry.data[CONF_DEVICE_ID]
        self.rated_power_w: int = int(entry.options.get(CONF_RATED_POWER_W, 1000))
        self.duty_base: float = float(entry.options.get(CONF_DUTY_BASE, DEFAULT_DUTY_BASE))
        self.duty_slope: float = float(entry.options.get(CONF_DUTY_SLOPE, DEFAULT_DUTY_SLOPE))
        self.idle_offset_c100: int = round(float(entry.options.get(CONF_IDLE_OFFSET_K, DEFAULT_IDLE_OFFSET_K)) * 100)
        self.settle: timedelta = timedelta(minutes=int(entry.options.get(CONF_SETTLE_MIN, DEFAULT_SETTLE_MIN)))
        self.last_heated: datetime | None = None   # in memory only; a (re)start assumes "heated just now"
        self.energy_kwh: float = 0.0           # running total; restored by the energy sensor
        self._failures = 0
        self._prev_poll: datetime | None = None
        self._prev_power_w = 0

    def _duty(self, curr: int, targ: int) -> float:
        """Time-proportional model: duty = clamp(base + slope x (target - room) in K, 0, 1); 0 when off."""
        if targ == TARGET_OFF:
            return 0.0
        return min(1.0, max(0.0, self.duty_base + self.duty_slope * (targ - curr) / 100))

    async def _async_update_data(self) -> HeaterData:
        try:
            raw = await self.api.async_stat()
        except AdaxDirectError as err:
            self._failures += 1
            _LOGGER.warning(
                "adax_direct %s: poll failure %d/%d (%s)",
                self.device_name, self._failures, MAX_CONSECUTIVE_FAILURES, err,
            )
            if self.data is None:
                raise UpdateFailed(f"no successful poll yet: {err}") from err
            if self._failures >= MAX_CONSECUTIVE_FAILURES:
                raise UpdateFailed(f"{self._failures} consecutive poll failures: {err}") from err
            return self.data                    # tolerated: last good data, no energy booked

        recovered = self._failures >= MAX_CONSECUTIVE_FAILURES   # the entities were unavailable
        self._failures = 0
        now = dt_util.utcnow()
        curr, targ = raw["currTemp"], raw["targTemp"]
        duty = self._duty(curr, targ)
        action = OFF if targ == TARGET_OFF else (HEATING if duty > 0 else IDLE)
        power_w = round(self.rated_power_w * duty)

        heating = duty > 0
        if self.last_heated is None or recovered or heating:
            self.last_heated = now
        offset_active = (
            self.idle_offset_c100 != 0
            and curr != 0                       # a raw 0 is a sensor fault: never offset
            and not heating
            and now - self.last_heated >= self.settle
        )
        display = curr + self.idle_offset_c100 if offset_active else curr
        if offset_active and display == 0:
            display = -1                        # never publish an exact 0 for a valid reading

        if self._prev_poll is not None:         # the first successful poll is a baseline only
            dt_s = min((now - self._prev_poll).total_seconds(), ENERGY_DT_CAP_S)
            self.energy_kwh += self._prev_power_w * dt_s / 3_600_000.0
        self._prev_poll, self._prev_power_w = now, power_w
        return HeaterData(
            curr, targ, action, duty, power_w, now, dict(raw), display, offset_active, self.last_heated
        )
