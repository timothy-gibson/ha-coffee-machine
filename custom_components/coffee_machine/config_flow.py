"""Config and options flow for the Coffee Machine integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_ACTIVITY_WINDOW,
    CONF_MIN_HEATING,
    CONF_POWER,
    CONF_SLEEP_TIMEOUT,
    CONF_SWITCH,
    CONF_THRESHOLD,
    CONF_WAKE_OFF,
    DEFAULT_ACTIVITY_WINDOW,
    DEFAULT_MIN_HEATING,
    DEFAULT_NAME,
    DEFAULT_SLEEP_TIMEOUT,
    DEFAULT_THRESHOLD,
    DEFAULT_WAKE_OFF,
    DOMAIN,
)


def _number(minimum: float, maximum: float, step: float, unit: str | None = None):
    config = selector.NumberSelectorConfig(
        min=minimum,
        max=maximum,
        step=step,
        mode=selector.NumberSelectorMode.BOX,
    )
    # unit_of_measurement must be a string if present — passing None makes the
    # selector fail validation and the flow returns "400: Bad Request".
    if unit is not None:
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(config)


def _settings_schema(defaults: dict[str, Any]) -> dict:
    return {
        vol.Required(CONF_SWITCH, default=defaults.get(CONF_SWITCH, vol.UNDEFINED)): (
            selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["switch", "light", "input_boolean"])
            )
        ),
        vol.Required(CONF_POWER, default=defaults.get(CONF_POWER, vol.UNDEFINED)): (
            selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
        ),
        vol.Required(
            CONF_THRESHOLD, default=defaults.get(CONF_THRESHOLD, DEFAULT_THRESHOLD)
        ): _number(0, 5000, 0.01),
        vol.Required(
            CONF_SLEEP_TIMEOUT,
            default=defaults.get(CONF_SLEEP_TIMEOUT, DEFAULT_SLEEP_TIMEOUT),
        ): _number(1, 240, 1, "min"),
        vol.Required(
            CONF_WAKE_OFF, default=defaults.get(CONF_WAKE_OFF, DEFAULT_WAKE_OFF)
        ): _number(1, 30, 1, "s"),
        vol.Required(
            CONF_MIN_HEATING,
            default=defaults.get(CONF_MIN_HEATING, DEFAULT_MIN_HEATING),
        ): _number(0, 900, 5, "s"),
        vol.Required(
            CONF_ACTIVITY_WINDOW,
            default=defaults.get(CONF_ACTIVITY_WINDOW, DEFAULT_ACTIVITY_WINDOW),
        ): _number(0, 600, 5, "s"),
    }


class CoffeeMachineConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a coffee machine."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_SWITCH])
            self._abort_if_unique_id_configured()
            name = user_input.pop(CONF_NAME)
            return self.async_create_entry(title=name, data={}, options=user_input)

        schema = vol.Schema(
            {vol.Required(CONF_NAME, default=DEFAULT_NAME): str, **_settings_schema({})}
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return CoffeeMachineOptionsFlow()


class CoffeeMachineOptionsFlow(OptionsFlow):
    """Change plug, sensor, threshold and timeouts after setup."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(_settings_schema(current))
        )
