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
) -> bool:
    """Return True if all conditions are satisfied.

    vals keys: azimuth (float), elevation (float), time (HHMM int), month (int),
               presence ("home"|"away"|None), workday ("work"|"nowork"|None).
               Custom sensor vars can be added under any other key.
    prev_vals: same shape as vals; required for crossing operators (=, =^, =v).

    A key present in vals with value None → condition returns False immediately
    (declared-but-unavailable, fail-safe). A key absent from vals entirely →
    condition is silently ignored (forward-compat with unknown future vars).
    """
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

        if op_str in ("=", "=^", "=v"):
            # Crossing condition — needs previous sample
            if prev_vals is None:
                return False
            prev = prev_vals.get(var)
            if prev is None:
                return False

            var_type = _VAR_TYPE.get(var, "number")

            if var_type == "time":
                # Time is monotonic; =v never fires.
                # Standard prev < threshold <= cur handles midnight wrap correctly.
                if op_str == "=v":
                    return False
                if not (prev < expected <= cur):
                    return False
            elif isinstance(expected, str):
                # String/boolean: crossing into or out of a specific state
                if op_str == "=v":
                    if not (prev == expected and cur != expected):
                        return False
                else:  # "=" or "=^" — "just entered this state"
                    if not (prev != expected and cur == expected):
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
) -> None:
    """Apply first-matching rule per group for *mode* to covers not yet in *targets*."""
    for group in groups:
        if group.get("mode") != mode:
            continue
        covers = group.get("covers", [])
        for rule in group.get("rules", []):
            if not rule_matches(rule.get("conditions", []), vals, prev_vals):
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
) -> dict:
    """Run the full 3-pass evaluation and return the shade targets dict.

    Returns: { entity_id: {"p": position_or_None, "t": tilt_or_None} }
    block_fallback: when True, the fallback pass is skipped entirely.
    """
    targets: dict = {}
    fill_targets("_priority", groups, targets, vals, prev_vals)
    if current_mode:
        fill_targets(current_mode, groups, targets, vals, prev_vals)
    if not block_fallback:
        fill_targets("_fallback", groups, targets, vals, prev_vals)
    return targets


def normalize_groups(rules: list) -> list:
    """Expand old {rules:[{conditions,action},...]} groups to flat {conditions,action} groups.

    Idempotent: groups already in the new flat format are passed through unchanged.
    """
    out = []
    for g in rules:
        if "rules" in g:
            for r in g["rules"]:
                out.append({
                    "mode":       g.get("mode"),
                    "covers":     g.get("covers", []),
                    "conditions": r.get("conditions", []),
                    "action":     r.get("action", {}),
                })
        else:
            out.append(g)
    return out


