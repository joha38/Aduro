"""Config flow for Aduro Hybrid Stove integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_STOVE_SERIAL,
    CONF_STOVE_PIN,
    CONF_STOVE_MODEL,
    DEFAULT_STOVE_MODEL,
    STOVE_MODELS,
)

_LOGGER = logging.getLogger(__name__)


class AduroConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aduro Hybrid Stove."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Set unique ID based on serial number
            await self.async_set_unique_id(user_input[CONF_STOVE_SERIAL])
            self._abort_if_unique_id_configured()

            # Create the config entry
            stove_model = user_input.get(CONF_STOVE_MODEL, DEFAULT_STOVE_MODEL)
            return self.async_create_entry(
                title=f"Aduro {stove_model} ({user_input[CONF_STOVE_SERIAL]})",
                data=user_input,
            )

        # Define the configuration schema
        data_schema = vol.Schema(
            {
                vol.Required(CONF_STOVE_MODEL, default=DEFAULT_STOVE_MODEL): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=STOVE_MODELS,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_STOVE_SERIAL): cv.string,
                vol.Required(CONF_STOVE_PIN): cv.string,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "model_info": "Select your Aduro stove model (H1, H2, H3, H4, H5, or H6)"
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> AduroOptionsFlowHandler:
        """Get the options flow for this handler."""
        return AduroOptionsFlowHandler(config_entry)


class AduroOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Aduro integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Update the config entry
            return self.async_create_entry(title="", data=user_input)

        # Get current values
        current_model = self.config_entry.data.get(CONF_STOVE_MODEL, DEFAULT_STOVE_MODEL)

        options_schema = vol.Schema(
            {
                vol.Required(CONF_STOVE_MODEL, default=current_model): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=STOVE_MODELS,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
            description_placeholders={
                "model_info": "Update your Aduro stove model"
            },
        )
