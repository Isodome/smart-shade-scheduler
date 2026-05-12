"""Constants for Smart Shade Scheduler."""

DOMAIN = "smart_shades"

# Top-level config / options keys
CONF_MODE_ENTITY = "mode_entity"
CONF_TOLERANCE = "tolerance"
CONF_DND_START = "dnd_start"
CONF_DND_END = "dnd_end"
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
# To add a new one: append an entry here with a resolver(hass, now) -> float | None.
from functools import partial

def _entity_attr(entity, attr, hass, now):
    s = hass.states.get(entity)
    if s is None: return None
    try: return float(s.attributes.get(attr, 0))
    except (ValueError, TypeError): return None

def _now_hhmm(hass, now):  return float(now.hour * 100 + now.minute)
def _now_month(hass, now):  return float(now.month)
def _now_weekday(hass, now): return float(now.weekday())

BUILT_IN_VARS = [
    {"short": "az", "long": "azimuth",   "type": "number", "resolver": partial(_entity_attr, "sun.sun", "azimuth")},
    {"short": "el", "long": "elevation", "type": "number", "resolver": partial(_entity_attr, "sun.sun", "elevation")},
    {"short": "t",  "long": "time",      "type": "time",   "resolver": _now_hhmm},
    {"short": "mo", "long": "month",     "type": "number", "resolver": _now_month},
    {"short": "d",  "long": "day",       "type": "number", "resolver": _now_weekday},
]
CONF_CUSTOM_VARS     = "custom_vars"     # str: multiline "name=entity_id" or "name={{template}}"
CONF_TILT_DELAY      = "tilt_delay"     # seconds to wait between position and tilt commands
DEFAULT_TILT_DELAY   = 30

# Reserved mode keys — always present, never orphaned
PRIORITY_MODE = "_priority"
FALLBACK_MODE = "_fallback"
SPECIAL_MODES = {PRIORITY_MODE, FALLBACK_MODE}

# Defaults (time values as HH:MM:SS to match TimeSelector output)
DEFAULT_TOLERANCE = 5
DEFAULT_DND_START = "22:00:00"
DEFAULT_DND_END = "07:00:00"

# Behaviour
CONF_OVERRIDE_DURATION = "override_duration"   # seconds, stored in options
DEFAULT_OVERRIDE_DURATION = 2                  # seconds
SCAN_INTERVAL_MINUTES = 15
