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
    DEFAULT_OVERRIDE_DURATION,
    DEFAULT_TILT_DELAY,
    DEFAULT_TOLERANCE,
    DOMAIN,
    FALLBACK_MODE,
    PRIORITY_MODE,
    SCAN_INTERVAL_MINUTES,
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


async def _async_options_updated(hass: HomeAssistant, entry) -> None:
    """Re-init listeners and immediately apply the new rules."""
    manager: ShadeManager | None = hass.data[DOMAIN].get(entry.entry_id)
    if manager:
        manager.reinit_mode_listener()
        manager.reinit_armed_listener()
        await manager.async_evaluate_rules()


# ---------------------------------------------------------------------------

class ShadeManager:
    """Manages all shade rules and override state for one config entry."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self.entry = entry

        # entity_id → datetime when override started
        self._overrides: dict[str, datetime] = {}
        # entity_id → {"p": position, "t": tilt, "ts": datetime} of our last command
        self._last_commanded: dict[str, dict] = {}

        # Seconds after a command during which divergence checks are suppressed
        # (cover may still be travelling to its commanded position)
        self._TRANSIT_GRACE = 90

        self._prev_vals: dict | None = None
        self._var_values: dict[str, float | None] = {}   # built-ins + custom, last eval

        self._unsub: list = []
        self._mode_unsub = None
        self._armed_unsub = None
        self._eval_lock = asyncio.Lock()
        self._listeners: list = []

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

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def _on_ha_started(self, _event) -> None:
        await self.async_evaluate_rules()

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
            mode_cfg = self.entry.options.get(CONF_MODE_CONFIG, {})
            if mode_cfg.get(new_mode, {}).get("force"):
                covers = self._managed_covers_for_mode(new_mode)
                cleared = [e for e in list(self._overrides) if e in covers]
                for entity_id in cleared:
                    self._overrides.pop(entity_id)
                    self._last_commanded.pop(entity_id, None)
                _LOGGER.info(
                    "Force mode '%s': cleared overrides for %s", new_mode, cleared
                )
                self._notify()
        self.hass.async_create_task(self.async_evaluate_rules())

    @callback
    def _on_armed_change(self, event) -> None:
        new_state = event.data.get("new_state")
        if new_state and new_state.state == "on":
            self.hass.async_create_task(self.async_evaluate_rules())

    @callback
    def _on_sun_change(self, _event) -> None:
        self.hass.async_create_task(self.async_evaluate_rules())

    @callback
    def _on_interval(self, _now) -> None:
        self.hass.async_create_task(self.async_evaluate_rules())

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

    def _override_duration(self) -> timedelta:
        # Entity-based override takes priority (backwards compat)
        entity = self.entry.data.get(CONF_OVERRIDE_DURATION_ENTITY)
        if entity:
            state = self.hass.states.get(entity)
            if state:
                try:
                    return timedelta(hours=float(state.state))
                except ValueError:
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
                def resolver(hass, now):
                    try:
                        return _coerce_state(str(Template(source, hass).async_render()))
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

    async def async_evaluate_rules(self) -> None:
        """Evaluate rules, moving covers as needed. Skips overridden covers."""
        async with self._eval_lock:
            await self._do_evaluate()

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
        for name, resolver in self._build_custom_resolvers().items():
            if name not in cur_vals:
                cur_vals[name] = resolver(self.hass, now)

        self._var_values = dict(cur_vals)

        shade_targets = evaluate_rules(groups, current_mode, cur_vals, self._prev_vals, block_fallback)
        self._prev_vals = cur_vals

        pos_cmds: dict[str, int] = {}
        tilt_cmds: dict[str, int] = {}

        for entity_id, target in shade_targets.items():
            state = self.hass.states.get(entity_id)
            if not state:
                continue

            cur_pos = state.attributes.get("current_position")
            cur_tilt = state.attributes.get("current_tilt_position")
            target_pos = target["p"]
            target_tilt = target["t"]

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
                expired = age >= self._override_duration()
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
            last = self._last_commanded.get(entity_id)
            if last is not None:
                cmd_age = (now - last["ts"]).total_seconds()
                if cmd_age < self._TRANSIT_GRACE:
                    # Still in transit — re-send position only, skip tilt
                    needs_pos = target_pos is not None and cur_pos is not None and abs(int(cur_pos) - target_pos) > tolerance
                    if needs_pos:
                        self._last_commanded[entity_id] = {"p": target_pos, "t": target_tilt, "ts": dt_util.now()}
                        pos_cmds[entity_id] = target_pos
                    else:
                        self._last_commanded[entity_id]["p"] = target_pos
                        self._last_commanded[entity_id]["t"] = target_tilt
                    continue

                last_pos = last.get("p")
                last_tilt = last.get("t")
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

            needs_pos = target_pos is not None and cur_pos is not None and abs(int(cur_pos) - target_pos) > tolerance
            needs_tilt = target_tilt is not None and cur_tilt is not None and abs(int(cur_tilt) - target_tilt) > tolerance
            needs_move = needs_pos or needs_tilt
            if entity_id not in self._last_commanded or needs_move:
                self._last_commanded[entity_id] = {"p": target_pos, "t": target_tilt, "ts": dt_util.now()}
            else:
                self._last_commanded[entity_id]["p"] = target_pos
                self._last_commanded[entity_id]["t"] = target_tilt
            if needs_pos:
                pos_cmds[entity_id] = target_pos
            if needs_tilt:
                tilt_cmds[entity_id] = target_tilt

        # Send all position commands immediately
        for entity_id, pos in pos_cmds.items():
            await self._send_pos(entity_id, pos)

        # Send tilt commands: delayed via background task if positions were also
        # sent (device needs to finish moving first), otherwise immediately.
        if tilt_cmds:
            if pos_cmds:
                delay = self._tilt_delay()
                async def _delayed_tilts(cmds: dict = dict(tilt_cmds)) -> None:
                    await asyncio.sleep(delay)
                    for eid, tilt in cmds.items():
                        await self._send_tilt(eid, tilt)
                self.hass.async_create_task(_delayed_tilts())
            else:
                for entity_id, tilt in tilt_cmds.items():
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
