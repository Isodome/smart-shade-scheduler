"""Tests for fill_targets(), evaluate_rules() — priority order and first-match logic."""
from custom_components.smart_shades.logic import evaluate_rules

CTX = dict(azimuth=200.0, elevation=10.0, hour=14, minute=0)


def ev(groups, mode="NORMAL", block_fallback=False, presence=None, workday=None, **ctx_overrides):
    c = {**CTX, **ctx_overrides}
    time_hhmm = c["hour"] * 100 + c["minute"]
    return evaluate_rules(groups, mode, c["azimuth"], c["elevation"], time_hhmm,
                          block_fallback=block_fallback, presence=presence, workday=workday)

# backward-compat alias used by existing tests
eval = ev


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
            "mode": "COOLING",
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


# ── Real-world COOLING scenario ───────────────────────────────────────────────

def test_cooling_southwest_scenario():
    groups = [
        # priority: retract awnings at night
        {
            "mode": "_priority",
            "covers": ["cover.awning"],
            "rules": [{"conditions": [{"var": "elevation", "op": "<", "val": 0}], "action": {"position": 100}}]
        },
        # COOLING: west sun → balkon awnings at 60%
        {
            "mode": "COOLING",
            "covers": ["cover.awning"],
            "rules": [{"conditions": [{"var": "azimuth", "op": ">", "val": 200}, {"var": "elevation", "op": ">", "val": 5}], "action": {"position": 60}}]
        },
        # COOLING: south sun → main blind closed
        {
            "mode": "COOLING",
            "covers": ["cover.blind_living"],
            "rules": [{"conditions": [{"var": "azimuth", "op": ">", "val": 185}, {"var": "elevation", "op": ">", "val": 5}], "action": {"position": 0, "tilt": 0}}]
        },
        # fallback: open at night
        {
            "mode": "_fallback",
            "covers": ["cover.awning"],
            "rules": [{"conditions": [{"var": "elevation", "op": "<", "val": 0}], "action": {"position": 100}}]
        }
    ]

    # Afternoon, az=210, el=15 → COOLING west rule fires for awning
    r = eval(groups, mode="COOLING", azimuth=210, elevation=15, hour=15)
    assert r["cover.awning"]["p"] == 60
    assert r["cover.blind_living"]["p"] == 0

    # Low sun (el=3) → azimuth_above:200 + elevation_above:5 fails → no COOLING match
    # fallback also has elevation_below:0 which fails at el=3 → cover not in result
    r = eval(groups, mode="COOLING", azimuth=210, elevation=3, hour=18)
    assert "cover.awning" not in r

    # Night (el=-5) → priority claims awning → position 100
    r = eval(groups, mode="COOLING", azimuth=0, elevation=-5, hour=22)
    assert r["cover.awning"]["p"] == 100


# ── block_fallback ────────────────────────────────────────────────────────────

def test_block_fallback_suppresses_default_pass():
    groups = [
        {"mode": "RAIN",      "covers": ["cover.a"], "rules": [{"conditions": [], "action": {"position": 100}}]},
        {"mode": "_fallback", "covers": ["cover.b"], "rules": [{"conditions": [], "action": {"position": 50}}]},
    ]
    # Without block_fallback: fallback fires for cover.b
    r = ev(groups, mode="RAIN")
    assert r["cover.b"]["p"] == 50

    # With block_fallback: cover.b is untouched
    r = ev(groups, mode="RAIN", block_fallback=True)
    assert "cover.b" not in r

def test_block_fallback_does_not_suppress_priority():
    groups = [
        {"mode": "_priority", "covers": ["cover.a"], "rules": [{"conditions": [], "action": {"position": 0}}]},
        {"mode": "_fallback", "covers": ["cover.b"], "rules": [{"conditions": [], "action": {"position": 50}}]},
    ]
    r = ev(groups, mode="RAIN", block_fallback=True)
    assert r["cover.a"]["p"] == 0    # priority always runs
    assert "cover.b" not in r        # fallback blocked


# ── Multiple rules within a group (first-match-wins) ─────────────────────────

def test_first_matching_rule_in_group_wins():
    groups = [{"mode": "NORMAL", "covers": ["cover.a"], "rules": [
        {"conditions": [{"var": "azimuth", "op": ">", "val": 250}], "action": {"position": 0}},
        {"conditions": [],                                            "action": {"position": 100}},
    ]}]
    # az=200 → first rule fails, catch-all fires
    r = ev(groups, mode="NORMAL", azimuth=200)
    assert r["cover.a"]["p"] == 100

    # az=260 → first rule fires, catch-all never reached
    r = ev(groups, mode="NORMAL", azimuth=260)
    assert r["cover.a"]["p"] == 0

def test_rule_with_no_valid_action_is_skipped():
    # A rule that matches but has no position or tilt should be skipped,
    # allowing the next rule to fire.
    groups = [{"mode": "NORMAL", "covers": ["cover.a"], "rules": [
        {"conditions": [], "action": {}},           # valid conditions, but empty action
        {"conditions": [], "action": {"position": 75}},
    ]}]
    r = ev(groups, mode="NORMAL")
    assert r["cover.a"]["p"] == 75

def test_cover_claimed_by_first_group_cannot_be_overwritten():
    groups = [
        {"mode": "NORMAL", "covers": ["cover.a"], "rules": [{"conditions": [], "action": {"position": 0}}]},
        {"mode": "NORMAL", "covers": ["cover.a"], "rules": [{"conditions": [], "action": {"position": 100}}]},
    ]
    r = ev(groups, mode="NORMAL")
    assert r["cover.a"]["p"] == 0   # first group wins, second cannot overwrite


# ── Presence and workday in evaluation ────────────────────────────────────────

def test_presence_home_gates_rule():
    groups = [{"mode": "NORMAL", "covers": ["cover.a"], "rules": [
        {"conditions": [{"var": "presence", "op": "==", "val": "home"}], "action": {"position": 50}},
        {"conditions": [],                                                 "action": {"position": 100}},
    ]}]
    assert ev(groups, presence=True) ["cover.a"]["p"] == 50    # home → first rule
    assert ev(groups, presence=False)["cover.a"]["p"] == 100   # away → falls through to catch-all
    assert ev(groups, presence=None) ["cover.a"]["p"] == 100   # unknown → fails, catch-all

def test_workday_gates_rule():
    groups = [{"mode": "NORMAL", "covers": ["cover.a"], "rules": [
        {"conditions": [{"var": "workday", "op": "==", "val": "work"}],   "action": {"position": 0}},
        {"conditions": [{"var": "workday", "op": "==", "val": "nowork"}], "action": {"position": 100}},
    ]}]
    assert ev(groups, workday=True) ["cover.a"]["p"] == 0      # workday
    assert ev(groups, workday=False)["cover.a"]["p"] == 100    # day off
