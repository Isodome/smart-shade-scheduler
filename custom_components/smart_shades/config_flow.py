"""Config flow and options flow for Smart Shade Scheduler."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_ARMED_ENTITY,
    CONF_MODE_ENTITY,
    CONF_OVERRIDE_DURATION,
    CONF_OVERRIDE_DURATION_ENTITY,
    CONF_TILT_DELAY,
    CONF_TOLERANCE,
    CONF_TRANSIT_GRACE,
    DEFAULT_OVERRIDE_DURATION,
    DEFAULT_TILT_DELAY,
    DEFAULT_TOLERANCE,
    DEFAULT_TRANSIT_GRACE,
    DOMAIN,
)


def _settings_schema(opts: dict) -> vol.Schema:
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
                CONF_OVERRIDE_DURATION,
                default=opts.get(CONF_OVERRIDE_DURATION, DEFAULT_OVERRIDE_DURATION),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=1440, step=1, mode="box",
                    unit_of_measurement="min",
                )
            ),
            vol.Optional(
                CONF_TILT_DELAY,
                default=opts.get(CONF_TILT_DELAY, DEFAULT_TILT_DELAY),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=120, step=1, mode="slider",
                    unit_of_measurement="s",
                )
            ),
            vol.Optional(
                CONF_TRANSIT_GRACE,
                default=opts.get(CONF_TRANSIT_GRACE, DEFAULT_TRANSIT_GRACE),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=300, step=5, mode="slider",
                    unit_of_measurement="s",
                )
            ),
            vol.Optional(
                CONF_ARMED_ENTITY,
                description={"suggested_value": opts.get(CONF_ARMED_ENTITY)},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor")
            ),
            vol.Optional(
                CONF_OVERRIDE_DURATION_ENTITY,
                description={"suggested_value": opts.get(CONF_OVERRIDE_DURATION_ENTITY)},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="input_number")
            ),
        }
    )


# ---------------------------------------------------------------------------
# Initial config flow
# ---------------------------------------------------------------------------

class SmartShadesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Require a mode entity (input_select) at setup."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict = {}
        if user_input is not None:
            entity_id = user_input[CONF_MODE_ENTITY]
            state = self.hass.states.get(entity_id)
            if state is None:
                errors[CONF_MODE_ENTITY] = "entity_not_found"
            elif not state.attributes.get("options"):
                errors[CONF_MODE_ENTITY] = "no_options"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured(
                    updates={CONF_MODE_ENTITY: entity_id}
                )
                data: dict = {CONF_MODE_ENTITY: entity_id}
                if user_input.get(CONF_ARMED_ENTITY):
                    data[CONF_ARMED_ENTITY] = user_input[CONF_ARMED_ENTITY]
                if user_input.get(CONF_OVERRIDE_DURATION_ENTITY):
                    data[CONF_OVERRIDE_DURATION_ENTITY] = (
                        user_input[CONF_OVERRIDE_DURATION_ENTITY]
                    )
                return self.async_create_entry(
                    title="Smart Shade Scheduler", data=data
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODE_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="input_select")
                    ),
                    vol.Optional(CONF_ARMED_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="binary_sensor")
                    ),
                    vol.Optional(
                        CONF_OVERRIDE_DURATION_ENTITY
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="input_number")
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SmartShadesOptionsFlow()


# ---------------------------------------------------------------------------
# Options flow — settings only (rules live in the sidebar panel)
# ---------------------------------------------------------------------------

class SmartShadesOptionsFlow(config_entries.OptionsFlow):
    """Manage global settings (tolerance, tilt delay) via the cogwheel."""

    def __init__(self) -> None:
        pass

    async def async_step_init(self, user_input=None):
        return await self.async_step_edit_settings()

    async def async_step_edit_settings(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    **self.config_entry.options,
                    CONF_TOLERANCE: int(user_input[CONF_TOLERANCE]),
                    CONF_OVERRIDE_DURATION: int(user_input[CONF_OVERRIDE_DURATION]),
                    CONF_TILT_DELAY: int(user_input[CONF_TILT_DELAY]),
                    CONF_TRANSIT_GRACE: int(user_input[CONF_TRANSIT_GRACE]),
                    CONF_ARMED_ENTITY: user_input.get(CONF_ARMED_ENTITY) or None,
                    CONF_OVERRIDE_DURATION_ENTITY: user_input.get(CONF_OVERRIDE_DURATION_ENTITY) or None,
                },
            )
        merged = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="edit_settings",
            data_schema=_settings_schema(merged),
        )
