"""Pure rule-matching logic — no Home Assistant imports, fully unit-testable."""

import operator
from datetime import time

_OPS = {
    ">":  operator.gt,
    "<":  operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
}


def rule_matches(
    conditions: list,
    azimuth: float,
    elevation: float,
    time_hhmm: int,
    month: int = 1,
    presence: bool | None = None,
) -> bool:
    """Return True if all conditions are satisfied.

    conditions is a list of {"var": str, "op": str, "val": number|str}.
    time_hhmm is hour*100 + minute (e.g. 19:30 → 1930).
    """
    vals = {
        "azimuth":   azimuth,
        "elevation": elevation,
        "time":      time_hhmm,
        "month":     month,
    }

    for cond in conditions:
        var     = cond.get("var")
        op_str  = cond.get("op")
        expected = cond.get("val")

        if var == "presence":
            if expected == "home" and presence is not True:
                return False
            if expected == "away" and presence is not False:
                return False
            continue

        if var not in vals or op_str not in _OPS:
            continue  # unknown var/op — ignore silently

        if not _OPS[op_str](vals[var], expected):
            return False

    return True


def fill_targets(
    mode: str,
    groups: list,
    targets: dict,
    azimuth: float,
    elevation: float,
    time_hhmm: int,
    month: int = 1,
    presence: bool | None = None,
) -> None:
    """Apply first-matching rule per group for *mode* to covers not yet in *targets*."""
    for group in groups:
        if group.get("mode") != mode:
            continue
        covers = group.get("covers", [])
        for rule in group.get("rules", []):
            if not rule_matches(rule.get("conditions", []), azimuth, elevation, time_hhmm, month, presence):
                continue
            action = rule.get("action", {})
            p = action.get("position")
            t = action.get("tilt")
            if p is None and t is None:
                continue  # no valid action — try next rule
            for cover in covers:
                if cover not in targets:
                    targets[cover] = {"p": p, "t": t}
            break  # first matching rule with valid action wins for this group


def evaluate_rules(
    groups: list,
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
    fill_targets("_priority",  groups, targets, azimuth, elevation, time_hhmm, month, presence)
    if current_mode:
        fill_targets(current_mode, groups, targets, azimuth, elevation, time_hhmm, month, presence)
    fill_targets("_fallback",  groups, targets, azimuth, elevation, time_hhmm, month, presence)
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
