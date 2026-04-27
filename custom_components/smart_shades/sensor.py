"""Sensor entity exposing the Smart Shade Scheduler's internal state."""

from datetime import datetime, timedelta
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback

from .const import CONF_MODE_ENTITY, DOMAIN, OVERRIDE_DURATION_HOURS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the state sensor for this config entry."""
    manager = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if manager:
        async_add_entities([SmartShadesSensor(hass, manager, entry)])


class SmartShadesSensor(SensorEntity):
    """Single sensor that surfaces the scheduler's assumed positions and overrides."""

    _attr_icon = "mdi:window-shutter-auto"
    _attr_should_poll = False

    def __init__(self, hass, manager, entry) -> None:
        self._hass = hass
        self._manager = manager
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_state"
        self._attr_name = "Smart Shade Scheduler"

    # ── State: current mode name (or "unknown") ──────────────────────

    @property
    def native_value(self) -> str:
        mode_entity = self._manager._opt(CONF_MODE_ENTITY, None)
        if mode_entity:
            state = self._hass.states.get(mode_entity)
            if state:
                return state.state
        return "unknown"

    # ── Attributes ────────────────────────────────────────────────────

    @property
    def extra_state_attributes(self) -> dict:
        now = datetime.now()
        expiry_td = timedelta(hours=OVERRIDE_DURATION_HOURS)

        assumed = {
            entity_id: {
                k: v for k, v in
                [("position", cmd.get("p")), ("tilt", cmd.get("t"))]
                if v is not None
            }
            for entity_id, cmd in self._manager._last_commanded.items()
        }

        overrides = {}
        for entity_id, since in self._manager.active_overrides.items():
            expires = since + expiry_td
            overrides[entity_id] = {
                "since": since.isoformat(timespec="seconds"),
                "expires": expires.isoformat(timespec="seconds"),
                "expires_in_minutes": max(
                    0, int((expires - now).total_seconds() / 60)
                ),
            }

        return {
            "assumed_positions": assumed,
            "overrides": overrides,
        }

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def async_added_to_hass(self) -> None:
        self._manager.register_listener(self._on_manager_update)

    async def async_will_remove_from_hass(self) -> None:
        self._manager.unregister_listener(self._on_manager_update)

    @callback
    def _on_manager_update(self) -> None:
        self.async_write_ha_state()
