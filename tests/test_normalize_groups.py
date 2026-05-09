"""Tests for normalize_groups() — old→new rule format migration."""
from custom_components.smart_shades.logic import normalize_groups


# ── Already flat (new format) — pass through unchanged ────────────────────────

def test_flat_group_is_unchanged():
    groups = [{"mode": "NORMAL", "covers": ["cover.a"], "conditions": [], "action": {"position": 100}}]
    assert normalize_groups(groups) == groups

def test_multiple_flat_groups_unchanged():
    groups = [
        {"mode": "NORMAL",    "covers": ["cover.a"], "conditions": [], "action": {"position": 100}},
        {"mode": "_fallback", "covers": ["cover.b"], "conditions": [], "action": {"position": 0}},
    ]
    assert normalize_groups(groups) == groups


# ── Old nested format — expand to flat ────────────────────────────────────────

def test_single_rule_group_expanded():
    groups = [{"mode": "NORMAL", "covers": ["cover.a"], "rules": [
        {"conditions": [{"var": "azimuth", "op": ">", "val": 150}], "action": {"position": 50}},
    ]}]
    result = normalize_groups(groups)
    assert len(result) == 1
    assert result[0]["mode"] == "NORMAL"
    assert result[0]["covers"] == ["cover.a"]
    assert result[0]["conditions"] == [{"var": "azimuth", "op": ">", "val": 150}]
    assert result[0]["action"] == {"position": 50}
    assert "rules" not in result[0]

def test_multi_rule_group_expands_to_multiple_flat_groups():
    groups = [{"mode": "COOLING", "covers": ["cover.a", "cover.b"], "rules": [
        {"conditions": [{"var": "elevation", "op": ">", "val": 5}], "action": {"position": 0}},
        {"conditions": [],                                            "action": {"position": 100}},
    ]}]
    result = normalize_groups(groups)
    assert len(result) == 2
    # Both inherit the same covers and mode
    assert result[0]["covers"] == ["cover.a", "cover.b"]
    assert result[1]["covers"] == ["cover.a", "cover.b"]
    assert result[0]["mode"] == "COOLING"
    assert result[1]["mode"] == "COOLING"
    # But get separate conditions and actions
    assert result[0]["conditions"] == [{"var": "elevation", "op": ">", "val": 5}]
    assert result[0]["action"] == {"position": 0}
    assert result[1]["conditions"] == []
    assert result[1]["action"] == {"position": 100}


# ── Mixed input — flat and nested groups together ─────────────────────────────

def test_mixed_flat_and_nested():
    groups = [
        {"mode": "NORMAL",    "covers": ["cover.a"], "conditions": [], "action": {"position": 100}},
        {"mode": "_fallback", "covers": ["cover.b"], "rules": [
            {"conditions": [], "action": {"position": 50}},
        ]},
    ]
    result = normalize_groups(groups)
    assert len(result) == 2
    assert result[0] == groups[0]        # flat passed through
    assert result[1]["conditions"] == []  # nested expanded
    assert result[1]["action"] == {"position": 50}


# ── Idempotency ───────────────────────────────────────────────────────────────

def test_normalizing_already_normalized_output_is_idempotent():
    groups = [{"mode": "NORMAL", "covers": ["cover.a"], "rules": [
        {"conditions": [], "action": {"position": 100}},
    ]}]
    once  = normalize_groups(groups)
    twice = normalize_groups(once)
    assert once == twice
