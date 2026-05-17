"""Tests for vars.py — pure helper functions."""
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from custom_components.smart_shades.vars import (
    _coerce_state,
    _infer_type_from_raw,
    normalize_built_ins,
)


# ── _coerce_state ─────────────────────────────────────────────────────────────

def test_coerce_numeric():
    assert _coerce_state("42")   == 42.0
    assert _coerce_state("3.14") == 3.14
    assert _coerce_state("-5")   == -5.0

def test_coerce_hhmm():
    assert _coerce_state("8:30")     == 830.0
    assert _coerce_state("22:00")    == 2200.0
    assert _coerce_state("14:30:00") == 1430.0

def test_coerce_bool_strings():
    for s in ("on", "ON", "True", "true", "yes"):
        assert _coerce_state(s) == 1.0, f"Expected 1.0 for {s!r}"
    for s in ("off", "OFF", "False", "false", "no"):
        assert _coerce_state(s) == 0.0, f"Expected 0.0 for {s!r}"

def test_coerce_unknown_returns_none():
    assert _coerce_state("unavailable") is None
    assert _coerce_state("unknown")     is None
    assert _coerce_state("garbage")     is None

def test_coerce_iso_datetime_naive():
    # Naive datetime — no dt_util.as_local call
    assert _coerce_state("2026-05-17T14:30:00") == 1430.0
    assert _coerce_state("2026-05-17T08:05:00") == 805.0

def test_coerce_iso_datetime_tz_aware():
    # UTC 10:00 → local 12:00 (UTC+2); as_local does the conversion
    local_dt = datetime(2026, 5, 17, 12, 0, tzinfo=timezone(timedelta(hours=2)))
    with patch("custom_components.smart_shades.vars.dt_util") as mock_dt:
        mock_dt.as_local.return_value = local_dt
        result = _coerce_state("2026-05-17T10:00:00+00:00")
    assert result == 1200.0
    mock_dt.as_local.assert_called_once()


# ── _infer_type_from_raw ──────────────────────────────────────────────────────

def test_infer_none_is_number():
    assert _infer_type_from_raw(None) == "number"

def test_infer_bool_strings():
    for s in ("on", "off", "true", "false", "yes", "no", "ON", "True", "False"):
        assert _infer_type_from_raw(s) == "bool", f"Expected bool for {s!r}"

def test_infer_hhmm_is_time():
    assert _infer_type_from_raw("8:30")  == "time"
    assert _infer_type_from_raw("22:00") == "time"

def test_infer_iso_datetime_is_time():
    assert _infer_type_from_raw("2026-05-17T14:30:00")       == "time"
    assert _infer_type_from_raw("2026-05-17T14:30:00+00:00") == "time"

def test_infer_numeric_is_number():
    assert _infer_type_from_raw("42")   == "number"
    assert _infer_type_from_raw("3.14") == "number"
    assert _infer_type_from_raw("1500") == "number"

def test_infer_unknown_is_number():
    assert _infer_type_from_raw("unavailable") == "number"
    assert _infer_type_from_raw("garbage")     == "number"


# ── normalize_built_ins ───────────────────────────────────────────────────────

_SAMPLE_BUILT_INS = [
    {"short": "az", "long": "azimuth",   "type": "number", "resolver": lambda h, n: 180.0},
    {"short": "t",  "long": "time",      "type": "time",   "resolver": lambda h, n: 1430.0},
    {"short": "mo", "long": "month",     "type": "number", "resolver": lambda h, n: 5.0},
]

def test_normalize_shape():
    specs = normalize_built_ins(_SAMPLE_BUILT_INS)
    assert set(specs) == {"az", "t", "mo"}
    for spec in specs.values():
        assert callable(spec["resolver"])
        assert callable(spec["type_fn"])

def test_normalize_type_fn_captures_correctly():
    # Each lambda must return its own type — guards against late-binding closure bug
    specs = normalize_built_ins(_SAMPLE_BUILT_INS)
    assert specs["az"]["type_fn"]() == "number"
    assert specs["t"]["type_fn"]()  == "time"
    assert specs["mo"]["type_fn"]() == "number"

def test_normalize_resolver_passthrough():
    specs = normalize_built_ins(_SAMPLE_BUILT_INS)
    assert specs["az"]["resolver"](None, None) == 180.0
    assert specs["t"]["resolver"](None, None)  == 1430.0
