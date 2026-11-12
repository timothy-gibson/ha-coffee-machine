"""Constants for the Coffee Machine integration."""

DOMAIN = "coffee_machine"
# The integration version lives only in manifest.json.

CONF_SWITCH = "switch_entity"
CONF_POWER = "power_entity"
CONF_THRESHOLD = "threshold"
CONF_SLEEP_TIMEOUT = "sleep_timeout"
CONF_WAKE_OFF = "wake_off_seconds"
CONF_MIN_HEATING = "min_heating_seconds"
CONF_ACTIVITY_WINDOW = "activity_window_seconds"

DEFAULT_NAME = "Coffee Machine"
DEFAULT_THRESHOLD = 1.0  # in the units of the chosen sensor (A or W)
DEFAULT_SLEEP_TIMEOUT = 30  # minutes, counted from last heating or use
DEFAULT_WAKE_OFF = 3  # seconds the plug stays off when waking
# High current shorter than this is a thermostat top-up, not real heating.
DEFAULT_MIN_HEATING = 90  # seconds
# Short bursts starting within this long of the previous activity are use of
# the machine (shots, steaming) and restart the sleep countdown.
DEFAULT_ACTIVITY_WINDOW = 120  # seconds

# After the plug is switched on, how long to wait for the heater to start
# drawing current before deciding the machine is asleep.
WAKE_GRACE_SECONDS = 45

# Extra time allowed for a slow sensor before a steady high reading is confirmed
# as heating without a fresh state update.
TOPUP_CHECK_GRACE_SECONDS = 45

CARD_FILENAME = "coffee-machine-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILENAME}"
