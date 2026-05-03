"""Tests for rule_matches() — all condition operators."""
import pytest
from custom_components.smart_shades.logic import rule_matches

SUN  = dict(azimuth=200.0, elevation=10.0, hour=14, minute=30)
MORN = dict(azimuth=90.0,  elevation=20.0, hour=8,  minute=0)


def m(rule, **kwargs):
    ctx = {**SUN, **kwargs}
    time_hhmm = ctx["hour"] * 100 + ctx["minute"]
    month = ctx.get("month", 1)
    return rule_matches(rule, ctx["azimuth"], ctx["elevation"], time_hhmm, month)


# ── Empty rule (catch-all) ────────────────────────────────────────────────────

def test_empty_rule_always_matches():
    assert m({})


# ── Azimuth ──────────────────────────────────────────────────────────────────

def test_azimuth_above():
    assert     m({"azimuth_above": 185})
    assert not m({"azimuth_above": 200})   # 200 is not > 200
    assert not m({"azimuth_above": 210})

def test_azimuth_below():
    assert     m({"azimuth_below": 210})
    assert not m({"azimuth_below": 200})   # 200 is not < 200
    assert not m({"azimuth_below": 190})

def test_azimuth_min():
    assert     m({"azimuth_min": 200})     # 200 >= 200
    assert     m({"azimuth_min": 185})
    assert not m({"azimuth_min": 201})

def test_azimuth_max():
    assert     m({"azimuth_max": 200})     # 200 <= 200
    assert     m({"azimuth_max": 210})
    assert not m({"azimuth_max": 199})

def test_azimuth_eq():
    assert     m({"azimuth_eq": 200})
    assert not m({"azimuth_eq": 199})

def test_azimuth_range():
    assert     m({"azimuth_min": 185, "azimuth_max": 250})
    assert not m({"azimuth_min": 185, "azimuth_max": 250}, azimuth=180)
    assert not m({"azimuth_min": 185, "azimuth_max": 250}, azimuth=251)


# ── Elevation ─────────────────────────────────────────────────────────────────

def test_elevation_above():
    assert     m({"elevation_above": 5})
    assert not m({"elevation_above": 10})   # 10 is not > 10
    assert not m({"elevation_above": 15})

def test_elevation_below():
    assert     m({"elevation_below": 15})
    assert not m({"elevation_below": 10})   # 10 is not < 10
    assert not m({"elevation_below": 5})

def test_elevation_min():
    assert     m({"elevation_min": 10})     # 10 >= 10
    assert not m({"elevation_min": 11})

def test_elevation_max():
    assert     m({"elevation_max": 10})     # 10 <= 10
    assert not m({"elevation_max": 9})

def test_elevation_eq():
    assert     m({"elevation_eq": 10})
    assert not m({"elevation_eq": 9})

def test_night_rule():
    assert     m({"elevation_below": 0}, elevation=-1)
    assert not m({"elevation_below": 0}, elevation=0)
    assert not m({"elevation_below": 0}, elevation=1)


# ── Time ──────────────────────────────────────────────────────────────────────

def test_time_above():
    assert not m({"time_above": 800}, **MORN)   # t=800, 800 > 800 is False
    assert     m({"time_above": 700}, **MORN)   # t=800, 800 > 700 is True
    assert not m({"time_above": 900}, **MORN)   # t=800, 800 > 900 is False

def test_time_below():
    assert     m({"time_below": 900},  **MORN)
    assert not m({"time_below": 800},  **MORN)   # 800 is not < 800

def test_time_min():
    assert     m({"time_min": 800},    **MORN)   # 800 >= 800
    assert not m({"time_min": 900},    **MORN)

def test_time_max():
    assert     m({"time_max": 800},    **MORN)   # 800 <= 800
    assert not m({"time_max": 700},    **MORN)

def test_time_eq():
    assert     m({"time_eq": 800},     **MORN)
    assert not m({"time_eq": 900},     **MORN)

def test_time_window():
    # t>=800 t<=1000 should match t=800,900,1000 but not 700 or 1100
    rule = {"time_min": 800, "time_max": 1000}
    assert     m(rule, **{**MORN, "hour": 8})
    assert     m(rule, **{**MORN, "hour": 10})
    assert not m(rule, **{**MORN, "hour": 7})
    assert not m(rule, **{**MORN, "hour": 11})

def test_time_minutes():
    # SUN has hour=14, minute=30 -> 1430
    assert     m({"time_above": 1429})
    assert not m({"time_above": 1430})
    assert     m({"time_below": 1431})
    assert not m({"time_below": 1430})


# ── Combined conditions (AND semantics) ───────────────────────────────────────

def test_combined_sun_and_time():
    rule = {"azimuth_above": 185, "elevation_above": 5, "time_above": 1200}
    assert     m(rule)                           # az=200, el=10, h=14 → all pass
    assert not m(rule, azimuth=180)              # az fails
    assert not m(rule, elevation=3)              # el fails
    assert not m(rule, hour=10)                  # time fails
