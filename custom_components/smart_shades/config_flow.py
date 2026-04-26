"""Config flow and options flow for Smart Shade Scheduler."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_DND_END,
    CONF_DND_START,
    CONF_MODE_ENTITY,
    CONF_TOLERANCE,
    CONF_WIPE_TIME,
    DEFAULT_DND_END,
    DEFAULT_DND_START,
    DEFAULT_TOLERANCE,
    DEFAULT_WIPE_TIME,
    DOMAIN,
)


def _settings_schema(opts: dict) -> vol.Schema:
    """Settings form — all fields optional, pre-filled from current options."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_MODE_ENTITY,
                description={"suggested_value": opts.get(CONF_MODE_ENTITY)},
            ): selector.EntitySelector(),
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


# ---------------------------------------------------------------------------
# Initial config flow — no form, creates entry immediately
# ---------------------------------------------------------------------------

class SmartShadesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Single-instance integration — no setup form needed."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        # Allow only one instance
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Smart Shade Scheduler", data={})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SmartShadesOptionsFlow()


# ---------------------------------------------------------------------------
# Options flow — settings only (rules live in the sidebar panel)
# ---------------------------------------------------------------------------

class SmartShadesOptionsFlow(config_entries.OptionsFlow):
    """Manage global settings via the cogwheel."""

    def __init__(self) -> None:
        pass  # config_entry is set automatically by the framework

    async def async_step_init(self, user_input=None):
        return await self.async_step_edit_settings()

    async def async_step_edit_settings(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    **self.config_entry.options,
                    CONF_MODE_ENTITY: user_input.get(CONF_MODE_ENTITY),
                    CONF_TOLERANCE: int(user_input[CONF_TOLERANCE]),
                    CONF_DND_START: user_input[CONF_DND_START],
                    CONF_DND_END: user_input[CONF_DND_END],
                    CONF_WIPE_TIME: user_input[CONF_WIPE_TIME],
                },
            )
        return self.async_show_form(
            step_id="edit_settings",
            data_schema=_settings_schema(self.config_entry.options),
        )
