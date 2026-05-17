"""Sidebar panel + WebSocket API for Smart Shade Scheduler."""

import logging
import os
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.frontend import (
    async_register_built_in_panel,
    async_remove_panel,
)
from homeassistant.core import HomeAssistant

from .const import (
    BUILT_IN_VARS,
    CONF_CUSTOM_VARS,
    CONF_MODE_CONFIG,
    CONF_MODE_ENTITY,
    CONF_RULES,
    DOMAIN,
    FALLBACK_MODE,
    PRIORITY_MODE,
    SPECIAL_MODES,
)

if TYPE_CHECKING:
    from . import ShadeManager

_LOGGER = logging.getLogger(__name__)
_PANEL_URL = "smart-shades"
_STATIC_URL = "/smart_shades_static"
_WWW_DIR = os.path.join(os.path.dirname(__file__), "www")
_JS_VERSION = "110"  # bump to bust the browser cache


async def async_setup(hass: HomeAssistant) -> None:
    """Register static path, sidebar panel and WebSocket commands."""
    _LOGGER.debug("Registering static path %s → %s", _STATIC_URL, _WWW_DIR)
    from homeassistant.components.http import StaticPathConfig
    await hass.http.async_register_static_paths(
        [StaticPathConfig(_STATIC_URL, _WWW_DIR)]
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
                    "module_url": (
                        f"{_STATIC_URL}/smart_shades_panel.js"
                        f"?v={_JS_VERSION}"
                    ),
                }
            },
        )
        _LOGGER.debug("Panel registered OK")
    except Exception:
        _LOGGER.exception("async_register_built_in_panel failed")
        raise

    websocket_api.async_register_command(hass, ws_get_config)
    websocket_api.async_register_command(hass, ws_save_rules)
    websocket_api.async_register_command(hass, ws_clear_overrides)
    websocket_api.async_register_command(hass, ws_eval_custom_vars)
    _LOGGER.debug("Panel setup complete")


def async_unload(hass: HomeAssistant) -> None:
    """Remove the sidebar panel when the last config entry is unloaded."""
    async_remove_panel(hass, _PANEL_URL)


# ---------------------------------------------------------------------------
# WebSocket: read current config + state
# ---------------------------------------------------------------------------

@websocket_api.websocket_command({
    vol.Required("type"): "smart_shades/get_config",
    vol.Optional("entry_id"): str,
})
@websocket_api.async_response
async def ws_get_config(hass: HomeAssistant, connection, msg) -> None:
    """Fetch the current configuration for the panel."""
    try:
        entry_id = msg.get("entry_id")
        if entry_id:
            entry = hass.config_entries.async_get_entry(entry_id)
        else:
            entries = hass.config_entries.async_entries(DOMAIN)
            entry = entries[0] if entries else None

        if not entry:
            connection.send_error(msg["id"], "not_found", "No config entry found")
            return

        mode_entity = entry.data.get(CONF_MODE_ENTITY)
        mode_state = hass.states.get(mode_entity) if mode_entity else None

        entity_options: list[str] = (
            list(mode_state.attributes.get("options") or [])
            if mode_state else []
        )
        rules = entry.options.get(CONF_RULES, [])
        # Modes that have rules but no longer exist in the input_select
        rule_modes = list(dict.fromkeys(
            r["mode"] for r in rules if isinstance(r, dict) and r.get("mode")
        ))
        orphaned = [
            m for m in rule_modes
            if m not in entity_options and m not in SPECIAL_MODES
        ]
        combined = (
            [PRIORITY_MODE] + entity_options + orphaned + [FALLBACK_MODE]
        )

        manager = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        overrides = (
            list(manager.active_overrides.keys())
            if manager and hasattr(manager, "active_overrides")
            else []
        )

        custom_var_specs = []
        if manager:
            for name, spec in manager._get_custom_resolvers().items():
                _, var_type = spec["resolver"](manager.hass, None)
                custom_var_specs.append({"short": name, "long": name, "type": var_type})

        connection.send_result(msg["id"], {
            "entry_id": entry.entry_id,
            "mode_entity": mode_entity,
            "mode_config": entry.options.get(CONF_MODE_CONFIG, {}),
            "mode_options": combined,
            "special_modes": list(SPECIAL_MODES),
            "orphaned_modes": orphaned,
            "rules": rules,
            "overrides": overrides,
            "current_mode": mode_state.state if mode_state else None,
            "custom_vars": entry.options.get(CONF_CUSTOM_VARS, ""),
            "built_in_vars": [
                {"short": v["short"], "long": v["long"], "type": v["type"]}
                for v in BUILT_IN_VARS
            ],
            "custom_var_specs": custom_var_specs,
            "var_values": manager.var_values if manager else {},
        })
    except Exception as e:
        _LOGGER.exception("Error in ws_get_config")
        connection.send_error(msg["id"], "unknown_error", str(e))


# ---------------------------------------------------------------------------
# WebSocket: persist rule changes
# ---------------------------------------------------------------------------

@websocket_api.websocket_command({
    vol.Required("type"): "smart_shades/save_rules",
    vol.Required("entry_id"): str,
    vol.Required("rules"): list,
    vol.Optional("mode_config"): dict,
    vol.Optional("custom_vars"): str,
})
@websocket_api.async_response
async def ws_save_rules(hass: HomeAssistant, connection, msg) -> None:
    """Persist the rules and mode configuration."""
    try:
        entry = hass.config_entries.async_get_entry(msg["entry_id"])
        if not entry:
            connection.send_error(
                msg["id"], "not_found", "Config entry not found"
            )
            return

        new_options = {**entry.options, CONF_RULES: msg["rules"]}
        if "mode_config" in msg:
            new_options[CONF_MODE_CONFIG] = msg["mode_config"]
        if "custom_vars" in msg:
            new_options[CONF_CUSTOM_VARS] = msg["custom_vars"]
        
        hass.config_entries.async_update_entry(entry, options=new_options)
        connection.send_result(msg["id"], {"success": True})
    except Exception as e:
        _LOGGER.exception("Error in ws_save_rules")
        connection.send_error(msg["id"], "unknown_error", str(e))


# ---------------------------------------------------------------------------
# WebSocket: clear manual overrides
# ---------------------------------------------------------------------------

@websocket_api.websocket_command({
    vol.Required("type"): "smart_shades/clear_overrides",
    vol.Optional("entity_id"): str,
})
@websocket_api.async_response
async def ws_clear_overrides(hass: HomeAssistant, connection, msg) -> None:
    """Clear manual overrides."""
    try:
        from . import ShadeManager

        found = False
        for manager in hass.data.get(DOMAIN, {}).values():
            if isinstance(manager, ShadeManager):
                manager.clear_overrides(msg.get("entity_id"))
                manager.async_schedule_evaluation(high_priority=True)
                found = True

        if not found:
            connection.send_error(msg["id"], "not_found", "No active managers found")
            return

        connection.send_result(msg["id"], {"success": True})
    except Exception as e:
        _LOGGER.exception("Error in ws_clear_overrides")
        connection.send_error(msg["id"], "unknown_error", str(e))


# ---------------------------------------------------------------------------
# WebSocket: ad-hoc evaluate custom variable bindings (no config change)
# ---------------------------------------------------------------------------

@websocket_api.websocket_command({
    vol.Required("type"): "smart_shades/eval_custom_vars",
    vol.Required("custom_vars"): str,
})
@websocket_api.async_response
async def ws_eval_custom_vars(hass: HomeAssistant, connection, msg) -> None:
    """Evaluate custom variable bindings on-the-fly without modifying config."""
    try:
        from .vars import eval_vars
        results = eval_vars(hass, msg["custom_vars"])
        connection.send_result(msg["id"], {"specs": results})
    except Exception as e:
        _LOGGER.exception("Error in ws_eval_custom_vars")
        connection.send_error(msg["id"], "unknown_error", str(e))
