"""Config flow for Solarfocus integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from pysolarfocus import SolarfocusAPI, Systems


from .const import (
    CONF_BOILER,
    CONF_BUFFER,
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
    CONF_PELLETSBOILER,
    CONF_PHOTOVOLTAIC,
    CONF_SOLAR,
    CONF_SOLARFOCUS_SYSTEM,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SOLARFOCUS_SYSTEMS = [
    selector.SelectOptionDict(value="Vampair", label="Heat pump vampair"),
    selector.SelectOptionDict(
        value="Therminator", label=" Biomass boiler therminator II touch"
    ),
]

_COMPONENT_COUNT_ZERO_EIGHT_SELECTOR = vol.All(
    selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0, max=8, mode=selector.NumberSelectorMode.SLIDER
        ),
    ),
    vol.Coerce(int),
)

_COMPONENT_COUNT_ZERO_FOUR_SELECTOR = vol.All(
    selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0, max=4, mode=selector.NumberSelectorMode.SLIDER
        ),
    ),
    vol.Coerce(int),
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(
            CONF_SCAN_INTERVAL,
            default=DEFAULT_SCAN_INTERVAL,
        ): cv.positive_int,
        vol.Required(
            CONF_SOLARFOCUS_SYSTEM, default="Vampair"
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(options=SOLARFOCUS_SYSTEMS),
        ),
    }
)

STEP_COMP_SELECTION_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_HEATING_CIRCUIT, default=1
        ): _COMPONENT_COUNT_ZERO_EIGHT_SELECTOR,
        vol.Optional(CONF_BUFFER, default=1): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        vol.Optional(CONF_BOILER, default=1): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        vol.Optional(CONF_PHOTOVOLTAIC, default=False): bool,
        vol.Optional(CONF_PELLETSBOILER, default=True): bool,
        vol.Optional(CONF_SOLAR, default=False): bool,
    }
)

STEP_COMP_VAMPAIR_SELECTION_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_HEATING_CIRCUIT, default=1
        ): _COMPONENT_COUNT_ZERO_EIGHT_SELECTOR,
        vol.Optional(CONF_BUFFER, default=1): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        vol.Optional(CONF_BOILER, default=1): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        vol.Optional(CONF_HEATPUMP, default=True): bool,
        vol.Optional(CONF_PHOTOVOLTAIC, default=False): bool,
        vol.Optional(CONF_SOLAR, default=False): bool,
    }
)

STEP_COMP_THERMINATOR_SELECTION_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_HEATING_CIRCUIT, default=1
        ): _COMPONENT_COUNT_ZERO_EIGHT_SELECTOR,
        vol.Optional(CONF_BUFFER, default=1): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        vol.Optional(CONF_BOILER, default=1): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        vol.Optional(CONF_PELLETSBOILER, default=True): bool,
        vol.Optional(CONF_PHOTOVOLTAIC, default=False): bool,
        vol.Optional(CONF_SOLAR, default=False): bool,
    }
)


class Solarfocus:
    """Solarfocus Configflow"""

    def __init__(self, hass, data) -> None:
        """Initialize."""
        self.host = data[CONF_HOST]
        self.port = data[CONF_PORT]
        self.hass = hass
        self.api = SolarfocusAPI(
            ip=data[CONF_HOST],
            port=data[CONF_PORT],
            system=Systems(data[CONF_SOLARFOCUS_SYSTEM]).name,
        )


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    client = Solarfocus(hass, data=data)

    if not await hass.async_add_executor_job(client.api.connect):
        raise CannotConnect

    if data[CONF_SCAN_INTERVAL] < 5:
        raise InvalidScanInterval

    # Return info that you want to store in the config entry.
    return {"title": data["name"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solarfocus."""

    VERSION = 3
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    data: dict[str, Any]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            self.data = user_input
            return await self.async_step_component()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_component(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the Component Selection step."""
        if user_input is None:
            if self.data[CONF_SOLARFOCUS_SYSTEM] == Systems.Vampair:
                return self.async_show_form(
                    step_id="component", data_schema=STEP_COMP_VAMPAIR_SELECTION_SCHEMA
                )
            if self.data[CONF_SOLARFOCUS_SYSTEM] == Systems.Therminator:
                return self.async_show_form(
                    step_id="component",
                    data_schema=STEP_COMP_THERMINATOR_SELECTION_SCHEMA,
                )

        self.data[CONF_BOILER] = user_input[CONF_BOILER]
        self.data[CONF_BUFFER] = user_input[CONF_BUFFER]
        self.data[CONF_HEATING_CIRCUIT] = user_input[CONF_HEATING_CIRCUIT]
        self.data[CONF_PHOTOVOLTAIC] = user_input[CONF_PHOTOVOLTAIC]
        self.data[CONF_SOLAR] = user_input[CONF_SOLAR]

        if self.data[CONF_SOLARFOCUS_SYSTEM] == Systems.Vampair:
            self.data[CONF_HEATPUMP] = user_input[CONF_HEATPUMP]
            self.data[CONF_PELLETSBOILER] = False
        elif self.data[CONF_SOLARFOCUS_SYSTEM] == Systems.Therminator:
            self.data[CONF_PELLETSBOILER] = user_input[CONF_PELLETSBOILER]
            self.data[CONF_HEATPUMP] = False

        return self.async_create_entry(
            title=self.data["name"], data=self.data, options=self.data
        )

    # @staticmethod
    # @callback
    # def async_get_options_flow(config_entry):
    #    """Get options flow."""
    #    return SolarfocusOptionsFlowHandler(config_entry)


class SolarfocusOptionsFlowHandler(config_entries.OptionsFlow):
    """Solarfocus config flow options handler."""

    def __init__(self, config_entry):
        """Initialize Solarfocus options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self._errors = {}

    async def async_step_init(self, user_input=None):  # pylint: disable=unused-argument
        """Manage the options."""

        errors = {}

        if user_input is not None:
            _LOGGER.debug(f"OptionsFlow: going to update configuration {user_input}")
            # if not (errors := check_input(self.hass, user_input)):
            return self.async_create_entry(
                title=self.config_entry.data["name"], data=user_input
            )

        return await self._show_options_form(user_input)

    async def _show_options_form(self, user_input):
        """Show the options form to edit info."""
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=self.options.get(CONF_HOST, DEFAULT_HOST)
                    ): str,
                    vol.Required(
                        CONF_PORT, default=self.options.get(CONF_PORT, DEFAULT_PORT)
                    ): int,
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): int,
                    vol.Optional(
                        CONF_HEATING_CIRCUIT,
                        default=self.options.get(CONF_HEATING_CIRCUIT, True),
                    ): bool,
                    vol.Optional(
                        CONF_BUFFER, default=self.options.get(CONF_BUFFER, True)
                    ): bool,
                    vol.Optional(
                        CONF_BOILER, default=self.options.get(CONF_BOILER, True)
                    ): bool,
                    vol.Optional(
                        CONF_HEATPUMP, default=self.options.get(CONF_HEATPUMP, True)
                    ): bool,
                    vol.Optional(
                        CONF_PHOTOVOLTAIC,
                        default=self.options.get(CONF_PHOTOVOLTAIC, True),
                    ): bool,
                    vol.Optional(
                        CONF_PELLETSBOILER,
                        default=self.options.get(CONF_PELLETSBOILER, True),
                    ): bool,
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidScanInterval(HomeAssistantError):
    """Error to indicate there is invalid scan interval."""
