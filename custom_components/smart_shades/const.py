"""Constants for Smart Shade Scheduler."""

DOMAIN = "smart_shades"

# Top-level config / options keys
CONF_MODE_ENTITY = "mode_entity"
CONF_TOLERANCE = "tolerance"
CONF_DND_START = "dnd_start"
CONF_DND_END = "dnd_end"
CONF_WIPE_TIME = "wipe_time"
CONF_RULES = "rules"

# Rule dict keys
RULE_NAME = "name"
RULE_MODE = "mode"
RULE_COVERS = "covers"
RULE_AZIMUTH_ABOVE = "azimuth_above"
RULE_AZIMUTH_BELOW = "azimuth_below"
RULE_AZIMUTH_MIN = "azimuth_min"
RULE_AZIMUTH_MAX = "azimuth_max"
RULE_AZIMUTH_EQ = "azimuth_eq"
RULE_ELEVATION_ABOVE = "elevation_above"
RULE_ELEVATION_BELOW = "elevation_below"
RULE_ELEVATION_MIN = "elevation_min"
RULE_ELEVATION_MAX = "elevation_max"
RULE_ELEVATION_EQ = "elevation_eq"
RULE_HOUR_ABOVE = "hour_above"
RULE_HOUR_BELOW = "hour_below"
RULE_HOUR_MIN = "hour_min"
RULE_HOUR_MAX = "hour_max"
RULE_HOUR_EQ = "hour_eq"
RULE_MINUTE_ABOVE = "minute_above"
RULE_MINUTE_BELOW = "minute_below"
RULE_MINUTE_MIN = "minute_min"
RULE_MINUTE_MAX = "minute_max"
RULE_MINUTE_EQ = "minute_eq"
RULE_POSITION = "position"
RULE_TILT = "tilt"

# Optional helper entities that override manually-entered values
CONF_DND_ENTITY = "dnd_entity"           # binary_sensor: on = DND active
CONF_OVERRIDE_DURATION_ENTITY = "override_duration_entity"
CONF_PRESENCE_ENTITY = "presence_entity" # zone/binary_sensor/person/device_tracker

# Reserved mode keys — always present, never orphaned
PRIORITY_MODE = "_priority"
FALLBACK_MODE = "_fallback"
SPECIAL_MODES = {PRIORITY_MODE, FALLBACK_MODE}

# Defaults (time values as HH:MM:SS to match TimeSelector output)
DEFAULT_TOLERANCE = 5
DEFAULT_WIPE_TIME = "04:00:00"
DEFAULT_DND_START = "22:00:00"
DEFAULT_DND_END = "07:00:00"

# Behaviour
OVERRIDE_DURATION_HOURS = 4
SCAN_INTERVAL_MINUTES = 15
