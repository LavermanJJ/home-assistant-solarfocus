"""Config flow for Solarfocus integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, override

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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_BIOMASS_BOILER,
    CONF_BOILER,
    CONF_BUFFER,
    CONF_CIRCULATION,
    CONF_DIFFERENTIAL_MODULE,
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
    build_unique_id,
)

_LOGGER = logging.getLogger(__name__)

# Below this the controller is asked faster than it answers.
MINIMUM_SCAN_INTERVAL = 5

SOLARFOCUS_SYSTEMS = [
    selector.SelectOptionDict(value="Vampair", label="Heat pump vampair"),
    selector.SelectOptionDict(
        value="Therminator", label=" Biomass boiler therminator II"
    ),
    selector.SelectOptionDict(value="Ecotop", label=" Biomass boiler EcoTop"),
    selector.SelectOptionDict(
        value="Pellet Elegance", label=" Biomass boiler Pellet Elegance"
    ),
    selector.SelectOptionDict(value="Octoplus", label=" Biomass boiler Octoplus"),
]

# CONF_API_VERSION
# Every version the library speaks is a version the user can pick, so the list
# is taken from it rather than written out again here. Kept by hand it fell
# behind - 25.100 was missing from it while controllers in the field were on
# 25.110 - and a version that is not offered leaves the user choosing one that
# is too low, which silently drops the registers added since. Newest first,
# which is the declaration order of the enum reversed.
SOLARFOCUS_API_VERSIONS = [
    selector.SelectOptionDict(value=api_version.value, label=f"v{api_version.value}")
    for api_version in reversed(ApiVersions)
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


def _heat_source(was: str, now: str) -> dict[str, bool]:
    """Return the component flags a change of system forces, if any.

    The heat pump and the biomass boiler are the one part of the component
    layout that the system decides rather than the user: the component step
    only ever offers whichever of the two the chosen system has. So crossing
    between them has to switch the flags over, or the entry would go on reading
    a heat source its system does not have and stop reading the one it does.
    The new one arrives switched on, as it does in the component step.

    A change that stays on the same side of that line - the EcoTop read as a
    Pellet Elegance this is mostly here for - leaves both alone. Someone who
    turned the biomass boiler off meant it.
    """
    if (was == Systems.VAMPAIR) == (now == Systems.VAMPAIR):
        return {}
    heat_pump = now == Systems.VAMPAIR
    return {CONF_HEATPUMP: heat_pump, CONF_BIOMASS_BOILER: not heat_pump}


def _connection_schema(current: Mapping[str, Any]) -> vol.Schema:
    """Return the form for what it takes to read the heating system at all.

    Where it is, which system it is, which register layout it speaks, and how
    often to ask it.
    """
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=current[CONF_HOST]): cv.string,
            vol.Optional(CONF_PORT, default=current[CONF_PORT]): cv.port,
            vol.Optional(
                CONF_SCAN_INTERVAL, default=current[CONF_SCAN_INTERVAL]
            ): cv.positive_int,
            vol.Required(
                CONF_SOLARFOCUS_SYSTEM, default=current[CONF_SOLARFOCUS_SYSTEM]
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=SOLARFOCUS_SYSTEMS, mode=selector.SelectSelectorMode.DROPDOWN
                ),
            ),
            vol.Required(
                CONF_API_VERSION, default=current[CONF_API_VERSION]
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=SOLARFOCUS_API_VERSIONS),
            ),
        }
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
        vol.Optional(CONF_SOLAR, default=0): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
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
        vol.Optional(CONF_CIRCULATION, default=0): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        vol.Optional(
            CONF_DIFFERENTIAL_MODULE, default=0
        ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        vol.Optional(CONF_HEATPUMP, default=True): bool,
        vol.Optional(CONF_PHOTOVOLTAIC, default=False): bool,
        vol.Optional(CONF_SOLAR, default=0): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
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
        vol.Optional(CONF_CIRCULATION, default=0): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        vol.Optional(
            CONF_DIFFERENTIAL_MODULE, default=0
        ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        vol.Optional(CONF_BIOMASS_BOILER, default=True): bool,
        vol.Optional(CONF_PHOTOVOLTAIC, default=False): bool,
        vol.Optional(CONF_SOLAR, default=0): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
    }
)


class Solarfocus:
    """Solarfocus Configflow."""

    def __init__(self, hass: HomeAssistant, data: dict[str, Any]) -> None:
        """Initialize."""
        self.host = data[CONF_HOST]
        self.port = data[CONF_PORT]
        self.hass = hass

        self.api = SolarfocusAPI(
            ip=data[CONF_HOST],
            port=data[CONF_PORT],
            system=Systems(data[CONF_SOLARFOCUS_SYSTEM]),
            api_version=ApiVersions(data[CONF_API_VERSION]),
        )


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    client = Solarfocus(hass, data=data)

    if not await hass.async_add_executor_job(client.api.connect):
        raise CannotConnect

    if data[CONF_SCAN_INTERVAL] < MINIMUM_SCAN_INTERVAL:
        raise InvalidScanInterval

    # Return info that you want to store in the config entry.
    return {"title": data["name"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solarfocus."""

    VERSION = 11
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    data: dict[str, Any]

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        await self.async_set_unique_id(
            build_unique_id(user_input[CONF_HOST], user_input[CONF_PORT])
        )
        self._abort_if_unique_id_configured()

        try:
            await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except InvalidScanInterval:
            errors[CONF_SCAN_INTERVAL] = "invalid_scan_interval"
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
    ) -> config_entries.ConfigFlowResult:
        """Handle the Component Selection step."""
        if user_input is None:
            # The vampair is the only heat pump in `SOLARFOCUS_SYSTEMS`, so the
            # boiler form covers everything else. Falling out of this without a
            # form would leave the step reading an input the user has not given
            # yet.
            if self.data[CONF_SOLARFOCUS_SYSTEM] == Systems.VAMPAIR:
                return self.async_show_form(
                    step_id="component", data_schema=STEP_COMP_VAMPAIR_SELECTION_SCHEMA
                )
            return self.async_show_form(
                step_id="component",
                data_schema=STEP_COMP_THERMINATOR_SELECTION_SCHEMA,
            )

        # Split on the heat pump here as well, so this reads back exactly the
        # flag the form above asked for. Naming the biomass systems instead
        # would leave a system neither branch knows about falling through with
        # both flags unset, into a `KeyError` on the entry below.
        if self.data[CONF_SOLARFOCUS_SYSTEM] == Systems.VAMPAIR:
            self.data[CONF_HEATPUMP] = user_input[CONF_HEATPUMP]
            self.data[CONF_BIOMASS_BOILER] = False
        else:
            self.data[CONF_BIOMASS_BOILER] = user_input[CONF_BIOMASS_BOILER]
            self.data[CONF_HEATPUMP] = False

        return self.async_create_entry(
            title=self.data[CONF_NAME],
            data={
                CONF_NAME: self.data[CONF_NAME],
                CONF_SOLARFOCUS_SYSTEM: self.data[CONF_SOLARFOCUS_SYSTEM],
                CONF_HOST: self.data[CONF_HOST],
                CONF_PORT: self.data[CONF_PORT],
                CONF_API_VERSION: self.data[CONF_API_VERSION],
            },
            options={
                CONF_SCAN_INTERVAL: self.data[CONF_SCAN_INTERVAL],
                CONF_BOILER: user_input[CONF_BOILER],
                CONF_BUFFER: user_input[CONF_BUFFER],
                CONF_HEATING_CIRCUIT: user_input[CONF_HEATING_CIRCUIT],
                CONF_PHOTOVOLTAIC: user_input[CONF_PHOTOVOLTAIC],
                CONF_SOLAR: user_input[CONF_SOLAR],
                CONF_HEATPUMP: self.data[CONF_HEATPUMP],
                CONF_BIOMASS_BOILER: self.data[CONF_BIOMASS_BOILER],
                CONF_FRESH_WATER_MODULE: user_input[CONF_FRESH_WATER_MODULE],
                CONF_CIRCULATION: user_input[CONF_CIRCULATION],
                CONF_DIFFERENTIAL_MODULE: user_input[CONF_DIFFERENTIAL_MODULE],
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Correct what an entry says its heating system is and where it is.

        The options flow can already change the address and the interval, but it
        asks for the whole component layout in the same form: a user whose
        controller moved to another address has to answer for every component of
        their heating system in order to say so, and a wrong answer there removes
        entities. This is the connection on its own.

        Which system it is belongs here too. It was asked once, in the user step,
        and never again, so anyone who picked the wrong one - or picked the
        nearest of the three that used to be offered - could only fix it by
        deleting the entry and losing its history. An entity `unique_id` is built
        from the id of the entry and the key of the entity, and the system is in
        neither, so changing it here keeps every entity the two systems share.
        """
        entry = self._get_reconfigure_entry()

        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=_connection_schema({**entry.data, **entry.options}),
            )

        errors: dict[str, str] = {}
        unique_id = build_unique_id(user_input[CONF_HOST], user_input[CONF_PORT])

        if any(
            other.unique_id == unique_id and other.entry_id != entry.entry_id
            for other in self._async_current_entries()
        ):
            errors["base"] = "already_configured"
        else:
            try:
                await validate_input(
                    self.hass, {CONF_NAME: entry.data[CONF_NAME], **user_input}
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidScanInterval:
                errors[CONF_SCAN_INTERVAL] = "invalid_scan_interval"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Updating the options is what reloads the entry: the update
                # listener the integration registers does that already, for the
                # options flow as much as for here. Asking for the reload as
                # well would do it twice, and Home Assistant refuses to from
                # 2026.12 for exactly that reason.
                connection = dict(user_input)
                scan_interval = connection.pop(CONF_SCAN_INTERVAL)
                return self.async_update_and_abort(
                    entry,
                    # An entry the migration left without a unique id shares an
                    # address with another one by definition, so giving it one
                    # here is the collision that migration avoided.
                    unique_id=None if entry.unique_id is None else unique_id,
                    data={**entry.data, **connection},
                    options={
                        **entry.options,
                        **_heat_source(
                            entry.data[CONF_SOLARFOCUS_SYSTEM],
                            user_input[CONF_SOLARFOCUS_SYSTEM],
                        ),
                        CONF_SCAN_INTERVAL: scan_interval,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_connection_schema(user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return SolarfocusOptionsFlowHandler()


class SolarfocusOptionsFlowHandler(config_entries.OptionsFlow):
    """Solarfocus config flow options handler.

    What an entry that already works lets a user change: how often to ask the
    heating system, and which of its components to ask about. Where the system
    is and which register layout it speaks are what it takes to read anything
    at all, so they live in `ConfigEntry.data` and are changed by the
    reconfigure flow.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is None:
            return self._show_init_form(self.config_entry.options, {})

        if user_input[CONF_SCAN_INTERVAL] < MINIMUM_SCAN_INTERVAL:
            return self._show_init_form(
                user_input, {CONF_SCAN_INTERVAL: "invalid_scan_interval"}
            )

        # Which of the two the system can have is not asked, so it is not in the
        # form and has to be carried over rather than read back from it.
        vampair = self.config_entry.data[CONF_SOLARFOCUS_SYSTEM] == Systems.VAMPAIR

        return self.async_create_entry(
            title="",
            data={
                **user_input,
                CONF_HEATPUMP: user_input[CONF_HEATPUMP] if vampair else False,
                CONF_BIOMASS_BOILER: (
                    False if vampair else user_input[CONF_BIOMASS_BOILER]
                ),
            },
        )

    @callback
    def _show_init_form(
        self, current: Mapping[str, Any], errors: dict[str, str]
    ) -> config_entries.ConfigFlowResult:
        """Show the options form, filled in with what the entry has now."""
        # A voluptuous schema holds markers against validators of every shape,
        # a selector next to a plain `bool`, so there is no narrower type here.
        schema: dict[Any, Any] = {
            vol.Optional(
                CONF_SCAN_INTERVAL, default=current[CONF_SCAN_INTERVAL]
            ): cv.positive_int,
            vol.Optional(
                CONF_HEATING_CIRCUIT, default=current[CONF_HEATING_CIRCUIT]
            ): _COMPONENT_COUNT_ZERO_EIGHT_SELECTOR,
            vol.Optional(
                CONF_BUFFER, default=current[CONF_BUFFER]
            ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
            vol.Optional(
                CONF_BOILER, default=current[CONF_BOILER]
            ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
            vol.Optional(
                CONF_FRESH_WATER_MODULE, default=current[CONF_FRESH_WATER_MODULE]
            ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
            vol.Optional(
                CONF_CIRCULATION, default=current[CONF_CIRCULATION]
            ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
            vol.Optional(
                CONF_DIFFERENTIAL_MODULE, default=current[CONF_DIFFERENTIAL_MODULE]
            ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        }

        if self.config_entry.data[CONF_SOLARFOCUS_SYSTEM] == Systems.VAMPAIR:
            schema[vol.Optional(CONF_HEATPUMP, default=current[CONF_HEATPUMP])] = bool
        else:
            schema[
                vol.Optional(CONF_BIOMASS_BOILER, default=current[CONF_BIOMASS_BOILER])
            ] = bool

        schema[
            vol.Optional(CONF_PHOTOVOLTAIC, default=current[CONF_PHOTOVOLTAIC])
        ] = bool
        schema[
            vol.Optional(CONF_SOLAR, default=current[CONF_SOLAR])
        ] = _COMPONENT_COUNT_ZERO_FOUR_SELECTOR

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema), errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidScanInterval(HomeAssistantError):
    """Error to indicate there is invalid scan interval."""
