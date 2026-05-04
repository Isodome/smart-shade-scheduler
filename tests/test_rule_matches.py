"""Tests for rule_matches() — all condition operators using AST."""
import pytest
from custom_components.smart_shades.logic import rule_matches

SUN  = dict(azimuth=200.0, elevation=10.0, hour=14, minute=30)
MORN = dict(azimuth=90.0,  elevation=20.0, hour=8,  minute=0)


def m(conditions, **kwargs):
    ctx = {**SUN, **kwargs}
    time_hhmm = ctx["hour"] * 100 + ctx["minute"]
    month = ctx.get("month", 1)
    return rule_matches(conditions, ctx["azimuth"], ctx["elevation"], time_hhmm, month)


# ── Empty rule (catch-all) ────────────────────────────────────────────────────

def test_empty_rule_always_matches():
    assert m([])


# ── Azimuth ──────────────────────────────────────────────────────────────────

def test_azimuth_above():
    assert     m([{"var": "azimuth", "op": ">", "val": 185}])
    assert not m([{"var": "azimuth", "op": ">", "val": 200}])   # 200 is not > 200
    assert not m([{"var": "azimuth", "op": ">", "val": 210}])

def test_azimuth_below():
    assert     m([{"var": "azimuth", "op": "<", "val": 210}])
    assert not m([{"var": "azimuth", "op": "<", "val": 200}])   # 200 is not < 200
    assert not m([{"var": "azimuth", "op": "<", "val": 190}])

def test_azimuth_min():
    assert     m([{"var": "azimuth", "op": ">=", "val": 200}])     # 200 >= 200
    assert     m([{"var": "azimuth", "op": ">=", "val": 185}])
    assert not m([{"var": "azimuth", "op": ">=", "val": 201}])

def test_azimuth_max():
    assert     m([{"var": "azimuth", "op": "<=", "val": 200}])     # 200 <= 200
    assert     m([{"var": "azimuth", "op": "<=", "val": 210}])
    assert not m([{"var": "azimuth", "op": "<=", "val": 199}])

def test_azimuth_eq():
    assert     m([{"var": "azimuth", "op": "==", "val": 200}])
    assert not m([{"var": "azimuth", "op": "==", "val": 199}])

def test_azimuth_range():
    conds = [{"var": "azimuth", "op": ">=", "val": 185}, {"var": "azimuth", "op": "<=", "val": 250}]
    assert     m(conds)
    assert not m(conds, azimuth=180)
    assert not m(conds, azimuth=251)


# ── Elevation ─────────────────────────────────────────────────────────────────

def test_elevation_above():
    assert     m([{"var": "elevation", "op": ">", "val": 5}])
    assert not m([{"var": "elevation", "op": ">", "val": 10}])
    assert not m([{"var": "elevation", "op": ">", "val": 15}])

def test_elevation_below():
    assert     m([{"var": "elevation", "op": "<", "val": 15}])
    assert not m([{"var": "elevation", "op": "<", "val": 10}])
    assert not m([{"var": "elevation", "op": "<", "val": 5}])

def test_elevation_min():
    assert     m([{"var": "elevation", "op": ">=", "val": 10}])
    assert not m([{"var": "elevation", "op": ">=", "val": 11}])

def test_elevation_max():
    assert     m([{"var": "elevation", "op": "<=", "val": 10}])
    assert not m([{"var": "elevation", "op": "<=", "val": 9}])

def test_elevation_eq():
    assert     m([{"var": "elevation", "op": "==", "val": 10}])
    assert not m([{"var": "elevation", "op": "==", "val": 9}])

def test_night_rule():
    assert     m([{"var": "elevation", "op": "<", "val": 0}], elevation=-1)
    assert not m([{"var": "elevation", "op": "<", "val": 0}], elevation=0)
    assert not m([{"var": "elevation", "op": "<", "val": 0}], elevation=1)


# ── Time ──────────────────────────────────────────────────────────────────────

def test_time_above():
    assert not m([{"var": "time", "op": ">", "val": 800}], **MORN)
    assert     m([{"var": "time", "op": ">", "val": 700}], **MORN)
    assert not m([{"var": "time", "op": ">", "val": 900}], **MORN)

def test_time_below():
    assert     m([{"var": "time", "op": "<", "val": 900}],  **MORN)
    assert not m([{"var": "time", "op": "<", "val": 800}],  **MORN)

def test_time_min():
    assert     m([{"var": "time", "op": ">=", "val": 800}],    **MORN)
    assert not m([{"var": "time", "op": ">=", "val": 900}],    **MORN)

def test_time_max():
    assert     m([{"var": "time", "op": "<=", "val": 800}],    **MORN)
    assert not m([{"var": "time", "op": "<=", "val": 700}],    **MORN)

def test_time_eq():
    assert     m([{"var": "time", "op": "==", "val": 800}],     **MORN)
    assert not m([{"var": "time", "op": "==", "val": 900}],     **MORN)

def test_time_window():
    conds = [{"var": "time", "op": ">=", "val": 800}, {"var": "time", "op": "<=", "val": 1000}]
    assert     m(conds, **{**MORN, "hour": 8})
    assert     m(conds, **{**MORN, "hour": 10})
    assert not m(conds, **{**MORN, "hour": 7})
    assert not m(conds, **{**MORN, "hour": 11})

def test_time_minutes():
    # SUN has hour=14, minute=30 -> 1430
    assert     m([{"var": "time", "op": ">", "val": 1429}])
    assert not m([{"var": "time", "op": ">", "val": 1430}])
    assert     m([{"var": "time", "op": "<", "val": 1431}])
    assert not m([{"var": "time", "op": "<", "val": 1430}])


# ── Combined conditions (AND semantics) ───────────────────────────────────────

def test_combined_sun_and_time():
    conds = [
        {"var": "azimuth", "op": ">", "val": 185},
        {"var": "elevation", "op": ">", "val": 5},
        {"var": "time", "op": ">", "val": 1200}
    ]
    assert     m(conds)                           # az=200, el=10, h=14 → all pass
    assert not m(conds, azimuth=180)              # az fails
    assert not m(conds, elevation=3)              # el fails
    assert not m(conds, hour=10)                  # time fails
