"""Tests for ShadeManager override detection logic.

Reproduces the transit-grace refresh bug: _control_shade always updates
_last_commanded.ts, so when sun.sun triggers evals every ~60 s (< TRANSIT_GRACE
of 90 s), cmd_age never exceeds TRANSIT_GRACE and the divergence check is
perpetually skipped — manual overrides are never detected.
"""
import asyncio
import sys
import types
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Extra HA stubs not covered by conftest.py ─────────────────────────────────

def _ensure_stub(name, **attrs):
    if name not in sys.modules:
        mod = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        sys.modules[name] = mod
    return sys.modules[name]

_ensure_stub("homeassistant.helpers.template", Template=MagicMock())
_ensure_stub("homeassistant.util")
_ensure_stub("homeassistant.util.dt", as_local=lambda dt: dt, now=MagicMock())

# ── Import under test ─────────────────────────────────────────────────────────

from custom_components.smart_shades.__init__ import ShadeManager  # noqa: E402
from custom_components.smart_shades.const import (  # noqa: E402
    CONF_RULES,
    CONF_TOLERANCE,
    CONF_CUSTOM_VARS,
    DEFAULT_TOLERANCE,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_COVER = "cover.blind_test"
_TARGET_POS = 50

_SIMPLE_RULES = [
    {
        "mode": "_fallback",
        "covers": [_COVER],
        "rules": [{"conditions": [], "action": {"position": _TARGET_POS}}],
    }
]


def _make_state(pos, tilt=None):
    state = MagicMock()
    state.state = str(pos)
    attrs = {"current_position": pos}
    if tilt is not None:
        attrs["current_tilt_position"] = tilt
    state.attributes = attrs
    return state


def _make_sun_state(az=180.0, el=30.0):
    state = MagicMock()
    state.attributes = {"azimuth": az, "elevation": el}
    return state


def _make_manager(cover_pos_fn):
    """Build a ShadeManager with a mock hass whose cover state is provided by cover_pos_fn()."""
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()

    def states_get(entity_id):
        if entity_id == _COVER:
            return _make_state(cover_pos_fn())
        if entity_id == "sun.sun":
            return _make_sun_state()
        return None

    hass.states = MagicMock()
    hass.states.get = states_get

    entry = MagicMock()
    entry.data = {}
    entry.options = {
        CONF_RULES: _SIMPLE_RULES,
        CONF_TOLERANCE: DEFAULT_TOLERANCE,
        CONF_CUSTOM_VARS: "",
    }

    mgr = ShadeManager(hass, entry)
    return mgr


# ── Tests ─────────────────────────────────────────────────────────────────────

T0 = datetime(2026, 5, 12, 14, 0, 0)


@pytest.mark.asyncio
async def test_override_detected_after_transit_grace():
    """Override IS detected when enough time passes between evals (> TRANSIT_GRACE)."""
    cover_pos = [_TARGET_POS]  # cover at target

    mgr = _make_manager(lambda: cover_pos[0])

    module = "custom_components.smart_shades.__init__"

    # Eval 1 at T0: cover at target, no last_commanded yet → _control_shade called, ts=T0
    with patch(f"{module}.dt_util") as mock_dt_util:
        mock_dt_util.now.return_value = T0
        await mgr._do_evaluate()

    assert _COVER in mgr._last_commanded
    assert _COVER not in mgr._overrides

    # User moves cover manually
    cover_pos[0] = 100

    # Eval 2 at T0 + 120s (> TRANSIT_GRACE=90s): divergence should be detected
    with patch(f"{module}.dt_util") as mock_dt_util:
        mock_dt_util.now.return_value = T0 + timedelta(seconds=120)
        await mgr._do_evaluate()

    assert _COVER in mgr._overrides, "Override should be detected after transit grace has passed"


@pytest.mark.asyncio
async def test_override_missed_due_to_transit_grace_refresh():
    """Reproduces the bug: rapid sun.sun evals (every 60 s) keep refreshing
    _last_commanded.ts, so cmd_age never exceeds TRANSIT_GRACE and the
    divergence check is never reached even after the user manually moves the cover."""
    cover_pos = [_TARGET_POS]

    mgr = _make_manager(lambda: cover_pos[0])

    module = "custom_components.smart_shades.__init__"

    # Eval 1 at T0: cover at target → _control_shade records ts=T0
    with patch(f"{module}.dt_util") as mock_dt_util:
        mock_dt_util.now.return_value = T0
        await mgr._do_evaluate()

    # Eval 2 at T0+60s (sun.sun change): cover still at target → ts refreshed to T0+60s
    with patch(f"{module}.dt_util") as mock_dt_util:
        mock_dt_util.now.return_value = T0 + timedelta(seconds=60)
        await mgr._do_evaluate()

    # User moves cover manually between eval 2 and eval 3
    cover_pos[0] = 100

    # Eval 3 at T0+120s (sun.sun change again): cmd_age = 120-60 = 60s < TRANSIT_GRACE(90)
    # → divergence check skipped → override NOT detected (the bug)
    with patch(f"{module}.dt_util") as mock_dt_util:
        mock_dt_util.now.return_value = T0 + timedelta(seconds=120)
        await mgr._do_evaluate()

    # With the fix, this assertion PASSES because ts is not refreshed
    assert _COVER in mgr._overrides, (
        "Divergence should be detected even with intermediate evals "
        "because transit grace should not be refreshed for same-target evals"
    )

@pytest.mark.asyncio
async def test_fast_mode_switch_sends_command_during_grace():
    """Verify that if the target changes during transit grace, a new command IS sent."""
    cover_pos = [_TARGET_POS]
    mgr = _make_manager(lambda: cover_pos[0])
    module = "custom_components.smart_shades.__init__"

    # 1. Eval at T0 -> records target=50, ts=T0
    with patch(f"{module}.dt_util") as mock_dt_util:
        mock_dt_util.now.return_value = T0
        await mgr._do_evaluate()
    
    assert mgr._last_commanded[_COVER]["p"] == 50
    assert mgr._last_commanded[_COVER]["ts"] == T0
    mgr.hass.services.async_call.reset_mock()

    # 2. Target changes to 0 (e.g. mode switch) at T0 + 30s (< 90s grace)
    # We must mock evaluate_rules to return a different target
    with patch(f"{module}.evaluate_rules") as mock_eval:
        mock_eval.return_value = {_COVER: {"p": 0, "t": None}}
        with patch(f"{module}.dt_util") as mock_dt_util:
            mock_dt_util.now.return_value = T0 + timedelta(seconds=30)
            await mgr._do_evaluate()
    
    # Assert: command was sent and ts updated
    assert mgr.hass.services.async_call.called, "Command should be sent even during grace if target changed"
    assert mgr._last_commanded[_COVER]["p"] == 0
    assert mgr._last_commanded[_COVER]["t"] is None
    assert mgr._last_commanded[_COVER]["ts"] == T0 + timedelta(seconds=30)


@pytest.mark.asyncio
async def test_stale_tilt_task_cancelled_on_mode_switch():
    """When mode switches to one with no tilt, any pending delayed tilt task must be cancelled."""
    loop = asyncio.get_event_loop()
    cover_pos = [50]
    mgr = _make_manager(lambda: cover_pos[0])
    # Make async_create_task use real asyncio tasks so cancel/done work correctly
    mgr.hass.async_create_task = loop.create_task
    module = "custom_components.smart_shades.__init__"

    # Eval 1: mode A returns pos=80 + tilt=30 → delayed tilt task is created
    with patch(f"{module}.evaluate_rules") as mock_eval, \
         patch(f"{module}.dt_util") as mock_dt:
        mock_dt.now.return_value = T0
        mock_eval.return_value = {_COVER: {"p": 80, "t": 30}}
        await mgr._do_evaluate()

    assert _COVER in mgr._tilt_tasks, "Delayed tilt task should have been created"
    stale_task = mgr._tilt_tasks[_COVER]
    assert not stale_task.done(), "Stale task should still be pending"

    # Eval 2: mode B returns pos=20, no tilt → stale tilt task must be cancelled
    with patch(f"{module}.evaluate_rules") as mock_eval, \
         patch(f"{module}.dt_util") as mock_dt:
        mock_dt.now.return_value = T0 + timedelta(seconds=5)
        mock_eval.return_value = {_COVER: {"p": 20, "t": None}}
        await mgr._do_evaluate()

    assert _COVER not in mgr._tilt_tasks, "Stale tilt task should have been removed"
    await asyncio.sleep(0)  # let event loop process the cancellation
    assert stale_task.cancelled(), "Stale tilt task should have been cancelled"
