"""Config flow and options flow for Smart Shade Scheduler."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

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
    RULE_AZIMUTH_ABOVE,
    RULE_COVERS,
    RULE_ELEVATION_ABOVE,
    RULE_ELEVATION_BELOW,
    RULE_MODE,
    RULE_NAME,
    RULE_POSITION,
    RULE_TILT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rule_schema(defaults: dict | None = None) -> vol.Schema:
    """Build a rule schema, optionally pre-filled from `defaults`."""
    d = defaults or {}

    def _opt(key):
        val = d.get(key)
        if val is not None:
            return vol.Optional(key, description={"suggested_value": val})
        return vol.Optional(key)

    return vol.Schema(
        {
            vol.Required(RULE_NAME, default=d.get(RULE_NAME, "")): (
                selector.TextSelector()
            ),
            vol.Required(RULE_MODE, default=d.get(RULE_MODE, "")): (
                selector.TextSelector()
            ),
            vol.Required(
                RULE_COVERS, default=d.get(RULE_COVERS, [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="cover", multiple=True
                )
            ),
            _opt(RULE_AZIMUTH_ABOVE): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=360, step=1, mode="box"
                )
            ),
            _opt(RULE_ELEVATION_ABOVE): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-90, max=90, step=0.5, mode="box"
                )
            ),
            _opt(RULE_ELEVATION_BELOW): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-90, max=90, step=0.5, mode="box"
                )
            ),
            _opt(RULE_POSITION): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=100, step=1, mode="slider"
                )
            ),
            _opt(RULE_TILT): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=100, step=1, mode="slider"
                )
            ),
        }
    )


def _settings_schema(opts: dict) -> vol.Schema:
    """Return a schema for global settings, pre-filled from current options."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_TOLERANCE,
                default=opts.get(CONF_TOLERANCE, DEFAULT_TOLERANCE),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=20, step=1, mode="slider"
                )
            ),
            vol.Optional(
                CONF_DND_START,
                default=opts.get(CONF_DND_START, DEFAULT_DND_START),
            ): selector.TimeSelector(),
            vol.Optional(
                CONF_DND_END,
                default=opts.get(CONF_DND_END, DEFAULT_DND_END),
            ): selector.TimeSelector(),
            vol.Optional(
                CONF_WIPE_TIME,
                default=opts.get(CONF_WIPE_TIME, DEFAULT_WIPE_TIME),
            ): selector.TimeSelector(),
        }
    )


def _normalize_rule(raw: dict) -> dict:
    """Coerce number selector floats to int and drop None values."""
    rule: dict = {}
    for key, val in raw.items():
        if val is None:
            continue
        if key in (
            RULE_AZIMUTH_ABOVE,
            RULE_ELEVATION_ABOVE,
            RULE_ELEVATION_BELOW,
            RULE_POSITION,
            RULE_TILT,
        ):
            rule[key] = int(val)
        elif key == RULE_COVERS:
            rule[key] = list(val) if isinstance(val, (list, tuple)) else [val]
        else:
            rule[key] = val
    return rule


# ---------------------------------------------------------------------------
# Initial config flow
# ---------------------------------------------------------------------------

class SmartShadesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup: just asks for the mode entity."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict = {}

        if user_input is not None:
            entity_id = user_input[CONF_MODE_ENTITY]
            if self.hass.states.get(entity_id) is None:
                errors[CONF_MODE_ENTITY] = "entity_not_found"
            else:
                return self.async_create_entry(
                    title="Smart Shade Scheduler",
                    data={CONF_MODE_ENTITY: entity_id},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODE_ENTITY): selector.EntitySelector(),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SmartShadesOptionsFlow()


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------

class SmartShadesOptionsFlow(config_entries.OptionsFlow):
    """
    Options flow for managing rules and global settings.

    Menu structure:
      menu → add_rule
           → manage_rules (only when rules exist)
               → rule_action → edit_rule
                             → delete_rule
           → edit_settings
    """

    def __init__(self) -> None:
        self._editing_index: int | None = None

    # ── Root menu ───────────────────────────────────────────────────────────

    async def async_step_init(self, user_input=None):
        return await self.async_step_menu()

    async def async_step_menu(self, user_input=None):
        rules = self.config_entry.options.get(CONF_RULES, [])
        menu_options = ["add_rule", "edit_settings"]
        if rules:
            menu_options.insert(1, "manage_rules")
        return self.async_show_menu(
            step_id="menu", menu_options=menu_options
        )

    # ── Add rule ────────────────────────────────────────────────────────────

    async def async_step_add_rule(self, user_input=None):
        if user_input is not None:
            rules = list(self.config_entry.options.get(CONF_RULES, []))
            rules.append(_normalize_rule(user_input))
            return self._save({CONF_RULES: rules})
        return self.async_show_form(
            step_id="add_rule", data_schema=_rule_schema()
        )

    # ── Manage existing rules ───────────────────────────────────────────────

    async def async_step_manage_rules(self, user_input=None):
        rules = self.config_entry.options.get(CONF_RULES, [])

        if user_input is not None:
            self._editing_index = int(user_input["rule_index"])
            return await self.async_step_rule_action()

        options = [
            selector.SelectOptionDict(
                value=str(i),
                label=(
                    f"{r.get(RULE_NAME, f'Rule {i + 1}')}"
                    f"  [{r.get(RULE_MODE, '?')}]"
                ),
            )
            for i, r in enumerate(rules)
        ]
        return self.async_show_form(
            step_id="manage_rules",
            data_schema=vol.Schema(
                {
                    vol.Required("rule_index"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options)
                    ),
                }
            ),
        )

    async def async_step_rule_action(self, user_input=None):
        return self.async_show_menu(
            step_id="rule_action",
            menu_options=["edit_rule", "delete_rule"],
        )

    async def async_step_edit_rule(self, user_input=None):
        rules = list(self.config_entry.options.get(CONF_RULES, []))
        if user_input is not None:
            rules[self._editing_index] = _normalize_rule(user_input)
            return self._save({CONF_RULES: rules})
        existing = rules[self._editing_index]
        return self.async_show_form(
            step_id="edit_rule", data_schema=_rule_schema(existing)
        )

    async def async_step_delete_rule(self, user_input=None):
        rules = list(self.config_entry.options.get(CONF_RULES, []))
        idx = self._editing_index
        rule_name = rules[idx].get(RULE_NAME, f"Rule {idx + 1}")

        if user_input is not None:
            if user_input.get("confirm"):
                rules.pop(idx)
            return self._save({CONF_RULES: rules})

        return self.async_show_form(
            step_id="delete_rule",
            data_schema=vol.Schema(
                {
                    vol.Required("confirm", default=False): (
                        selector.BooleanSelector()
                    ),
                }
            ),
            description_placeholders={"rule_name": rule_name},
        )

    # ── Global settings ─────────────────────────────────────────────────────

    async def async_step_edit_settings(self, user_input=None):
        if user_input is not None:
            return self._save(
                {
                    CONF_TOLERANCE: int(user_input[CONF_TOLERANCE]),
                    CONF_DND_START: user_input[CONF_DND_START],
                    CONF_DND_END: user_input[CONF_DND_END],
                    CONF_WIPE_TIME: user_input[CONF_WIPE_TIME],
                }
            )
        return self.async_show_form(
            step_id="edit_settings",
            data_schema=_settings_schema(self.config_entry.options),
        )

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _save(self, patch: dict):
        """Merge `patch` into existing options and save."""
        return self.async_create_entry(
            title="",
            data={**self.config_entry.options, **patch},
        )
