"""Tests for rule_matches() — all condition operators and variables."""
from custom_components.smart_shades.logic import rule_matches

SUN  = dict(azimuth=200.0, elevation=10.0, hour=14, minute=30)
MORN = dict(azimuth=90.0,  elevation=20.0, hour=8,  minute=0)


def m(conditions, presence=None, workday=None, **kwargs):
    ctx = {**SUN, **kwargs}
    time_hhmm = ctx["hour"] * 100 + ctx["minute"]
    month = ctx.get("month", 1)
    return rule_matches(conditions, ctx["azimuth"], ctx["elevation"], time_hhmm, month, presence, workday)


def c(var, op, val):
    return {"var": var, "op": op, "val": val}


# ── Catch-all ─────────────────────────────────────────────────────────────────

def test_empty_conditions_always_matches():
    assert m([])


# ── Azimuth ───────────────────────────────────────────────────────────────────

def test_azimuth_above():
    assert     m([c("azimuth", ">", 185)])
    assert not m([c("azimuth", ">", 200)])   # 200 is not > 200
    assert not m([c("azimuth", ">", 210)])

def test_azimuth_below():
    assert     m([c("azimuth", "<", 210)])
    assert not m([c("azimuth", "<", 200)])
    assert not m([c("azimuth", "<", 190)])

def test_azimuth_min():
    assert     m([c("azimuth", ">=", 200)])
    assert     m([c("azimuth", ">=", 185)])
    assert not m([c("azimuth", ">=", 201)])

def test_azimuth_max():
    assert     m([c("azimuth", "<=", 200)])
    assert     m([c("azimuth", "<=", 210)])
    assert not m([c("azimuth", "<=", 199)])

def test_azimuth_eq():
    assert     m([c("azimuth", "==", 200)])
    assert not m([c("azimuth", "==", 199)])

def test_azimuth_range():
    conds = [c("azimuth", ">=", 185), c("azimuth", "<=", 250)]
    assert     m(conds)
    assert not m(conds, azimuth=180)
    assert not m(conds, azimuth=251)


# ── Elevation ──────────────────────────────────────────────────────────────────

def test_elevation_above():
    assert     m([c("elevation", ">", 5)])
    assert not m([c("elevation", ">", 10)])
    assert not m([c("elevation", ">", 15)])

def test_elevation_below():
    assert     m([c("elevation", "<", 15)])
    assert not m([c("elevation", "<", 10)])
    assert not m([c("elevation", "<", 5)])

def test_elevation_min():
    assert     m([c("elevation", ">=", 10)])
    assert not m([c("elevation", ">=", 11)])

def test_elevation_max():
    assert     m([c("elevation", "<=", 10)])
    assert not m([c("elevation", "<=", 9)])

def test_elevation_eq():
    assert     m([c("elevation", "==", 10)])
    assert not m([c("elevation", "==", 9)])

def test_night_rule():
    assert     m([c("elevation", "<", 0)], elevation=-1)
    assert not m([c("elevation", "<", 0)], elevation=0)
    assert not m([c("elevation", "<", 0)], elevation=1)


# ── Time (HHMM integer) ────────────────────────────────────────────────────────

def test_time_above():
    assert not m([c("time", ">", 800)], **MORN)   # 800 not > 800
    assert     m([c("time", ">", 700)], **MORN)
    assert not m([c("time", ">", 900)], **MORN)

def test_time_below():
    assert     m([c("time", "<", 900)], **MORN)
    assert not m([c("time", "<", 800)], **MORN)

def test_time_min():
    assert     m([c("time", ">=", 800)], **MORN)
    assert not m([c("time", ">=", 900)], **MORN)

def test_time_max():
    assert     m([c("time", "<=", 800)], **MORN)
    assert not m([c("time", "<=", 700)], **MORN)

def test_time_eq():
    assert     m([c("time", "==", 800)], **MORN)
    assert not m([c("time", "==", 900)], **MORN)

def test_time_window():
    conds = [c("time", ">=", 800), c("time", "<=", 1000)]
    assert     m(conds, **{**MORN, "hour": 8})
    assert     m(conds, **{**MORN, "hour": 10})
    assert not m(conds, **{**MORN, "hour": 7})
    assert not m(conds, **{**MORN, "hour": 11})

def test_time_minutes():
    assert     m([c("time", ">", 1429)])   # SUN = 14:30 = 1430
    assert not m([c("time", ">", 1430)])
    assert     m([c("time", "<", 1431)])
    assert not m([c("time", "<", 1430)])


# ── Month ──────────────────────────────────────────────────────────────────────

def test_month_in_range():
    conds = [c("month", ">=", 4), c("month", "<=", 9)]
    assert     m(conds, month=4)
    assert     m(conds, month=9)
    assert not m(conds, month=3)
    assert not m(conds, month=10)

def test_month_eq():
    assert     m([c("month", "==", 6)], month=6)
    assert not m([c("month", "==", 6)], month=7)


# ── Presence ───────────────────────────────────────────────────────────────────

def test_home_matches_when_present():
    assert     m([c("presence", "==", "home")], presence=True)
    assert not m([c("presence", "==", "home")], presence=False)
    assert not m([c("presence", "==", "home")], presence=None)

def test_away_matches_when_absent():
    assert     m([c("presence", "==", "away")], presence=False)
    assert not m([c("presence", "==", "away")], presence=True)
    assert not m([c("presence", "==", "away")], presence=None)

def test_presence_combined_with_sun():
    conds = [c("presence", "==", "home"), c("elevation", ">", 5)]
    assert     m(conds, presence=True)
    assert not m(conds, presence=False)
    assert not m(conds, presence=True, elevation=3)


# ── Workday ────────────────────────────────────────────────────────────────────

def test_work_matches_on_workday():
    assert     m([c("workday", "==", "work")], workday=True)
    assert not m([c("workday", "==", "work")], workday=False)
    assert not m([c("workday", "==", "work")], workday=None)

def test_nowork_matches_on_day_off():
    assert     m([c("workday", "==", "nowork")], workday=False)
    assert not m([c("workday", "==", "nowork")], workday=True)
    assert not m([c("workday", "==", "nowork")], workday=None)

def test_workday_combined_with_time():
    conds = [c("workday", "==", "work"), c("time", ">=", 800), c("time", "<=", 1700)]
    assert     m(conds, workday=True,  hour=9)
    assert not m(conds, workday=False, hour=9)    # day off
    assert not m(conds, workday=True,  hour=18)   # after 17:00


# ── Unknown var / op silently ignored ─────────────────────────────────────────

def test_unknown_var_ignored():
    # An unknown var is skipped — rule still matches
    assert m([{"var": "humidity", "op": ">", "val": 80}])

def test_unknown_op_ignored():
    assert m([{"var": "azimuth", "op": "!=", "val": 200}])


# ── Combined (AND semantics) ───────────────────────────────────────────────────

def test_combined_sun_and_time():
    conds = [c("azimuth", ">", 185), c("elevation", ">", 5), c("time", ">", 1200)]
    assert     m(conds)
    assert not m(conds, azimuth=180)
    assert not m(conds, elevation=3)
    assert not m(conds, hour=10)
