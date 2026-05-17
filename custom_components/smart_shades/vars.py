"""Variable resolution — built-ins and custom bindings share a unified spec shape."""

import re as _re
from datetime import datetime

from homeassistant.util import dt as dt_util


# ---------------------------------------------------------------------------
# State coercion
# ---------------------------------------------------------------------------

def _coerce_state(state_str: str) -> float | None:
    """Coerce an entity state string to float for use as a condition variable."""
    try:
        dt = datetime.fromisoformat(state_str)
        if dt.tzinfo is not None:
            dt = dt_util.as_local(dt)
        return float(dt.hour * 100 + dt.minute)
    except (ValueError, TypeError, AttributeError):
        pass
    m = _re.match(r"^(\d{1,2}):(\d{2})", state_str)
    if m:
        return float(int(m.group(1)) * 100 + int(m.group(2)))
    try:
        return float(state_str)
    except (ValueError, TypeError):
        pass
    low = state_str.strip().lower()
    if low in ("on",  "true",  "yes"): return 1.0
    if low in ("off", "false", "no"):  return 0.0
    return None


# ---------------------------------------------------------------------------
# Type inference
# ---------------------------------------------------------------------------

def _infer_type_from_raw(raw: str | None) -> str:
    if raw is None:
        return "number"
    low = raw.strip().lower()
    if low in ("on", "off", "true", "false", "yes", "no"):
        return "bool"
    r = raw.strip()
    if _re.match(r"^\d{1,2}:\d{2}", r):
        return "time"
    try:
        datetime.fromisoformat(r)
        return "time"
    except (ValueError, TypeError):
        pass
    return "number"


def _infer_type_from_entity(hass, entity_id: str) -> str:
    domain = entity_id.split(".")[0]
    if domain in ("binary_sensor", "input_boolean", "switch", "device_tracker"):
        return "bool"
    if domain == "sensor":
        state = hass.states.get(entity_id)
        if state and state.attributes.get("device_class") in ("timestamp", "date"):
            return "time"
    return "number"


# ---------------------------------------------------------------------------
# Unified spec shape: {resolver(hass, now) -> float|None, type_fn() -> str}
# ---------------------------------------------------------------------------

def normalize_built_ins(built_in_vars: list) -> dict[str, dict]:
    """Convert BUILT_IN_VARS list to {short: {resolver, type_fn}} dict."""
    return {
        v["short"]: {
            "resolver": v["resolver"],
            "type_fn": (lambda t=v["type"]: t),
        }
        for v in built_in_vars
    }


def build_custom_resolvers(hass, custom_vars_text: str) -> dict[str, dict]:
    """Parse custom_vars text and return {name: {resolver, type_fn}} for each binding."""
    from homeassistant.helpers.template import Template

    def _make(source):
        if source.startswith("{{") and source.endswith("}}"):
            tpl = Template(source, hass)
            _last_raw: list[str | None] = [None]
            def resolver(h, now, _tpl=tpl, _last=_last_raw):
                try:
                    raw = str(_tpl.async_render())
                    _last[0] = raw
                    return _coerce_state(raw)
                except Exception:
                    return None
            def type_fn(_last=_last_raw):
                return _infer_type_from_raw(_last[0])
        else:
            def resolver(h, now, _src=source):
                state = h.states.get(_src)
                if state is None or state.state in ("unavailable", "unknown"):
                    return None
                return _coerce_state(state.state)
            def type_fn(_src=source, _hass=hass):
                return _infer_type_from_entity(_hass, _src)
        return {"resolver": resolver, "type_fn": type_fn}

    result = {}
    for line in custom_vars_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, source = line.partition("=")
        name = name.strip().lower()
        source = source.strip()
        if name:
            result[name] = _make(source)
    return result


# ---------------------------------------------------------------------------
# Unified resolution
# ---------------------------------------------------------------------------

def resolve_all(hass, now, specs: dict[str, dict]) -> tuple[dict, dict]:
    """Resolve all vars. Returns (vals dict, types dict)."""
    vals, types = {}, {}
    for name, spec in specs.items():
        vals[name]  = spec["resolver"](hass, now)
        types[name] = spec["type_fn"]()
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
                var_type = _infer_type_from_raw(raw)
            except Exception:
                value, var_type = None, "number"
        else:
            var_type = _infer_type_from_entity(hass, source)
            s = hass.states.get(source)
            value = None if (s is None or s.state in ("unavailable", "unknown")) else _coerce_state(s.state)

        seen[name] = {"short": name, "long": name, "type": var_type, "value": value}
    return list(seen.values())
