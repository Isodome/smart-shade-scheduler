"""Tests for rule_matches() — all condition operators and variables."""
from custom_components.smart_shades.logic import rule_matches

# Default evaluation context (afternoon, sunny)
_SUN  = dict(azimuth=200.0, elevation=10.0, hour=14, minute=30, month=1)
_MORN = dict(azimuth=90.0,  elevation=20.0, hour=8,  minute=0,  month=1)


def _vals(**kwargs):
    """Build a vals dict using short keys (canonical internal form)."""
    ctx = {**_SUN, **kwargs}
    return {
        "az": ctx["azimuth"],
        "el": ctx["elevation"],
        "t":  ctx["hour"] * 100 + ctx["minute"],
        "mo": ctx["month"],
    }


def m(conditions, prev=None, **kwargs):
    return rule_matches(conditions, _vals(**kwargs), prev)


def c(var, op, val):
    return {"var": var, "op": op, "val": val}


# ── Catch-all ─────────────────────────────────────────────────────────────────

def test_empty_conditions_always_matches():
    assert m([])


# ── Azimuth ───────────────────────────────────────────────────────────────────

def test_azimuth_above():
    assert     m([c("az", ">", 185)])
    assert not m([c("az", ">", 200)])   # 200 is not > 200
    assert not m([c("az", ">", 210)])

def test_azimuth_below():
    assert     m([c("az", "<", 210)])
    assert not m([c("az", "<", 200)])
    assert not m([c("az", "<", 190)])

def test_azimuth_min():
    assert     m([c("az", ">=", 200)])
    assert     m([c("az", ">=", 185)])
    assert not m([c("az", ">=", 201)])

def test_azimuth_max():
    assert     m([c("az", "<=", 200)])
    assert     m([c("az", "<=", 210)])
    assert not m([c("az", "<=", 199)])

def test_azimuth_eq():
    assert     m([c("az", "==", 200)])
    assert not m([c("az", "==", 199)])

def test_azimuth_range():
    conds = [c("az", ">=", 185), c("az", "<=", 250)]
    assert     m(conds)
    assert not m(conds, azimuth=180)
    assert not m(conds, azimuth=251)


# ── Elevation ──────────────────────────────────────────────────────────────────

def test_elevation_above():
    assert     m([c("el", ">", 5)])
    assert not m([c("el", ">", 10)])
    assert not m([c("el", ">", 15)])

def test_elevation_below():
    assert     m([c("el", "<", 15)])
    assert not m([c("el", "<", 10)])
    assert not m([c("el", "<", 5)])

def test_elevation_min():
    assert     m([c("el", ">=", 10)])
    assert not m([c("el", ">=", 11)])

def test_elevation_max():
    assert     m([c("el", "<=", 10)])
    assert not m([c("el", "<=", 9)])

def test_elevation_eq():
    assert     m([c("el", "==", 10)])
    assert not m([c("el", "==", 9)])

def test_night_rule():
    assert     m([c("el", "<", 0)], elevation=-1)
    assert not m([c("el", "<", 0)], elevation=0)
    assert not m([c("el", "<", 0)], elevation=1)


# ── Time (HHMM integer) ────────────────────────────────────────────────────────

def test_time_above():
    assert not m([c("t", ">", 800)], **_MORN)   # 800 not > 800
    assert     m([c("t", ">", 700)], **_MORN)
    assert not m([c("t", ">", 900)], **_MORN)

def test_time_below():
    assert     m([c("t", "<", 900)], **_MORN)
    assert not m([c("t", "<", 800)], **_MORN)

def test_time_min():
    assert     m([c("t", ">=", 800)], **_MORN)
    assert not m([c("t", ">=", 900)], **_MORN)

def test_time_max():
    assert     m([c("t", "<=", 800)], **_MORN)
    assert not m([c("t", "<=", 700)], **_MORN)

def test_time_eq():
    assert     m([c("t", "==", 800)], **_MORN)
    assert not m([c("t", "==", 900)], **_MORN)

def test_time_window():
    conds = [c("t", ">=", 800), c("t", "<=", 1000)]
    assert     m(conds, **{**_MORN, "hour": 8})
    assert     m(conds, **{**_MORN, "hour": 10})
    assert not m(conds, **{**_MORN, "hour": 7})
    assert not m(conds, **{**_MORN, "hour": 11})

def test_time_minutes():
    assert     m([c("t", ">", 1429)])   # _SUN = 14:30 = 1430
    assert not m([c("t", ">", 1430)])
    assert     m([c("t", "<", 1431)])
    assert not m([c("t", "<", 1430)])


# ── Month ──────────────────────────────────────────────────────────────────────

def test_month_in_range():
    conds = [c("mo", ">=", 4), c("mo", "<=", 9)]
    assert     m(conds, month=4)
    assert     m(conds, month=9)
    assert not m(conds, month=3)
    assert not m(conds, month=10)

def test_month_eq():
    assert     m([c("mo", "==", 6)], month=6)
    assert not m([c("mo", "==", 6)], month=7)


# ── Day of week ───────────────────────────────────────────────────────────────

def test_day_weekday():
    mon = {**_vals(), "d": 0}
    sat = {**_vals(), "d": 5}
    assert     rule_matches([c("d", "<=", 4)], mon)  # Mon is a weekday
    assert not rule_matches([c("d", "<=", 4)], sat)  # Sat is not

def test_day_specific():
    assert     rule_matches([c("d",  "==", 0)], {**_vals(), "d": 0})  # Monday
    assert not rule_matches([c("d",  "==", 0)], {**_vals(), "d": 1})  # Tuesday

def test_day_long_name_accepted():
    assert rule_matches([c("day", "==", 0)], {**_vals(), "d": 0})


# ── Unknown var / op silently ignored ─────────────────────────────────────────

def test_unknown_var_ignored():
    assert m([{"var": "humidity", "op": ">", "val": 80}])

def test_unknown_op_ignored():
    assert m([{"var": "azimuth", "op": "!=", "val": 200}])


# ── Combined (AND semantics) ───────────────────────────────────────────────────

def test_combined_sun_and_time():
    conds = [c("az", ">", 185), c("el", ">", 5), c("t", ">", 1200)]
    assert     m(conds)
    assert not m(conds, azimuth=180)
    assert not m(conds, elevation=3)
    assert not m(conds, hour=10)


# ── Crossing conditions — numeric ─────────────────────────────────────────────

def _cross(conditions, prev_kw, cur_kw):
    return rule_matches(conditions, _vals(**cur_kw), _vals(**prev_kw))


def test_crossing_no_prev_vals_never_fires():
    # Without prev_vals, crossing conditions always return False
    assert not m([c("az", "=^", 185)])
    assert not m([c("az", "=v", 185)])
    assert not m([c("az", "=",  185)])

def test_crossing_rising_fires_when_threshold_crossed_upward():
    assert     _cross([c("az", "=^", 185)], {"azimuth": 180}, {"azimuth": 190})
    assert not _cross([c("az", "=^", 185)], {"azimuth": 190}, {"azimuth": 195})  # already past
    assert not _cross([c("az", "=^", 185)], {"azimuth": 185}, {"azimuth": 190})  # threshold not crossed (prev == threshold)
    assert not _cross([c("az", "=^", 185)], {"azimuth": 190}, {"azimuth": 180})  # falling

def test_crossing_rising_fires_when_landing_exactly_on_threshold():
    # prev < threshold = cur → should fire
    assert _cross([c("az", "=^", 185)], {"azimuth": 180}, {"azimuth": 185})

def test_crossing_falling_fires_when_threshold_crossed_downward():
    assert     _cross([c("el", "=v", 10)], {"elevation": 15}, {"elevation": 5})
    assert not _cross([c("el", "=v", 10)], {"elevation": 5},  {"elevation": 3})   # already past
    assert not _cross([c("el", "=v", 10)], {"elevation": 15}, {"elevation": 20})  # rising

def test_crossing_falling_fires_when_landing_exactly_on_threshold():
    assert _cross([c("el", "=v", 10)], {"elevation": 15}, {"elevation": 10})

def test_crossing_undirected_fires_both_ways():
    assert _cross([c("el", "=", 10)], {"elevation": 5},  {"elevation": 15})  # rising
    assert _cross([c("el", "=", 10)], {"elevation": 15}, {"elevation": 5})   # falling

def test_crossing_skipped_value_still_fires():
    # Prev=0, cur=2, threshold=1: the value was crossed even though never sampled at 1
    assert _cross([c("az", "=^", 1)], {"azimuth": 0}, {"azimuth": 2})

def test_crossing_time_fires_at_threshold():
    assert     _cross([c("t", "=^", 730)], {"hour": 7, "minute": 25}, {"hour": 7, "minute": 32})
    assert not _cross([c("t", "=^", 730)], {"hour": 7, "minute": 32}, {"hour": 7, "minute": 45})


