"""Tests for rule_matches() — all condition operators."""
import pytest
from custom_components.smart_shades.logic import rule_matches

SUN  = dict(azimuth=200.0, elevation=10.0, hour=14, minute=30)
MORN = dict(azimuth=90.0,  elevation=20.0, hour=8,  minute=0)


def m(rule, **kwargs):
    ctx = {**SUN, **kwargs}
    return rule_matches(rule, ctx["azimuth"], ctx["elevation"], ctx["hour"], ctx["minute"])


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


# ── Hour ──────────────────────────────────────────────────────────────────────

def test_hour_above():
    assert not m({"hour_above": 8}, **MORN)   # h=8, 8 > 8 is False
    assert     m({"hour_above": 7}, **MORN)   # h=8, 8 > 7 is True
    assert not m({"hour_above": 9}, **MORN)   # h=8, 8 > 9 is False

def test_hour_below():
    assert     m({"hour_below": 9},  **MORN)
    assert not m({"hour_below": 8},  **MORN)   # 8 is not < 8

def test_hour_min():
    assert     m({"hour_min": 8},    **MORN)   # 8 >= 8
    assert not m({"hour_min": 9},    **MORN)

def test_hour_max():
    assert     m({"hour_max": 8},    **MORN)   # 8 <= 8
    assert not m({"hour_max": 7},    **MORN)

def test_hour_eq():
    assert     m({"hour_eq": 8},     **MORN)
    assert not m({"hour_eq": 9},     **MORN)

def test_hour_window():
    # h>=8 h<=10 should match h=8,9,10 but not 7 or 11
    rule = {"hour_min": 8, "hour_max": 10}
    assert     m(rule, **{**MORN, "hour": 8})
    assert     m(rule, **{**MORN, "hour": 10})
    assert not m(rule, **{**MORN, "hour": 7})
    assert not m(rule, **{**MORN, "hour": 11})


# ── Minute ────────────────────────────────────────────────────────────────────

def test_minute_above():
    assert     m({"minute_above": 29})
    assert not m({"minute_above": 30})   # 30 is not > 30

def test_minute_below():
    assert     m({"minute_below": 31})
    assert not m({"minute_below": 30})   # 30 is not < 30

def test_minute_min():
    assert     m({"minute_min": 30})    # 30 >= 30
    assert not m({"minute_min": 31})

def test_minute_max():
    assert     m({"minute_max": 30})    # 30 <= 30
    assert not m({"minute_max": 29})

def test_minute_eq():
    assert     m({"minute_eq": 30})
    assert not m({"minute_eq": 0})


# ── Combined conditions (AND semantics) ───────────────────────────────────────

def test_combined_sun_and_time():
    rule = {"azimuth_above": 185, "elevation_above": 5, "hour_above": 12}
    assert     m(rule)                           # az=200, el=10, h=14 → all pass
    assert not m(rule, azimuth=180)              # az fails
    assert not m(rule, elevation=3)              # el fails
    assert not m(rule, hour=10)                  # h fails
