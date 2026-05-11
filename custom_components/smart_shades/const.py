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
RULE_POSITION = "position"
RULE_TILT = "tilt"

# Optional helper entities that override manually-entered values
CONF_DND_ENTITY = "dnd_entity"           # binary_sensor: on = DND active
CONF_OVERRIDE_DURATION_ENTITY = "override_duration_entity"
CONF_MODE_CONFIG     = "mode_config"     # dict: mode → {block_fallback, force}

# Built-in condition variables.
# To add a new one: append an entry here — nothing else needs changing.
#   ha_entity : HA entity_id to read, or None for synthetic vars
#   ha_attr   : attribute name on the entity, or sentinel for synthetic vars:
#               "time"  → current HHMM integer
#               "month" → current month integer
BUILT_IN_VARS = [
    {"short": "az", "long": "azimuth",   "type": "number", "ha_entity": "sun.sun", "ha_attr": "azimuth"},
    {"short": "el", "long": "elevation", "type": "number", "ha_entity": "sun.sun", "ha_attr": "elevation"},
    {"short": "t",  "long": "time",      "type": "time",   "ha_entity": None,      "ha_attr": "time"},
    {"short": "mo", "long": "month",     "type": "number", "ha_entity": None,      "ha_attr": "month"},
    {"short": "d",  "long": "day",       "type": "number", "ha_entity": None,      "ha_attr": "weekday"},
]
CONF_CUSTOM_VARS     = "custom_vars"     # str: multiline "name=entity_id" or "name={{template}}"

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
CONF_OVERRIDE_DURATION = "override_duration"   # seconds, stored in options
DEFAULT_OVERRIDE_DURATION = 2                  # seconds
SCAN_INTERVAL_MINUTES = 15
