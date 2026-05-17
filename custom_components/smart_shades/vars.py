"""Variable resolution — built-ins and custom bindings share a unified spec shape."""

import re as _re
from datetime import datetime

from homeassistant.util import dt as dt_util

_RE_HHMM = _re.compile(r"^(\d{1,2}):(\d{2})")

# ---------------------------------------------------------------------------
# State coercion
# ---------------------------------------------------------------------------

def _coerce_state(state_str: str) -> float | None:
    """Coerce an entity state string to float for use as a condition variable."""
    state_str = state_str.strip()
    try:
        return float(state_str)
    except (ValueError, TypeError):
        pass
    low = state_str.lower()
    if low in ("on",  "true",  "yes"): return 1.0
    if low in ("off", "false", "no"):  return 0.0
    m = _RE_HHMM.match(state_str)
    if m:
        return float(int(m.group(1)) * 100 + int(m.group(2)))
    if len(state_str) < 10:
        return None
    try:
        dt = datetime.fromisoformat(state_str)
        if dt.tzinfo is not None:
            dt = dt_util.as_local(dt)
        return float(dt.hour * 100 + dt.minute)
    except (ValueError, TypeError, AttributeError):
        pass
    return None


# ---------------------------------------------------------------------------
# Type inference
# ---------------------------------------------------------------------------

def _infer_type_from_value(raw: str | None) -> str:
    """Infer "bool", "time", or "number" from a rendered template string."""
    if raw is None:
        return "number"
    raw = raw.strip()
    low = raw.lower()
    if low in ("on", "off", "true", "false", "yes", "no"):
        return "bool"
    if _RE_HHMM.match(raw):
        return "time"
    if len(raw) >= 10:
        try:
            datetime.fromisoformat(raw)
            return "time"
        except (ValueError, TypeError):
            pass
    return "number"


def _infer_type_from_entity(hass, entity_id: str) -> str:
    """Infer "bool", "time", or "number" from entity domain and device_class."""
    domain = entity_id.split(".")[0]
    if domain in ("binary_sensor", "input_boolean", "switch", "device_tracker"):
        return "bool"
    if domain == "sensor":
        state = hass.states.get(entity_id)
        if state and state.attributes.get("device_class") in ("timestamp", "date"):
            return "time"
    return "number"


# ---------------------------------------------------------------------------
# Unified spec shape: {resolver(hass, now) -> (float|None, str)}
# resolver returns (value, type) together.
# ---------------------------------------------------------------------------

def _wrap_built_in(fn, t):
    def resolver(h, now): return (fn(h, now), t)
    return {"resolver": resolver}


def normalize_built_ins(built_in_vars: list) -> dict[str, dict]:
    """Convert BUILT_IN_VARS list to {short: {resolver}} dict."""
    return {v["short"]: _wrap_built_in(v["resolver"], v["type"]) for v in built_in_vars}


def build_custom_resolvers(hass, custom_vars_text: str) -> dict[str, dict]:
    """Parse custom_vars text and return {name: {resolver}} for each binding."""
    from homeassistant.helpers.template import Template

    def _make_template(source):
        tpl = Template(source, hass)
        def resolver(h, now, _tpl=tpl):
            try:
                raw = str(_tpl.async_render())
                return (_coerce_state(raw), _infer_type_from_value(raw))
            except Exception:
                return (None, "number")
        return {"resolver": resolver}

    def _make_entity(source):
        def resolver(h, now, _src=source, _hass=hass):
            state = h.states.get(_src)
            value = None if (state is None or state.state in ("unavailable", "unknown")) else _coerce_state(state.state)
            return (value, _infer_type_from_entity(_hass, _src))
        return {"resolver": resolver}

    result = {}
    for line in custom_vars_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, source = line.partition("=")
        name = name.strip().lower()
        source = source.strip()
        if name:
            make = _make_template if source.startswith("{{") and source.endswith("}}") else _make_entity
            result[name] = make(source)
    return result


# ---------------------------------------------------------------------------
# Unified resolution
# ---------------------------------------------------------------------------

def resolve_all(hass, now, specs: dict[str, dict]) -> tuple[dict, dict]:
    """Resolve all vars. Returns (vals dict, types dict)."""
    vals, types = {}, {}
    for name, spec in specs.items():
        vals[name], types[name] = spec["resolver"](hass, now)
    return vals, types


# ---------------------------------------------------------------------------
# Ad-hoc evaluation for the WS endpoint (no config change)
# ---------------------------------------------------------------------------

def eval_vars(hass, custom_vars_text: str) -> list[dict]:
    """Evaluate custom variable bindings ad-hoc. Returns [{short, long, type, value}]."""
    from homeassistant.helpers.template import Template

    seen: dict[str, dict] = {}
    for line in custom_vars_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, source = line.partition("=")
        name = name.strip().lower()
        source = source.strip()
        if not name:
            continue

        if source.startswith("{{") and source.endswith("}}"):
            try:
                raw = str(Template(source, hass).async_render())
                value    = _coerce_state(raw)
                var_type = _infer_type_from_value(raw)
            except Exception:
                value, var_type = None, "number"
        else:
            var_type = _infer_type_from_entity(hass, source)
            s = hass.states.get(source)
            value = None if (s is None or s.state in ("unavailable", "unknown")) else _coerce_state(s.state)

        seen[name] = {"short": name, "long": name, "type": var_type, "value": value}
    return list(seen.values())
