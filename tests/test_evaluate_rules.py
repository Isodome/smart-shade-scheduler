"""Tests for fill_targets(), evaluate_rules() — priority order and first-match logic."""
from custom_components.smart_shades.logic import evaluate_rules, fill_targets

CTX = dict(azimuth=200.0, elevation=10.0, hour=14, minute=0)


def eval(rules, mode="NORMAL", **ctx_overrides):
    c = {**CTX, **ctx_overrides}
    return evaluate_rules(rules, mode, c["azimuth"], c["elevation"], c["hour"], c["minute"])


# ── First-match-per-cover ─────────────────────────────────────────────────────

def test_first_rule_wins():
    rules = [
        {"mode": "NORMAL", "covers": ["cover.a"], "position": 0},
        {"mode": "NORMAL", "covers": ["cover.a"], "position": 50},  # never reached
    ]
    result = eval(rules)
    assert result["cover.a"]["p"] == 0


def test_second_rule_fills_unclaimed_cover():
    rules = [
        {"mode": "NORMAL", "covers": ["cover.a"], "position": 0},
        {"mode": "NORMAL", "covers": ["cover.b"], "position": 50},
    ]
    result = eval(rules)
    assert result["cover.a"]["p"] == 0
    assert result["cover.b"]["p"] == 50


def test_conditional_rule_skipped_when_unmet():
    rules = [
        {"mode": "NORMAL", "covers": ["cover.a"], "azimuth_above": 250, "position": 0},
        {"mode": "NORMAL", "covers": ["cover.a"], "position": 100},  # catch-all fallback
    ]
    result = eval(rules, azimuth=200)   # az=200, not > 250 → first rule skipped
    assert result["cover.a"]["p"] == 100


# ── Three-pass evaluation ─────────────────────────────────────────────────────

def test_priority_wins_over_mode():
    rules = [
        {"mode": "_priority", "covers": ["cover.a"], "position": 100},
        {"mode": "NORMAL",    "covers": ["cover.a"], "position": 0},
    ]
    result = eval(rules, mode="NORMAL")
    assert result["cover.a"]["p"] == 100   # priority claimed it first


def test_mode_wins_over_fallback():
    rules = [
        {"mode": "NORMAL",    "covers": ["cover.a"], "position": 50},
        {"mode": "_fallback", "covers": ["cover.a"], "position": 0},
    ]
    result = eval(rules, mode="NORMAL")
    assert result["cover.a"]["p"] == 50   # mode claimed it; fallback skipped


def test_fallback_fills_unclaimed_covers():
    rules = [
        {"mode": "NORMAL",    "covers": ["cover.a"], "position": 50},
        {"mode": "_fallback", "covers": ["cover.b"], "position": 0},
    ]
    result = eval(rules, mode="NORMAL")
    assert result["cover.a"]["p"] == 50
    assert result["cover.b"]["p"] == 0   # not claimed by NORMAL → fallback fires


def test_priority_does_not_block_fallback_for_other_covers():
    rules = [
        {"mode": "_priority", "covers": ["cover.a"], "position": 100},
        {"mode": "_fallback", "covers": ["cover.b"], "position": 0},
    ]
    result = eval(rules, mode="NORMAL")
    assert result["cover.a"]["p"] == 100
    assert result["cover.b"]["p"] == 0


def test_no_mode_match_uses_fallback():
    rules = [
        {"mode": "KUEHLEN",   "covers": ["cover.a"], "position": 0},
        {"mode": "_fallback", "covers": ["cover.a"], "position": 100},
    ]
    result = eval(rules, mode="NORMAL")   # NORMAL has no rules; fallback fires
    assert result["cover.a"]["p"] == 100


def test_unknown_mode_uses_fallback():
    rules = [
        {"mode": "_fallback", "covers": ["cover.a"], "position": 75},
    ]
    result = eval(rules, mode="NONEXISTENT")
    assert result["cover.a"]["p"] == 75


def test_none_mode_skips_mode_pass():
    rules = [
        {"mode": "_priority", "covers": ["cover.a"], "position": 100},
        {"mode": "_fallback", "covers": ["cover.b"], "position": 0},
    ]
    result = eval(rules, mode=None)
    assert result["cover.a"]["p"] == 100
    assert result["cover.b"]["p"] == 0


# ── Position and tilt ─────────────────────────────────────────────────────────

def test_position_and_tilt_both_stored():
    rules = [{"mode": "NORMAL", "covers": ["cover.a"], "position": 30, "tilt": 75}]
    result = eval(rules)
    assert result["cover.a"] == {"p": 30, "t": 75}


def test_position_only():
    rules = [{"mode": "NORMAL", "covers": ["cover.a"], "position": 0}]
    result = eval(rules)
    assert result["cover.a"] == {"p": 0, "t": None}


def test_tilt_only():
    rules = [{"mode": "NORMAL", "covers": ["cover.a"], "tilt": 100}]
    result = eval(rules)
    assert result["cover.a"] == {"p": None, "t": 100}


# ── Real-world KUEHLEN scenario ───────────────────────────────────────────────

def test_kuehlen_southwest_scenario():
    rules = [
        # priority: retract awnings at night
        {"mode": "_priority", "covers": ["cover.markise"], "elevation_below": 0, "position": 100},
        # KUEHLEN: west sun → balkon awnings at 60%
        {"mode": "KUEHLEN", "covers": ["cover.markise"], "azimuth_above": 200, "elevation_above": 5, "position": 60},
        # KUEHLEN: south sun → main storen closed
        {"mode": "KUEHLEN", "covers": ["cover.stor_wz"], "azimuth_above": 185, "elevation_above": 5, "position": 0, "tilt": 0},
        # fallback: open at night
        {"mode": "_fallback", "covers": ["cover.markise"], "elevation_below": 0, "position": 100},
    ]

    # Afternoon, az=210, el=15 → KUEHLEN west rule fires for markise
    r = eval(rules, mode="KUEHLEN", azimuth=210, elevation=15, hour=15)
    assert r["cover.markise"]["p"] == 60
    assert r["cover.stor_wz"]["p"] == 0

    # Low sun (el=3) → azimuth_above:200 + elevation_above:5 fails → no KUEHLEN match
    # fallback also has elevation_below:0 which fails at el=3 → cover not in result
    r = eval(rules, mode="KUEHLEN", azimuth=210, elevation=3, hour=18)
    assert "cover.markise" not in r

    # Night (el=-5) → priority claims markise → position 100
    r = eval(rules, mode="KUEHLEN", azimuth=0, elevation=-5, hour=22)
    assert r["cover.markise"]["p"] == 100
