"""Constants for Smart Shade Scheduler."""

DOMAIN = "smart_shades"

# Top-level config / options keys
CONF_MODE_ENTITY = "mode_entity"
CONF_TOLERANCE = "tolerance"
CONF_RULES = "rules"

# Rule dict keys
RULE_NAME = "name"
RULE_MODE = "mode"
RULE_COVERS = "covers"
RULE_POSITION = "position"
RULE_TILT = "tilt"

# Optional helper entities that override manually-entered values
CONF_ARMED_ENTITY = "armed_entity"       # binary_sensor: on = automation armed
CONF_OVERRIDE_DURATION_ENTITY = "override_duration_entity"
CONF_MODE_CONFIG     = "mode_config"     # dict: mode → {block_fallback, force}
CONF_TRANSIT_GRACE   = "transit_grace"   # int: seconds to wait before checking override

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
CONF_TILT_DELAY      = "tilt_delay"      # seconds to wait between position and tilt commands
DEFAULT_TILT_DELAY   = 60               # Typical vertical shades take ~60s to close before tilt is reliable

# Reserved mode keys — always present, never orphaned
PRIORITY_MODE = "_priority"
FALLBACK_MODE = "_fallback"
SPECIAL_MODES = {PRIORITY_MODE, FALLBACK_MODE}

# Defaults
DEFAULT_TOLERANCE = 5

# Behaviour
CONF_OVERRIDE_DURATION = "override_duration"   # minutes, stored in options
DEFAULT_OVERRIDE_DURATION = 120                # minutes (2 hours)
DEFAULT_TRANSIT_GRACE     = 90                 # seconds
SCAN_INTERVAL_MINUTES = 15
EVALUATION_LOW_PRIO_COOLDOWN = 240             # seconds (4 minutes)
