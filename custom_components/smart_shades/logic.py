"""Pure rule-matching logic — no Home Assistant imports, fully unit-testable."""

import operator

from .const import BUILT_IN_VARS

_OPS = {
    ">":  operator.gt,
    "<":  operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
}

# Derived from BUILT_IN_VARS — the single source of truth.
_LONG_TO_SHORT = {v["long"]: v["short"] for v in BUILT_IN_VARS}
_VAR_TYPE      = {v["short"]: v["type"]  for v in BUILT_IN_VARS}


def rule_matches(
    conditions: list,
    vals: dict,
    prev_vals: dict | None = None,
    extra_types: dict | None = None,
) -> bool:
    """Return True if all conditions are satisfied.

    vals keys: azimuth (float), elevation (float), time (HHMM int), month (int),
               presence ("home"|"away"|None), workday ("work"|"nowork"|None).
               Custom sensor vars can be added under any other key.
    prev_vals: same shape as vals; required for crossing operators (=, =^, =v).
    extra_types: {var_short: "number"|"bool"|"time"} for custom variables.

    A key present in vals with value None → condition returns False immediately
    (declared-but-unavailable, fail-safe). A key absent from vals entirely →
    condition is silently ignored (forward-compat with unknown future vars).
    """
    type_map = _VAR_TYPE if not extra_types else {**_VAR_TYPE, **extra_types}
    for cond in conditions:
        var      = _LONG_TO_SHORT.get(cond.get("var"), cond.get("var"))
        op_str   = cond.get("op")
        expected = cond.get("val")

        # Unknown variable — silently ignore (forward-compat)
        if var not in vals:
            continue

        cur = vals[var]

        # Declared-but-unavailable — fail safe
        if cur is None:
            return False

        # Bool operators — no val needed
        if op_str == "bool":
            if not cur:
                return False
            continue
        if op_str == "!bool":
            if cur:
                return False
            continue

        if op_str in ("=", "=^", "=v"):
            # Crossing condition — needs previous sample
            if prev_vals is None:
                return False
            prev = prev_vals.get(var)
            if prev is None:
                return False

            var_type = type_map.get(var, "number")

            if var_type == "time":
                # Time is monotonic; =v never fires.
                if op_str == "=v":
                    return False
                
                # Check if a midnight wrap occurred between prev and cur
                if cur < prev:
                    if not (prev < expected or expected <= cur):
                        return False
                else:
                    if not (prev < expected <= cur):
                        return False
            else:
                # Numeric threshold crossing
                if op_str == "=^":
                    if not (prev < expected <= cur):
                        return False
                elif op_str == "=v":
                    if not (prev > expected >= cur):
                        return False
                else:  # "=" — either direction
                    if not ((prev < expected <= cur) or (prev > expected >= cur)):
                        return False

        elif op_str in _OPS:
            if not _OPS[op_str](cur, expected):
                return False

        # Unknown operator — silently ignore

    return True


def fill_targets(
    mode: str,
    groups: list,
    targets: dict,
    vals: dict,
    prev_vals: dict | None = None,
    extra_types: dict | None = None,
) -> None:
    """Apply first-matching rule per group for *mode* to covers not yet in *targets*."""
    for group in groups:
        if group.get("mode") != mode:
            continue
        covers = group.get("covers", [])
        for rule in group.get("rules", []):
            if not rule_matches(rule.get("conditions", []), vals, prev_vals, extra_types):
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
    vals: dict,
    prev_vals: dict | None = None,
    block_fallback: bool = False,
    extra_types: dict | None = None,
) -> dict:
    """Run the full 3-pass evaluation and return the shade targets dict.

    Returns: { entity_id: {"p": position_or_None, "t": tilt_or_None} }
    block_fallback: when True, the fallback pass is skipped entirely.
    extra_types: {var_short: type_str} for custom variables.
    """
    targets: dict = {}
    fill_targets("_priority", groups, targets, vals, prev_vals, extra_types)
    if current_mode:
        fill_targets(current_mode, groups, targets, vals, prev_vals, extra_types)
    if not block_fallback:
        fill_targets("_fallback", groups, targets, vals, prev_vals, extra_types)
    return targets


