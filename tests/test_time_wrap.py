"""Tests for midnight time wrap logic in rule_matches()."""
from custom_components.smart_shades.logic import rule_matches

def _vals(hour, minute):
    return {"t": hour * 100 + minute}

def test_time_wrap_at_midnight():
    # Threshold at 00:00 (midnight)
    # 23:59 -> 00:01 crosses 00:00
    prev = _vals(23, 59)
    cur = _vals(0, 1)
    conds = [{"var": "t", "op": "=^", "val": 0}]
    assert rule_matches(conds, cur, prev)

def test_time_wrap_after_midnight():
    # Threshold at 00:05
    # 23:55 -> 00:10 crosses 00:05
    prev = _vals(23, 55)
    cur = _vals(0, 10)
    conds = [{"var": "t", "op": "=^", "val": 5}]
    assert rule_matches(conds, cur, prev)

def test_time_no_wrap_no_cross():
    # Threshold at 00:05
    # 23:55 -> 00:02 does NOT cross 00:05
    prev = _vals(23, 55)
    cur = _vals(0, 2)
    conds = [{"var": "t", "op": "=^", "val": 5}]
    assert not rule_matches(conds, cur, prev)

def test_time_wrap_boundary_landing():
    # Landing exactly on the threshold after a wrap
    prev = _vals(23, 50)
    cur = _vals(0, 5)
    conds = [{"var": "t", "op": "=^", "val": 5}]
    assert rule_matches(conds, cur, prev)

def test_time_wrap_just_before_midnight():
    # Threshold at 23:58
    # 23:55 -> 00:05 crosses 23:58
    prev = _vals(23, 55)
    cur = _vals(0, 5)
    conds = [{"var": "t", "op": "=^", "val": 2358}]
    assert rule_matches(conds, cur, prev)

def test_time_wrap_undirected():
    # undirected "=" operator
    prev = _vals(23, 59)
    cur = _vals(0, 1)
    conds = [{"var": "t", "op": "=", "val": 0}]
    assert rule_matches(conds, cur, prev)

