"""Config flow for Solarfocus integration."""
from __future__ import annotations

import logging
from typing import Any

from pysolarfocus import ApiVersions, SolarfocusAPI, Systems
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_BIOMASS_BOILER,
    CONF_BOILER,
    CONF_BUFFER,
    CONF_FRESH_WATER_MODULE,
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
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
        value="Therminator", label=" Biomass boiler therminator II"
    ),
    selector.SelectOptionDict(value="Ecotop", label=" Biomass boiler EcoTop"),
]

# CONF_API_VERSION
SOLARFOCUS_API_VERSIONS = [
    selector.SelectOptionDict(value="23.020", label="v23.020"),
    selector.SelectOptionDict(value="23.010", label="v23.010"),
    selector.SelectOptionDict(value="22.090", label="v22.090"),
    selector.SelectOptionDict(value="21.140", label="v21.140"),
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
            selector.SelectSelectorConfig(
                options=SOLARFOCUS_SYSTEMS, mode=selector.SelectSelectorMode.DROPDOWN
            ),
        ),
        vol.Required(CONF_API_VERSION, default="23.020"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=SOLARFOCUS_API_VERSIONS,
                mode=selector.SelectSelectorMode.DROPDOWN,
            ),
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
        vol.Optional(CONF_BIOMASS_BOILER, default=True): bool,
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
        vol.Optional(
            CONF_FRESH_WATER_MODULE, default=0
        ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        vol.Optional(
            CONF_FRESH_WATER_MODULE, default=False
        ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
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
        vol.Optional(
            CONF_FRESH_WATER_MODULE, default=0
        ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        vol.Optional(CONF_BIOMASS_BOILER, default=True): bool,
        vol.Optional(CONF_PHOTOVOLTAIC, default=False): bool,
        vol.Optional(CONF_SOLAR, default=False): bool,
    }
)


class Solarfocus:
    """Solarfocus Configflow."""

    def __init__(self, hass: HomeAssistant, data) -> None:
        """Initialize."""
        self.host = data[CONF_HOST]
        self.port = data[CONF_PORT]
        self.hass = hass

        self.api = SolarfocusAPI(
            ip=data[CONF_HOST],
            port=data[CONF_PORT],
            system=Systems(data[CONF_SOLARFOCUS_SYSTEM]).value,
            api_version=ApiVersions(data[CONF_API_VERSION]),
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

    VERSION = 5
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
            await validate_input(self.hass, user_input)
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
            if self.data[CONF_SOLARFOCUS_SYSTEM] == Systems.VAMPAIR:
                return self.async_show_form(
                    step_id="component", data_schema=STEP_COMP_VAMPAIR_SELECTION_SCHEMA
                )
            if self.data[CONF_SOLARFOCUS_SYSTEM] in [Systems.THERMINATOR, Systems.ECOTOP]:
                return self.async_show_form(
                    step_id="component",
                    data_schema=STEP_COMP_THERMINATOR_SELECTION_SCHEMA,
                )

        if self.data[CONF_SOLARFOCUS_SYSTEM] == Systems.VAMPAIR:
            self.data[CONF_HEATPUMP] = user_input[CONF_HEATPUMP]
            self.data[CONF_BIOMASS_BOILER] = False
        elif self.data[CONF_SOLARFOCUS_SYSTEM] in [Systems.THERMINATOR, Systems.ECOTOP]:
            self.data[CONF_BIOMASS_BOILER] = user_input[CONF_BIOMASS_BOILER]
            self.data[CONF_HEATPUMP] = False

        return self.async_create_entry(
            title=self.data[CONF_NAME],
            data={
                CONF_NAME: self.data[CONF_NAME],
                CONF_SOLARFOCUS_SYSTEM: self.data[CONF_SOLARFOCUS_SYSTEM],
            },
            options={
                CONF_HOST: self.data[CONF_HOST],
                CONF_PORT: self.data[CONF_PORT],
                CONF_SCAN_INTERVAL: self.data[CONF_SCAN_INTERVAL],
                CONF_API_VERSION: self.data[CONF_API_VERSION],
                CONF_BOILER: user_input[CONF_BOILER],
                CONF_BUFFER: user_input[CONF_BUFFER],
                CONF_HEATING_CIRCUIT: user_input[CONF_HEATING_CIRCUIT],
                CONF_PHOTOVOLTAIC: user_input[CONF_PHOTOVOLTAIC],
                CONF_SOLAR: user_input[CONF_SOLAR],
                CONF_HEATPUMP: self.data[CONF_HEATPUMP],
                CONF_BIOMASS_BOILER: self.data[CONF_BIOMASS_BOILER],
                CONF_FRESH_WATER_MODULE: user_input[CONF_FRESH_WATER_MODULE],
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return SolarfocusOptionsFlowHandler(config_entry)


class SolarfocusOptionsFlowHandler(config_entries.OptionsFlow):
    """Solarfocus config flow options handler."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize Solarfocus options flow."""

        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self._errors = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""

        errors = {}

        if user_input is None:
            return await self._show_init_form(user_input, errors)

        if self.config_entry.data[CONF_SOLARFOCUS_SYSTEM] == Systems.VAMPAIR:
            self.options[CONF_HEATPUMP] = user_input[CONF_HEATPUMP]
            self.options[CONF_BIOMASS_BOILER] = False
        elif self.config_entry.data[CONF_SOLARFOCUS_SYSTEM] in [Systems.THERMINATOR, Systems.ECOTOP]:
            self.options[CONF_BIOMASS_BOILER] = user_input[CONF_BIOMASS_BOILER]
            self.options[CONF_HEATPUMP] = False

        try:
            await validate_input(
                self.hass,
                {
                    CONF_NAME: self.config_entry.data[CONF_NAME],
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    CONF_API_VERSION: user_input[CONF_API_VERSION],
                    CONF_SOLARFOCUS_SYSTEM: self.config_entry.data[
                        CONF_SOLARFOCUS_SYSTEM
                    ],
                },
            )
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title="",
                data={
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    CONF_API_VERSION: user_input[CONF_API_VERSION],
                    CONF_BOILER: user_input[CONF_BOILER],
                    CONF_BUFFER: user_input[CONF_BUFFER],
                    CONF_HEATING_CIRCUIT: user_input[CONF_HEATING_CIRCUIT],
                    CONF_PHOTOVOLTAIC: user_input[CONF_PHOTOVOLTAIC],
                    CONF_SOLAR: user_input[CONF_SOLAR],
                    CONF_HEATPUMP: self.options[CONF_HEATPUMP],
                    CONF_BIOMASS_BOILER: self.options[CONF_BIOMASS_BOILER],
                    CONF_FRESH_WATER_MODULE: user_input[CONF_FRESH_WATER_MODULE],
                },
            )

        return await self._show_init_form(user_input, errors)

    async def _show_init_form(self, user_input, errors):
        """Show the options form to edit info."""

        data_schema = {}

        if self.config_entry.data[CONF_SOLARFOCUS_SYSTEM] == Systems.VAMPAIR:
            data_schema = vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=self.config_entry.options[CONF_HOST]
                    ): cv.string,
                    vol.Optional(
                        CONF_PORT, default=self.config_entry.options[CONF_PORT]
                    ): cv.port,
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options[CONF_SCAN_INTERVAL],
                    ): cv.positive_int,
                    vol.Required(
                        CONF_API_VERSION,
                        default=self.config_entry.options[CONF_API_VERSION],
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=SOLARFOCUS_API_VERSIONS,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                    vol.Optional(
                        CONF_HEATING_CIRCUIT,
                        default=self.config_entry.options[CONF_HEATING_CIRCUIT],
                    ): _COMPONENT_COUNT_ZERO_EIGHT_SELECTOR,
                    vol.Optional(
                        CONF_BUFFER, default=self.config_entry.options[CONF_BUFFER]
                    ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
                    vol.Optional(
                        CONF_BOILER, default=self.config_entry.options[CONF_BOILER]
                    ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
                    vol.Optional(
                        CONF_FRESH_WATER_MODULE,
                        default=self.config_entry.options[CONF_FRESH_WATER_MODULE],
                    ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
                    vol.Optional(
                        CONF_HEATPUMP,
                        default=self.config_entry.options[CONF_HEATPUMP],
                    ): bool,
                    vol.Optional(
                        CONF_PHOTOVOLTAIC,
                        default=self.config_entry.options[CONF_PHOTOVOLTAIC],
                    ): bool,
                    vol.Optional(
                        CONF_SOLAR, default=self.config_entry.options[CONF_SOLAR]
                    ): bool,
                }
            )

        elif self.config_entry.data[CONF_SOLARFOCUS_SYSTEM] in [Systems.THERMINATOR, Systems.ECOTOP]:
            data_schema = vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=self.config_entry.options[CONF_HOST]
                    ): cv.string,
                    vol.Optional(
                        CONF_PORT, default=self.config_entry.options[CONF_PORT]
                    ): cv.port,
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options[CONF_SCAN_INTERVAL],
                    ): cv.positive_int,
                    vol.Required(
                        CONF_API_VERSION,
                        default=self.config_entry.options[CONF_API_VERSION],
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=SOLARFOCUS_API_VERSIONS,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                    vol.Optional(
                        CONF_HEATING_CIRCUIT,
                        default=self.config_entry.options[CONF_HEATING_CIRCUIT],
                    ): bool,
                    vol.Optional(
                        CONF_HEATING_CIRCUIT,
                        default=self.config_entry.options[CONF_HEATING_CIRCUIT],
                    ): _COMPONENT_COUNT_ZERO_EIGHT_SELECTOR,
                    vol.Optional(
                        CONF_BUFFER, default=self.config_entry.options[CONF_BUFFER]
                    ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
                    vol.Optional(
                        CONF_BOILER, default=self.config_entry.options[CONF_BOILER]
                    ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
                    vol.Optional(
                        CONF_FRESH_WATER_MODULE,
                        default=self.config_entry.options[CONF_FRESH_WATER_MODULE],
                    ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
                    vol.Optional(
                        CONF_BIOMASS_BOILER,
                        default=self.config_entry.options[CONF_BIOMASS_BOILER],
                    ): bool,
                    vol.Optional(
                        CONF_PHOTOVOLTAIC,
                        default=self.config_entry.options[CONF_PHOTOVOLTAIC],
                    ): bool,
                    vol.Optional(
                        CONF_SOLAR, default=self.config_entry.options[CONF_SOLAR]
                    ): bool,
                }
            )

        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidScanInterval(HomeAssistantError):
    """Error to indicate there is invalid scan interval."""
