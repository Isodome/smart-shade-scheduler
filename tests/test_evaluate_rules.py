"""Tests for fill_targets(), evaluate_rules() — priority order and first-match logic."""
from custom_components.smart_shades.logic import evaluate_rules

CTX = dict(azimuth=200.0, elevation=10.0, hour=14, minute=0)


def eval(groups, mode="NORMAL", **ctx_overrides):
    c = {**CTX, **ctx_overrides}
    time_hhmm = c["hour"] * 100 + c["minute"]
    return evaluate_rules(groups, mode, c["azimuth"], c["elevation"], time_hhmm)


# ── First-match-per-cover ─────────────────────────────────────────────────────

def test_first_rule_wins():
    groups = [
        {
            "mode": "NORMAL",
            "covers": ["cover.a"],
            "rules": [
                {"action": {"position": 0}},
                {"action": {"position": 50}},  # never reached
            ]
        }
    ]
    result = eval(groups)
    assert result["cover.a"]["p"] == 0


def test_second_rule_fills_unclaimed_cover():
    groups = [
        {
            "mode": "NORMAL",
            "covers": ["cover.a"],
            "rules": [{"action": {"position": 0}}]
        },
        {
            "mode": "NORMAL",
            "covers": ["cover.b"],
            "rules": [{"action": {"position": 50}}]
        }
    ]
    result = eval(groups)
    assert result["cover.a"]["p"] == 0
    assert result["cover.b"]["p"] == 50


def test_conditional_rule_skipped_when_unmet():
    groups = [
        {
            "mode": "NORMAL",
            "covers": ["cover.a"],
            "rules": [
                {"conditions": [{"var": "azimuth", "op": ">", "val": 250}], "action": {"position": 0}},
                {"action": {"position": 100}},  # catch-all fallback
            ]
        }
    ]
    result = eval(groups, azimuth=200)   # az=200, not > 250 → first rule skipped
    assert result["cover.a"]["p"] == 100


# ── Three-pass evaluation ─────────────────────────────────────────────────────

def test_priority_wins_over_mode():
    groups = [
        {
            "mode": "_priority",
            "covers": ["cover.a"],
            "rules": [{"action": {"position": 100}}]
        },
        {
            "mode": "NORMAL",
            "covers": ["cover.a"],
            "rules": [{"action": {"position": 0}}]
        }
    ]
    result = eval(groups, mode="NORMAL")
    assert result["cover.a"]["p"] == 100   # priority claimed it first


def test_mode_wins_over_fallback():
    groups = [
        {
            "mode": "NORMAL",
            "covers": ["cover.a"],
            "rules": [{"action": {"position": 50}}]
        },
        {
            "mode": "_fallback",
            "covers": ["cover.a"],
            "rules": [{"action": {"position": 0}}]
        }
    ]
    result = eval(groups, mode="NORMAL")
    assert result["cover.a"]["p"] == 50   # mode claimed it; fallback skipped


def test_fallback_fills_unclaimed_covers():
    groups = [
        {
            "mode": "NORMAL",
            "covers": ["cover.a"],
            "rules": [{"action": {"position": 50}}]
        },
        {
            "mode": "_fallback",
            "covers": ["cover.b"],
            "rules": [{"action": {"position": 0}}]
        }
    ]
    result = eval(groups, mode="NORMAL")
    assert result["cover.a"]["p"] == 50
    assert result["cover.b"]["p"] == 0   # not claimed by NORMAL → fallback fires


def test_priority_does_not_block_fallback_for_other_covers():
    groups = [
        {
            "mode": "_priority",
            "covers": ["cover.a"],
            "rules": [{"action": {"position": 100}}]
        },
        {
            "mode": "_fallback",
            "covers": ["cover.b"],
            "rules": [{"action": {"position": 0}}]
        }
    ]
    result = eval(groups, mode="NORMAL")
    assert result["cover.a"]["p"] == 100
    assert result["cover.b"]["p"] == 0


def test_no_mode_match_uses_fallback():
    groups = [
        {
            "mode": "KUEHLEN",
            "covers": ["cover.a"],
            "rules": [{"action": {"position": 0}}]
        },
        {
            "mode": "_fallback",
            "covers": ["cover.a"],
            "rules": [{"action": {"position": 100}}]
        }
    ]
    result = eval(groups, mode="NORMAL")   # NORMAL has no rules; fallback fires
    assert result["cover.a"]["p"] == 100


def test_unknown_mode_uses_fallback():
    groups = [
        {
            "mode": "_fallback",
            "covers": ["cover.a"],
            "rules": [{"action": {"position": 75}}]
        }
    ]
    result = eval(groups, mode="NONEXISTENT")
    assert result["cover.a"]["p"] == 75


def test_none_mode_skips_mode_pass():
    groups = [
        {
            "mode": "_priority",
            "covers": ["cover.a"],
            "rules": [{"action": {"position": 100}}]
        },
        {
            "mode": "_fallback",
            "covers": ["cover.b"],
            "rules": [{"action": {"position": 0}}]
        }
    ]
    result = eval(groups, mode=None)
    assert result["cover.a"]["p"] == 100
    assert result["cover.b"]["p"] == 0


# ── Position and tilt ─────────────────────────────────────────────────────────

def test_position_and_tilt_both_stored():
    groups = [{"mode": "NORMAL", "covers": ["cover.a"], "rules": [{"action": {"position": 30, "tilt": 75}}]}]
    result = eval(groups)
    assert result["cover.a"] == {"p": 30, "t": 75}


def test_position_only():
    groups = [{"mode": "NORMAL", "covers": ["cover.a"], "rules": [{"action": {"position": 0}}]}]
    result = eval(groups)
    assert result["cover.a"] == {"p": 0, "t": None}


def test_tilt_only():
    groups = [{"mode": "NORMAL", "covers": ["cover.a"], "rules": [{"action": {"tilt": 100}}]}]
    result = eval(groups)
    assert result["cover.a"] == {"p": None, "t": 100}


# ── Real-world KUEHLEN scenario ───────────────────────────────────────────────

def test_kuehlen_southwest_scenario():
    groups = [
        # priority: retract awnings at night
        {
            "mode": "_priority",
            "covers": ["cover.markise"],
            "rules": [{"conditions": [{"var": "elevation", "op": "<", "val": 0}], "action": {"position": 100}}]
        },
        # KUEHLEN: west sun → balkon awnings at 60%
        {
            "mode": "KUEHLEN",
            "covers": ["cover.markise"],
            "rules": [{"conditions": [{"var": "azimuth", "op": ">", "val": 200}, {"var": "elevation", "op": ">", "val": 5}], "action": {"position": 60}}]
        },
        # KUEHLEN: south sun → main storen closed
        {
            "mode": "KUEHLEN",
            "covers": ["cover.stor_wz"],
            "rules": [{"conditions": [{"var": "azimuth", "op": ">", "val": 185}, {"var": "elevation", "op": ">", "val": 5}], "action": {"position": 0, "tilt": 0}}]
        },
        # fallback: open at night
        {
            "mode": "_fallback",
            "covers": ["cover.markise"],
            "rules": [{"conditions": [{"var": "elevation", "op": "<", "val": 0}], "action": {"position": 100}}]
        }
    ]

    # Afternoon, az=210, el=15 → KUEHLEN west rule fires for markise
    r = eval(groups, mode="KUEHLEN", azimuth=210, elevation=15, hour=15)
    assert r["cover.markise"]["p"] == 60
    assert r["cover.stor_wz"]["p"] == 0

    # Low sun (el=3) → azimuth_above:200 + elevation_above:5 fails → no KUEHLEN match
    # fallback also has elevation_below:0 which fails at el=3 → cover not in result
    r = eval(groups, mode="KUEHLEN", azimuth=210, elevation=3, hour=18)
    assert "cover.markise" not in r

    # Night (el=-5) → priority claims markise → position 100
    r = eval(groups, mode="KUEHLEN", azimuth=0, elevation=-5, hour=22)
    assert r["cover.markise"]["p"] == 100
