"""Smart Shade Scheduler — core integration."""

import asyncio
import logging
from datetime import datetime, time, timedelta

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)

from .logic import evaluate_rules, fill_targets, is_dnd_active, rule_matches
from .const import (
    CONF_DND_END,
    CONF_DND_ENTITY,
    CONF_DND_START,
    CONF_MODE_ENTITY,
    CONF_OVERRIDE_DURATION_ENTITY,
    CONF_PRESENCE_ENTITY,
    CONF_RULES,
    CONF_TOLERANCE,
    CONF_WIPE_TIME,
    DEFAULT_DND_END,
    DEFAULT_DND_START,
    DEFAULT_TOLERANCE,
    DEFAULT_WIPE_TIME,
    DOMAIN,
    FALLBACK_MODE,
    OVERRIDE_DURATION_HOURS,
    PRIORITY_MODE,
    SCAN_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    """Set up Smart Shade Scheduler from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    manager = ShadeManager(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = manager
    await manager.async_init()

    # Re-init wipe tracker whenever options change (e.g. wipe_time updated)
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
        manager.reinit_wipe_tracker()
        manager.reinit_mode_listener()
        await manager.async_evaluate_rules()


# ---------------------------------------------------------------------------

class ShadeManager:
    """Manages all shade rules and override state for one config entry."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self.entry = entry

        # entity_id → datetime when override started
        self._overrides: dict[str, datetime] = {}
        # entity_id → {"p": position, "t": tilt} of our last command
        self._last_commanded: dict[str, dict] = {}

        self._unsub: list = []
        self._wipe_unsub = None
        self._mode_unsub = None
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

        self.reinit_wipe_tracker()
        self.reinit_mode_listener()

    def reinit_wipe_tracker(self) -> None:
        """(Re-)register the daily override wipe. Safe to call repeatedly."""
        if self._wipe_unsub:
            self._wipe_unsub()
            self._wipe_unsub = None

        wipe_str = self._opt(CONF_WIPE_TIME, DEFAULT_WIPE_TIME)
        try:
            h, m = map(int, wipe_str.split(":")[:2])
            self._wipe_unsub = async_track_time_change(
                self.hass, self._on_daily_wipe, hour=h, minute=m, second=0
            )
        except (ValueError, AttributeError):
            _LOGGER.error("Invalid wipe_time value: %s", wipe_str)

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
        if self._wipe_unsub:
            self._wipe_unsub()
            self._wipe_unsub = None
        if self._mode_unsub:
            self._mode_unsub()
            self._mode_unsub = None

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

    @callback
    def _on_mode_change(self, _event) -> None:
        _LOGGER.debug("Mode changed, scheduling rule evaluation")
        self.hass.async_create_task(self.async_evaluate_rules())

    @callback
    def _on_sun_change(self, _event) -> None:
        self.hass.async_create_task(self.async_evaluate_rules())

    @callback
    def _on_interval(self, _now) -> None:
        self.hass.async_create_task(self.async_evaluate_rules())

    @callback
    def _on_daily_wipe(self, _now) -> None:
        _LOGGER.info("Daily wipe: clearing all overrides and command history")
        self._overrides.clear()
        self._last_commanded.clear()
        self._notify()

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def _opt(self, key: str, default):
        """Read from options, then data, then provided default."""
        return self.entry.options.get(
            key, self.entry.data.get(key, default)
        )

    def _is_dnd_active(self) -> bool:
        # Binary sensor entity overrides manual time window if configured
        dnd_entity = self.entry.data.get(CONF_DND_ENTITY)
        if dnd_entity:
            state = self.hass.states.get(dnd_entity)
            if state:
                return state.state == "on"

        start_str = self._opt(CONF_DND_START, DEFAULT_DND_START)
        end_str   = self._opt(CONF_DND_END,   DEFAULT_DND_END)
        return is_dnd_active(start_str, end_str, datetime.now().time())

    def _override_duration(self) -> timedelta:
        entity = self.entry.data.get(CONF_OVERRIDE_DURATION_ENTITY)
        if entity:
            state = self.hass.states.get(entity)
            if state:
                try:
                    return timedelta(hours=float(state.state))
                except ValueError:
                    pass
        return timedelta(hours=OVERRIDE_DURATION_HOURS)

    def _tolerance(self) -> int:
        return int(self._opt(CONF_TOLERANCE, DEFAULT_TOLERANCE))

    def _presence(self) -> bool | None:
        entity = self.entry.data.get(CONF_PRESENCE_ENTITY)
        if not entity:
            return None
        state = self.hass.states.get(entity)
        if not state:
            return None
        if entity.startswith("zone."):
            try:
                return int(state.state) > 0
            except (ValueError, TypeError):
                return None
        if entity.startswith("binary_sensor."):
            return state.state == "on"
        return state.state == "home"  # person.*, device_tracker.*

    async def async_evaluate_rules(self) -> None:
        """Evaluate rules, moving covers as needed. Skips overridden covers."""
        async with self._eval_lock:
            await self._do_evaluate()

    # Delegate to logic.py (pure, unit-testable)
    _rule_matches  = staticmethod(rule_matches)
    _fill_targets  = staticmethod(fill_targets)

    async def _do_evaluate(self) -> None:
        if self._is_dnd_active():
            _LOGGER.debug("DND active — skipping evaluation")
            return

        mode_entity = self.entry.data.get(CONF_MODE_ENTITY)
        mode_state = self.hass.states.get(mode_entity) if mode_entity else None
        current_mode = mode_state.state if mode_state else None

        sun = self.hass.states.get("sun.sun")
        if not sun:
            return

        azimuth = float(sun.attributes.get("azimuth", 0))
        elevation = float(sun.attributes.get("elevation", 0))
        tolerance = self._tolerance()
        now = datetime.now()

        groups = self.entry.options.get(CONF_RULES, [])
        hour, minute, month = now.hour, now.minute, now.month
        time_hhmm = hour * 100 + minute
        presence = self._presence()
        ctx = (azimuth, elevation, time_hhmm, month)

        shade_targets = evaluate_rules(groups, current_mode, *ctx, presence)

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

            await self._control_shade(
                entity_id, target_pos, target_tilt,
                tolerance, cur_pos, cur_tilt,
            )

        self._notify()

    async def _control_shade(
        self,
        entity_id: str,
        pos: int | None,
        tilt: int | None,
        tolerance: int,
        cur_pos,
        cur_tilt,
    ) -> None:
        # Phantom-52 workaround: some Somfy covers briefly report position 52
        # when fully closed; use 51 to avoid an endless correction loop.
        final_pos = 51 if pos == 52 else pos

        needs_move = False
        if final_pos is not None and cur_pos is not None:
            needs_move = abs(int(cur_pos) - final_pos) > tolerance
        if not needs_move and tilt is not None and cur_tilt is not None:
            needs_move = abs(int(cur_tilt) - tilt) > tolerance

        # Always record the scheduled target so the divergence check can detect
        # manual moves even when the cover was already at the right position
        # and no service call was needed.
        self._last_commanded[entity_id] = {"p": final_pos, "t": tilt}

        if not needs_move:
            return

        if final_pos is not None:
            if final_pos == 100:
                await self.hass.services.async_call(
                    "cover", "open_cover", {"entity_id": entity_id}
                )
            elif final_pos == 0:
                await self.hass.services.async_call(
                    "cover", "close_cover", {"entity_id": entity_id}
                )
            else:
                await self.hass.services.async_call(
                    "cover", "set_cover_position",
                    {"entity_id": entity_id, "position": final_pos},
                )
        if tilt is not None:
            await self.hass.services.async_call(
                "cover", "set_cover_tilt_position",
                {"entity_id": entity_id, "tilt_position": tilt},
            )
