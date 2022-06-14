"""Config flow for Solarfocus integration."""
from __future__ import annotations

import logging
from typing import Any
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError


from pysolarfocus import SolarfocusAPI
from pymodbus.client.sync import ModbusTcpClient as ModbusClient

from .const import (
    CONF_BOILER,
    CONF_BUFFER,
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
    CONF_PHOTOVOLTAIC,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
        vol.Optional(CONF_HEATING_CIRCUIT, default=True): bool,
        vol.Optional(CONF_BUFFER, default=True): bool,
        vol.Optional(CONF_BOILER, default=True): bool,
        vol.Optional(CONF_HEATPUMP, default=True): bool,
        vol.Optional(CONF_PHOTOVOLTAIC, default=True): bool,
    }
)


class Solarfocus:
    """Solarfocus Configflow"""

    def __init__(self, hass, host: str, port) -> None:
        """Initialize."""
        self.host = host
        self.port = port
        self.hass = hass
        client = ModbusClient(host, port)
        self.api = SolarfocusAPI(client)

    # async def authenticate(self, username: str, password: str) -> bool:
    #    """Test if we can authenticate with the host."""
    #    return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    client = Solarfocus(hass, data["host"], data["port"])

    if not await hass.async_add_executor_job(client.api.connect):
        raise CannotConnect

    if data[CONF_SCAN_INTERVAL] < 5:
        raise InvalidScanInterval

    # Return info that you want to store in the config entry.
    return {"title": data["name"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solarfocus."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

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
            return self.async_create_entry(
                title=info["title"], data=user_input, options=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
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
        return await self.async_step_user()

    async def _show_options_form(self, user_input):
        """Show the options form to edit info."""
        return self.async_show_form(
            step_id="user",
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
                }
            ),
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""

        if user_input is None:
            return await self._show_options_form(user_input)

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
            return self.async_create_entry(title=info["title"], data=user_input)

        return await self._show_options_form(user_input)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidScanInterval(HomeAssistantError):
    """Error to indicate there is invalid scan interval."""
