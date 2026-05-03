"""Pure rule-matching logic — no Home Assistant imports, fully unit-testable."""

import operator
from datetime import time

# To add a new condition variable, add one entry here.
_VARS = ("azimuth", "elevation", "time", "month")

# To add a new operator, add one entry here.
_OPS = (
    ("above", operator.gt),
    ("below", operator.lt),
    ("min",   operator.ge),
    ("max",   operator.le),
    ("eq",    operator.eq),
)


def rule_matches(
    rule: dict,
    azimuth: float,
    elevation: float,
    time_hhmm: int,
    month: int = 1,
    presence: bool | None = None,
) -> bool:
    """Return True if all conditions in *rule* are satisfied.

    time_hhmm is hour*100 + minute (e.g. 19:30 → 1930).
    """
    vals = {
        "azimuth":   azimuth,
        "elevation": elevation,
        "time":      time_hhmm,
        "month":     month,
    }

    def _ok(key, val, op):
        v = rule.get(key)
        return v is None or op(val, v)

    if not all(
        _ok(f"{var}_{suffix}", vals[var], op)
        for var in _VARS
        for suffix, op in _OPS
    ):
        return False

    if rule.get("require_home") and presence is not True:
        return False
    if rule.get("require_away") and presence is not False:
        return False

    return True


def fill_targets(
    mode: str,
    rules: list,
    targets: dict,
    azimuth: float,
    elevation: float,
    time_hhmm: int,
    month: int = 1,
    presence: bool | None = None,
) -> None:
    """Apply first-matching rules for *mode* to covers not yet in *targets*."""
    for rule in rules:
        if rule.get("mode") != mode:
            continue
        if not rule_matches(rule, azimuth, elevation, time_hhmm, month, presence):
            continue
        for cover in rule.get("covers", []):
            if cover not in targets:
                targets[cover] = {
                    "p": rule.get("position"),
                    "t": rule.get("tilt"),
                }


def evaluate_rules(
    rules: list,
    current_mode: str | None,
    azimuth: float,
    elevation: float,
    time_hhmm: int,
    month: int = 1,
    presence: bool | None = None,
) -> dict:
    """Run the full 3-pass evaluation and return the shade targets dict.

    Returns: { entity_id: {"p": position_or_None, "t": tilt_or_None} }
    """
    targets: dict = {}
    fill_targets("_priority",  rules, targets, azimuth, elevation, time_hhmm, month, presence)
    if current_mode:
        fill_targets(current_mode, rules, targets, azimuth, elevation, time_hhmm, month, presence)
    fill_targets("_fallback",  rules, targets, azimuth, elevation, time_hhmm, month, presence)
    return targets


def is_dnd_active(start_str: str, end_str: str, now: time) -> bool:
    """Return True if *now* falls within the DND window."""
    try:
        start_parts = list(map(int, start_str.split(":")))
        end_parts   = list(map(int, end_str.split(":")))
        start = time(*start_parts)
        end   = time(*end_parts)
        if start <= end:
            return start <= now <= end
        return now >= start or now <= end  # overnight window e.g. 22:00–07:00
    except Exception:
        return False
