"""Constants for the adax_direct integration."""

from datetime import timedelta

DOMAIN = "adax_direct"

CONF_HOST = "host"
CONF_TOKEN = "token"
CONF_DEVICE_ID = "device_id"
CONF_NAME = "name"
CONF_RATED_POWER_W = "rated_power_w"
CONF_DUTY_BASE = "duty_base"
CONF_DUTY_SLOPE = "duty_slope"

# Duty-cycle model: default curve fitted on a plug-measured Adax Clea H 12 KWT (adax-direct fit)
DEFAULT_DUTY_BASE = 0.23
DEFAULT_DUTY_SLOPE = 0.30               # per K of (target - room)
MAX_DUTY_SLOPE = 5.0
MIN_RATED_POWER_W = 100
MAX_RATED_POWER_W = 3000

SCAN_INTERVAL = timedelta(seconds=60)
REQUEST_TIMEOUT_S = 10
MAX_CONSECUTIVE_FAILURES = 5          # the 5th failed poll in a row makes the entities unavailable
ENERGY_DT_CAP_S = 180                 # one poll interval never books more than this

# The heater stores 0 (= off) or 5.00..35.00 degC in 1/100 degC; anything else is refused by api.py.
TARGET_OFF = 0
TARGET_MIN = 500
TARGET_MAX = 3500
DEFAULT_REMEMBERED_TARGET_C = 5.0
