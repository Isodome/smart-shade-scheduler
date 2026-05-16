"""Smart Shade Scheduler — core integration."""

import asyncio
import logging
import re as _re
from datetime import datetime, time, timedelta

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .logic import evaluate_rules, fill_targets, rule_matches
from .const import (
    BUILT_IN_VARS,
    CONF_CUSTOM_VARS,
    CONF_ARMED_ENTITY,
    CONF_MODE_CONFIG,
    CONF_MODE_ENTITY,
    CONF_OVERRIDE_DURATION,
    CONF_OVERRIDE_DURATION_ENTITY,
    CONF_RULES,
    CONF_TILT_DELAY,
    CONF_TOLERANCE,
    CONF_TRANSIT_GRACE,
    DEFAULT_OVERRIDE_DURATION,
    DEFAULT_TILT_DELAY,
    DEFAULT_TOLERANCE,
    DEFAULT_TRANSIT_GRACE,
    DOMAIN,
    FALLBACK_MODE,
    PRIORITY_MODE,
    SCAN_INTERVAL_MINUTES,
    EVALUATION_LOW_PRIO_COOLDOWN,
)



def _coerce_state(state_str: str) -> float | None:
    """Coerce an entity state string to float for use as a condition variable."""
    # ISO datetime with timezone → HHMM in local time
    try:
        dt = datetime.fromisoformat(state_str)
        if dt.tzinfo is not None:
            dt = dt_util.as_local(dt)
        return float(dt.hour * 100 + dt.minute)
    except (ValueError, TypeError, AttributeError):
        pass
    # HH:MM or HH:MM:SS
    m = _re.match(r"^(\d{1,2}):(\d{2})", state_str)
    if m:
        return float(int(m.group(1)) * 100 + int(m.group(2)))
    # Numeric string
    try:
        return float(state_str)
    except (ValueError, TypeError):
        pass
    # on / off
    low = state_str.lower()
    if low == "on":  return 1.0
    if low == "off": return 0.0
    return None

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    """Set up Smart Shade Scheduler from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    manager = ShadeManager(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = manager
    await manager.async_init()

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    # One-time domain-level setup (panel + WS commands + service)
    if not hass.data[DOMAIN].get("_panel"):
        try:
            from . import panel as _panel
            await _panel.async_setup(hass)
            hass.data[DOMAIN]["_panel"] = True
        except Exception:
            _LOGGER.exception("Failed to set up sidebar panel (non-fatal)")

    # Register service once per domain (guard against multiple entries)
    if not hass.services.has_service(DOMAIN, "clear_overrides"):

        async def _handle_clear_overrides(call):
            entity_id = call.data.get("entity_id")
            for m in hass.data.get(DOMAIN, {}).values():
                if isinstance(m, ShadeManager):
                    m.clear_overrides(entity_id)

        hass.services.async_register(
            DOMAIN, "clear_overrides", _handle_clear_overrides
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    manager: ShadeManager | None = hass.data[DOMAIN].pop(entry.entry_id, None)
    if manager:
        manager.unload()

    # Tear down domain-level things when the last entry is gone
    remaining = [
        v for v in hass.data.get(DOMAIN, {}).values()
        if isinstance(v, ShadeManager)
    ]
    if not remaining:
        hass.services.async_remove(DOMAIN, "clear_overrides")
        from . import panel as _panel
        _panel.async_unload(hass)
        hass.data[DOMAIN].pop("_panel", None)

    return True


@callback
def _async_options_updated(hass: HomeAssistant, entry) -> None:
    """Re-init listeners and immediately apply the new rules."""
    manager: ShadeManager | None = hass.data[DOMAIN].get(entry.entry_id)
    if manager:
        manager._custom_resolvers = None
        manager._TRANSIT_GRACE = entry.options.get(
            CONF_TRANSIT_GRACE, DEFAULT_TRANSIT_GRACE
        )
        manager.reinit_mode_listener()
        manager.reinit_armed_listener()
        manager.async_schedule_evaluation(high_priority=True)


# ---------------------------------------------------------------------------

class ShadeManager:
    """Manages all shade rules and override state for one config entry."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self.entry = entry

        self._last_commanded: dict[str, dict] = {}       # entity_id → {p, t, ts}
        self._overrides: dict[str, datetime] = {}
        
        # Debouncing / Rate-limiting state
        self._last_low_prio_eval: datetime | None = None
        self._eval_task: asyncio.Task | None = None
        self._needs_reeval = False
        self._next_eval_is_high_prio = False

        # Seconds after a command during which divergence checks are suppressed
        # (cover may still be travelling to its commanded position)
        self._TRANSIT_GRACE = entry.options.get(
            CONF_TRANSIT_GRACE, DEFAULT_TRANSIT_GRACE
        )

        self._prev_vals: dict | None = None
        self._var_values: dict[str, float | None] = {}   # built-ins + custom, last eval
        self._custom_resolvers: dict | None = None

        self._unsub: list = []
        self._mode_unsub = None
        self._armed_unsub = None
        self._listeners: list = []
        self._tilt_tasks: dict[str, asyncio.Task] = {}   # entity_id → active tilt task


    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Register all event listeners."""
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, self._on_ha_started
        )

        self._unsub.append(
            async_track_state_change_event(
                self.hass, "sun.sun", self._on_sun_change
            )
        )

        self._unsub.append(
            async_track_time_interval(
                self.hass,
                self._on_interval,
                timedelta(minutes=SCAN_INTERVAL_MINUTES),
            )
        )

        self.reinit_mode_listener()
        self.reinit_armed_listener()

    def reinit_armed_listener(self) -> None:
        if self._armed_unsub:
            self._armed_unsub()
            self._armed_unsub = None

        armed_entity = self._opt(CONF_ARMED_ENTITY, None)
        if armed_entity:
            self._armed_unsub = async_track_state_change_event(
                self.hass, armed_entity, self._on_armed_change
            )

    def reinit_mode_listener(self) -> None:
        """(Re-)register the mode entity state change listener."""
        if self._mode_unsub:
            self._mode_unsub()
            self._mode_unsub = None

        mode_entity = self.entry.data.get(CONF_MODE_ENTITY)
        if mode_entity:
            self._mode_unsub = async_track_state_change_event(
                self.hass, mode_entity, self._on_mode_change
            )

    def unload(self) -> None:
        """Unsubscribe all listeners."""
        for unsub in self._unsub:
            unsub()
        self._unsub.clear()
        if self._mode_unsub:
            self._mode_unsub()
            self._mode_unsub = None
        if self._armed_unsub:
            self._armed_unsub()
            self._armed_unsub = None
        for task in self._tilt_tasks.values():
            task.cancel()
        self._tilt_tasks.clear()


    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_listener(self, cb) -> None:
        self._listeners.append(cb)

    def unregister_listener(self, cb) -> None:
        self._listeners.remove(cb)

    @callback
    def _notify(self) -> None:
        for cb in self._listeners:
            cb()

    def clear_overrides(self, entity_id: str | None = None) -> None:
        """Clear one or all manual overrides."""
        if entity_id:
            self._overrides.pop(entity_id, None)
            self._last_commanded.pop(entity_id, None)
        else:
            self._overrides.clear()
            self._last_commanded.clear()
        _LOGGER.info("Overrides cleared for %s", entity_id or "all covers")
        self._notify()

    @property
    def active_overrides(self) -> dict[str, datetime]:
        return dict(self._overrides)

    @property
    def var_values(self) -> dict[str, float | None]:
        return dict(self._var_values)

    @property
    def assumed_positions(self) -> dict[str, dict]:
        return {k: dict(v) for k, v in self._last_commanded.items()}

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    @callback
    def _on_ha_started(self, _event) -> None:
        self.async_schedule_evaluation(high_priority=True)

    def _managed_covers_for_mode(self, mode: str) -> set[str]:
        """Return covers that will be evaluated (and potentially moved) in this mode."""
        groups = self.entry.options.get(CONF_RULES, [])
        mode_cfg = self.entry.options.get(CONF_MODE_CONFIG, {})
        block_fallback = mode_cfg.get(mode, {}).get("block_fallback", False)
        covers: set[str] = set()
        for group in groups:
            gmode = group.get("mode")
            if gmode == "_priority" or gmode == mode:
                covers.update(group.get("covers", []))
            elif gmode == "_fallback" and not block_fallback:
                covers.update(group.get("covers", []))
        return covers

    @callback
    def _on_mode_change(self, event) -> None:
        new_state = event.data.get("new_state")
        new_mode = new_state.state if new_state else None
        if new_mode:
            config = self._opt(CONF_MODE_CONFIG, {})
            mode_cfg = config.get(new_mode, {})
            if mode_cfg.get("force"):
                covers = self._managed_covers_for_mode(new_mode)
                cleared = [e for e in list(self._overrides) if e in covers]
                for entity_id in cleared:
                    self._overrides.pop(entity_id)
                    self._last_commanded.pop(entity_id, None)
                if cleared:
                    _LOGGER.info(
                        "Force mode '%s': cleared overrides for %s", new_mode, cleared
                    )
                    self._notify()
        self.async_schedule_evaluation(high_priority=True)

    @callback
    def _on_armed_change(self, event) -> None:
        new_state = event.data.get("new_state")
        if new_state and new_state.state == "on":
            self.async_schedule_evaluation(high_priority=True)

    @callback
    def _on_sun_change(self, _event) -> None:
        self.async_schedule_evaluation(high_priority=False)

    @callback
    def _on_interval(self, _now) -> None:
        self.async_schedule_evaluation(high_priority=False)

    @callback
    def async_schedule_evaluation(self, high_priority: bool = False) -> None:
        """Schedule an evaluation cycle, debouncing and rate-limiting."""
        if high_priority:
            self._next_eval_is_high_prio = True

        if not high_priority:
            now = dt_util.now()
            last = self._last_low_prio_eval
            if last and (now - last).total_seconds() < EVALUATION_LOW_PRIO_COOLDOWN:
                return

        if self._eval_task and not self._eval_task.done():
            self._needs_reeval = True
            return

        self._eval_task = self.hass.async_create_task(self._async_eval_loop())

    async def _async_eval_loop(self) -> None:
        """Core evaluation loop ensuring trailing-edge catches."""
        try:
            while True:
                current_high_prio = self._next_eval_is_high_prio
                self._needs_reeval = False
                self._next_eval_is_high_prio = False

                if not current_high_prio:
                    self._last_low_prio_eval = dt_util.now()

                await self._do_evaluate()

                if not self._needs_reeval:
                    break
                # Small breather between back-to-back evaluations
                await asyncio.sleep(1)
        finally:
            self._eval_task = None

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def _opt(self, key: str, default):
        """Read from options, then data, then provided default."""
        return self.entry.options.get(
            key, self.entry.data.get(key, default)
        )

    def _is_armed(self) -> bool:
        """Return True if automation should run. False when armed sensor is off."""
        armed_entity = self._opt(CONF_ARMED_ENTITY, None)
        if not armed_entity:
            return True
        state = self.hass.states.get(armed_entity)
        if state is None:
            _LOGGER.warning("Armed sensor %s not found — running armed (fail-open)", armed_entity)
            return True
        return state.state == "on"

    @property
    def override_duration(self) -> timedelta:
        # Entity-based override takes priority (backwards compat via _opt)
        entity = self._opt(CONF_OVERRIDE_DURATION_ENTITY, None)
        if entity:
            state = self.hass.states.get(entity)
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    return timedelta(minutes=float(state.state))
                except (ValueError, TypeError):
                    pass
        minutes = int(self._opt(CONF_OVERRIDE_DURATION, DEFAULT_OVERRIDE_DURATION))
        return timedelta(minutes=minutes)

    def _tolerance(self) -> int:
        return int(self._opt(CONF_TOLERANCE, DEFAULT_TOLERANCE))

    def _tilt_delay(self) -> int:
        return int(self._opt(CONF_TILT_DELAY, DEFAULT_TILT_DELAY))

    def _build_custom_resolvers(self) -> dict[str, object]:
        """Parse custom_vars option and return {name: resolver(hass, now)} for each binding."""
        from homeassistant.helpers.template import Template

        def _make(source):
            if source.startswith("{{") and source.endswith("}}"):
                tpl = Template(source, self.hass)
                def resolver(hass, now):
                    try:
                        return _coerce_state(str(tpl.async_render()))
                    except Exception:
                        return None
            else:
                def resolver(hass, now):
                    state = hass.states.get(source)
                    if state is None or state.state in ("unavailable", "unknown"):
                        return None
                    return _coerce_state(state.state)
            return resolver

        result = {}
        for line in self.entry.options.get(CONF_CUSTOM_VARS, "").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, source = line.partition("=")
            name = name.strip().lower()
            source = source.strip()
            if name:
                result[name] = _make(source)
        return result

    def _get_custom_resolvers(self) -> dict[str, object]:
        if self._custom_resolvers is None:
            self._custom_resolvers = self._build_custom_resolvers()
        return self._custom_resolvers

    # Delegate to logic.py (pure, unit-testable)
    _rule_matches  = staticmethod(rule_matches)
    _fill_targets  = staticmethod(fill_targets)

    async def _do_evaluate(self) -> None:
        if not self._is_armed():
            _LOGGER.debug("Armed sensor off — skipping evaluation")
            return

        mode_entity = self.entry.data.get(CONF_MODE_ENTITY)
        mode_state = self.hass.states.get(mode_entity) if mode_entity else None
        current_mode = mode_state.state if mode_state else None

        tolerance = self._tolerance()
        now = dt_util.now()

        groups = self.entry.options.get(CONF_RULES, [])
        mode_cfg = self.entry.options.get(CONF_MODE_CONFIG, {})
        block_fallback = mode_cfg.get(current_mode, {}).get("block_fallback", False)

        cur_vals: dict = {v["short"]: v["resolver"](self.hass, now) for v in BUILT_IN_VARS}
        for name, resolver in self._get_custom_resolvers().items():
            if name not in cur_vals:
                cur_vals[name] = resolver(self.hass, now)

        self._var_values = dict(cur_vals)

        shade_targets = evaluate_rules(groups, current_mode, cur_vals, self._prev_vals, block_fallback)
        self._prev_vals = cur_vals

        pos_cmds: dict[str, int] = {}
        tilt_cmds: dict[str, int] = {}
        pos_diffs: dict[str, int] = {}

        for entity_id, target in shade_targets.items():
            state = self.hass.states.get(entity_id)
            if not state:
                continue

            cur_pos = state.attributes.get("current_position")
            cur_tilt = state.attributes.get("current_tilt_position")
            target_pos = target["p"]
            target_tilt = target["t"]

            last = self._last_commanded.get(entity_id, {})
            last_pos = last.get("p")
            last_tilt = last.get("t")

            # ── Active override: check if it should be cleared ──────────────
            if entity_id in self._overrides:
                age = now - self._overrides[entity_id]
                pos_ok = (
                    target_pos is None
                    or cur_pos is None
                    or abs(int(cur_pos) - target_pos) <= tolerance
                )
                tilt_ok = (
                    target_tilt is None
                    or cur_tilt is None
                    or abs(int(cur_tilt) - target_tilt) <= tolerance
                )
                expired = age >= self.override_duration
                if expired or (pos_ok and tilt_ok):
                    _LOGGER.info(
                        "Override resolved for %s (age=%s)", entity_id, age
                    )
                    self._overrides.pop(entity_id)
                    self._last_commanded.pop(entity_id, None)
                else:
                    _LOGGER.debug(
                        "Override active for %s (age=%s)", entity_id, age
                    )
                    continue

            # ── Divergence check: cover moved since our last command? ──────
            is_in_grace = False
            if last:
                cmd_age = (now - last["ts"]).total_seconds()
                if cmd_age < self._TRANSIT_GRACE:
                    is_in_grace = True
                else:
                    pos_moved = (
                        last_pos is not None
                        and cur_pos is not None
                        and abs(int(cur_pos) - last_pos) > tolerance
                    )
                    tilt_moved = (
                        last_tilt is not None
                        and cur_tilt is not None
                        and abs(int(cur_tilt) - last_tilt) > tolerance
                    )
                    if pos_moved or tilt_moved:
                        _LOGGER.info(
                            "Manual override detected for %s "
                            "(expected pos=%s/tilt=%s, actual pos=%s/tilt=%s)",
                            entity_id, last_pos, last_tilt, cur_pos, cur_tilt,
                        )
                        self._overrides[entity_id] = now
                        continue

            # ── Determine if we need to send commands ───────────────────────
            
            # Use current state if available, otherwise fall back to our last commanded state.
            eff_pos = cur_pos if cur_pos is not None else last_pos
            eff_tilt = cur_tilt if cur_tilt is not None else last_tilt

            # We need to move if:
            # 1. Target is different from effective state.
            # 2. AND we are NOT in transit grace, OR the target itself has changed since our last command.
            
            target_pos_changed = target_pos is not None and (
                last_pos is None or abs(int(last_pos) - target_pos) > tolerance
            )
            target_tilt_changed = target_tilt is not None and (
                last_tilt is None or abs(int(last_tilt) - target_tilt) > tolerance
            )

            if is_in_grace:
                needs_pos = target_pos_changed
                needs_tilt = target_tilt_changed
            else:
                needs_pos = target_pos is not None and (
                    eff_pos is None or abs(int(eff_pos) - target_pos) > tolerance
                )
                needs_tilt = target_tilt is not None and (
                    eff_tilt is None or abs(int(eff_tilt) - target_tilt) > tolerance
                )

            needs_move = needs_pos or needs_tilt
            if entity_id not in self._last_commanded or needs_move:
                self._last_commanded[entity_id] = {"p": target_pos, "t": target_tilt, "ts": dt_util.now()}
            else:
                self._last_commanded[entity_id]["p"] = target_pos
                self._last_commanded[entity_id]["t"] = target_tilt

            if needs_pos:
                pos_cmds[entity_id] = target_pos
                # Calculate travel distance for tilt delay discounting
                if cur_pos is not None:
                    pos_diffs[entity_id] = abs(int(cur_pos) - target_pos)
                else:
                    pos_diffs[entity_id] = 100
            if needs_tilt:
                tilt_cmds[entity_id] = target_tilt

        # Send all position commands immediately
        for entity_id, pos in pos_cmds.items():
            await self._send_pos(entity_id, pos)

        # Cancel tilt tasks for covers whose tilt target is gone or removed
        for entity_id in list(self._tilt_tasks):
            target = shade_targets.get(entity_id)
            if target is None or target["t"] is None:
                task = self._tilt_tasks.pop(entity_id, None)
                if task:
                    task.cancel()

        # Send tilt commands
        if tilt_cmds:
            # Add delay to allow position command to complete before tilting
            delay = self._tilt_delay()
            for entity_id, tilt in tilt_cmds.items():
                # Cancel any existing pending tilt for this cover
                if entity_id in self._tilt_tasks:
                    self._tilt_tasks[entity_id].cancel()

                # Delay tilt only if THIS cover is also moving position
                if entity_id in pos_cmds:
                    # Discount delay based on travel distance: (total - 5s floor) * scale + 5s floor
                    scale = pos_diffs.get(entity_id, 100) / 100.0
                    actual_delay = max(5, (delay - 5) * scale + 5)

                    async def _delayed_tilt(eid=entity_id, t=tilt, d=actual_delay):
                        try:
                            await asyncio.sleep(d)
                            await self._send_tilt(eid, t)
                            # Reset transit grace so it starts from the ACTUAL tilt move
                            if eid in self._last_commanded:
                                self._last_commanded[eid]["ts"] = dt_util.now()
                        except asyncio.CancelledError:
                            pass
                        finally:
                            if self._tilt_tasks.get(eid) is asyncio.current_task():
                                self._tilt_tasks.pop(eid, None)

                    self._tilt_tasks[entity_id] = self.hass.async_create_task(_delayed_tilt())
                else:
                    await self._send_tilt(entity_id, tilt)

        self._notify()


    async def _send_pos(self, entity_id: str, pos: int) -> None:
        if pos == 100:
            await self.hass.services.async_call(
                "cover", "open_cover", {"entity_id": entity_id}
            )
        elif pos == 0:
            await self.hass.services.async_call(
                "cover", "close_cover", {"entity_id": entity_id}
            )
        else:
            await self.hass.services.async_call(
                "cover", "set_cover_position",
                {"entity_id": entity_id, "position": pos},
            )

    async def _send_tilt(self, entity_id: str, tilt: int) -> None:
        await self.hass.services.async_call(
            "cover", "set_cover_tilt_position",
            {"entity_id": entity_id, "tilt_position": tilt},
        )
