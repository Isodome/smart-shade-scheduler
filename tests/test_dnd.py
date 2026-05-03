"""Tests for is_dnd_active() — time window logic."""
from datetime import time
from custom_components.smart_shades.logic import is_dnd_active


def dnd(start, end, now):
    return is_dnd_active(start, end, time(*[int(x) for x in now.split(":")]))


# ── Same-day window (e.g. 10:00–14:00) ───────────────────────────────────────

def test_inside_same_day_window():
    assert dnd("10:00:00", "14:00:00", "12:00")

def test_at_start_of_window():
    assert dnd("10:00:00", "14:00:00", "10:00")

def test_at_end_of_window():
    assert dnd("10:00:00", "14:00:00", "14:00")

def test_before_same_day_window():
    assert not dnd("10:00:00", "14:00:00", "09:59")

def test_after_same_day_window():
    assert not dnd("10:00:00", "14:00:00", "14:01")


# ── Overnight window (e.g. 22:00–07:00) ──────────────────────────────────────

def test_inside_overnight_window_evening():
    assert dnd("22:00:00", "07:00:00", "23:30")

def test_inside_overnight_window_morning():
    assert dnd("22:00:00", "07:00:00", "06:00")

def test_at_overnight_start():
    assert dnd("22:00:00", "07:00:00", "22:00")

def test_at_overnight_end():
    assert dnd("22:00:00", "07:00:00", "07:00")

def test_outside_overnight_window_midday():
    assert not dnd("22:00:00", "07:00:00", "12:00")

def test_just_before_overnight_start():
    assert not dnd("22:00:00", "07:00:00", "21:59")

def test_just_after_overnight_end():
    assert not dnd("22:00:00", "07:00:00", "07:01")


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_invalid_start_returns_false():
    assert not is_dnd_active("bad", "07:00:00", time(3, 0))

def test_invalid_end_returns_false():
    assert not is_dnd_active("22:00:00", "bad", time(3, 0))
