"""Sidebar panel + WebSocket API for Smart Shade Scheduler."""

import logging
import os

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.frontend import (
    async_register_built_in_panel,
    async_remove_panel,
)
from homeassistant.core import HomeAssistant, callback

from .const import CONF_MODE_ENTITY, CONF_RULES, DOMAIN

_LOGGER = logging.getLogger(__name__)
_PANEL_URL = "smart-shades"
_STATIC_URL = "/smart_shades_static"
_WWW_DIR = os.path.join(os.path.dirname(__file__), "www")


async def async_setup(hass: HomeAssistant) -> None:
    """Register static path, sidebar panel and WebSocket commands."""
    _LOGGER.debug("Registering static path %s → %s", _STATIC_URL, _WWW_DIR)
    from homeassistant.components.http import StaticPathConfig
    await hass.http.async_register_static_paths(
        [StaticPathConfig(_STATIC_URL, _WWW_DIR, cache_ok=False)]
    )
    _LOGGER.debug("Static path registered")

    _LOGGER.debug("Registering sidebar panel at /%s", _PANEL_URL)
    try:
        async_register_built_in_panel(
            hass,
            "custom",
            sidebar_title="Shades",
            sidebar_icon="mdi:window-shutter-auto",
            frontend_url_path=_PANEL_URL,
            config={
                "_panel_custom": {
                    "name": "smart-shades-panel",
                    "js_url": f"{_STATIC_URL}/smart_shades_panel.js",
                }
            },
        )
        _LOGGER.debug("Panel registered OK")
    except Exception:
        _LOGGER.exception("async_register_built_in_panel failed")
        raise

    websocket_api.async_register_command(hass, ws_get_config)
    websocket_api.async_register_command(hass, ws_save_rules)
    _LOGGER.debug("Panel setup complete")


def async_unload(hass: HomeAssistant) -> None:
    """Remove the sidebar panel when the last config entry is unloaded."""
    async_remove_panel(hass, _PANEL_URL)


# ---------------------------------------------------------------------------
# WebSocket: read current config + state
# ---------------------------------------------------------------------------

@websocket_api.websocket_command(
    {vol.Required("type"): "smart_shades/get_config"}
)
@callback
def ws_get_config(hass: HomeAssistant, connection, msg) -> None:
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        connection.send_error(msg["id"], "not_found", "No config entry found")
        return

    entry = entries[0]
    mode_entity = entry.options.get(CONF_MODE_ENTITY)
    mode_state = hass.states.get(mode_entity) if mode_entity else None

    # Tabs = input_select options (if any) + modes already used in rules
    entity_options: list[str] = (
        list(mode_state.attributes.get("options", []))
        if mode_state else []
    )
    rules = entry.options.get(CONF_RULES, [])
    rule_modes = [r["mode"] for r in rules if r.get("mode")]
    combined = list(dict.fromkeys(entity_options + rule_modes))

    manager = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    overrides = (
        list(manager.active_overrides.keys())
        if manager and hasattr(manager, "active_overrides")
        else []
    )

    connection.send_result(msg["id"], {
        "entry_id": entry.entry_id,
        "rules": rules,
        "mode_entity": mode_entity,
        "current_mode": mode_state.state if mode_state else None,
        "mode_options": combined,
        "overrides": overrides,
    })


# ---------------------------------------------------------------------------
# WebSocket: persist rule changes
# ---------------------------------------------------------------------------

@websocket_api.websocket_command({
    vol.Required("type"): "smart_shades/save_rules",
    vol.Required("entry_id"): str,
    vol.Required("rules"): list,
})
@callback
def ws_save_rules(hass: HomeAssistant, connection, msg) -> None:
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if not entry:
        connection.send_error(
            msg["id"], "not_found", "Config entry not found"
        )
        return

    hass.config_entries.async_update_entry(
        entry,
        options={**entry.options, CONF_RULES: msg["rules"]},
    )
    connection.send_result(msg["id"], {"success": True})
