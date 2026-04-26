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

from .const import (
    CONF_DND_END,
    CONF_DND_START,
    CONF_MODE_ENTITY,
    CONF_RULES,
    CONF_TOLERANCE,
    CONF_WIPE_TIME,
    DEFAULT_DND_END,
    DEFAULT_DND_START,
    DEFAULT_TOLERANCE,
    DEFAULT_WIPE_TIME,
    DOMAIN,
    OVERRIDE_DURATION_HOURS,
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

    # One-time domain-level setup (panel + WS commands + service)
    if not hass.data[DOMAIN].get("_panel"):
        from . import panel as _panel
        await _panel.async_setup(hass)
        hass.data[DOMAIN]["_panel"] = True

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
    """Called by HA when options are saved — re-init the wipe time tracker."""
    manager: ShadeManager | None = hass.data[DOMAIN].get(entry.entry_id)
    if manager:
        manager.reinit_wipe_tracker()


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
        self._eval_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Register all event listeners."""
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, self._on_ha_started
        )

        mode_entity = self.entry.data.get(CONF_MODE_ENTITY)
        if mode_entity:
            self._unsub.append(
                async_track_state_change_event(
                    self.hass, mode_entity, self._on_mode_change
                )
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

    def unload(self) -> None:
        """Unsubscribe all listeners."""
        for unsub in self._unsub:
            unsub()
        self._unsub.clear()
        if self._wipe_unsub:
            self._wipe_unsub()
            self._wipe_unsub = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clear_overrides(self, entity_id: str | None = None) -> None:
        """Clear one or all manual overrides."""
        if entity_id:
            self._overrides.pop(entity_id, None)
            self._last_commanded.pop(entity_id, None)
        else:
            self._overrides.clear()
            self._last_commanded.clear()
        _LOGGER.info("Overrides cleared for %s", entity_id or "all covers")

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

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def _opt(self, key: str, default):
        """Read from options, then data, then provided default."""
        return self.entry.options.get(
            key, self.entry.data.get(key, default)
        )

    def _is_dnd_active(self) -> bool:
        start_str = self._opt(CONF_DND_START, DEFAULT_DND_START)
        end_str = self._opt(CONF_DND_END, DEFAULT_DND_END)
        try:
            now = datetime.now().time()
            start_parts = list(map(int, start_str.split(":")))
            end_parts = list(map(int, end_str.split(":")))
            start = time(*start_parts)
            end = time(*end_parts)
            if start <= end:
                return start <= now <= end
            # Overnight window (e.g. 22:00 – 07:00)
            return now >= start or now <= end
        except Exception:
            return False

    def _tolerance(self) -> int:
        return int(self._opt(CONF_TOLERANCE, DEFAULT_TOLERANCE))

    async def async_evaluate_rules(self) -> None:
        """Evaluate rules, moving covers as needed. Skips overridden covers."""
        async with self._eval_lock:
            await self._do_evaluate()

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

        # First matching rule wins per cover
        shade_targets: dict[str, dict] = {}
        for rule in self.entry.options.get(CONF_RULES, []):
            if rule.get("mode") != current_mode:
                continue
            az_min = rule.get("azimuth_above")
            el_max = rule.get("elevation_below")
            el_min = rule.get("elevation_above")
            if az_min is not None and azimuth <= az_min:
                continue
            if el_max is not None and elevation >= el_max:
                continue
            if el_min is not None and elevation <= el_min:
                continue
            for cover in rule.get("covers", []):
                if cover not in shade_targets:
                    shade_targets[cover] = {
                        "p": rule.get("position"),
                        "t": rule.get("tilt"),
                    }

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
                expired = age >= timedelta(hours=OVERRIDE_DURATION_HOURS)
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

        if not needs_move:
            return

        # Record command so the divergence check can detect manual moves later
        self._last_commanded[entity_id] = {"p": final_pos, "t": tilt}

        if final_pos is not None:
            await self.hass.services.async_call(
                "cover", "set_cover_position",
                {"entity_id": entity_id, "position": final_pos},
            )
        if tilt is not None:
            await self.hass.services.async_call(
                "cover", "set_cover_tilt_position",
                {"entity_id": entity_id, "tilt_position": tilt},
            )
