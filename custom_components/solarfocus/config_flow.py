"""Config flow for Solarfocus integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, override

from aiosolarfocus import (
    ApiVersion,
    Detection,
    SolarfocusClient,
    SolarfocusConfig,
    SolarfocusConnectionError,
    SolarfocusError,
    Systems,
)
from aiosolarfocus.detect import VERSION_MARKERS
import probatio

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
    CONF_DOOR_CONTACT_INVERTED,
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
    selector.SelectOptionDict(
        value=api_version.label, label=f"v{api_version.label}"
    )
    # `label`, not `value`: an `ApiVersion` is ordered by construction, so its
    # value is the printed version with the dot taken out - 25030, not the
    # "25.030" an entry has always stored and a controller shows on its screen.
    for api_version in reversed(ApiVersion)
]

_COMPONENT_COUNT_ZERO_EIGHT_SELECTOR = probatio.All(
    selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0, max=8, mode=selector.NumberSelectorMode.SLIDER
        ),
    ),
    probatio.Coerce(int),
)

_COMPONENT_COUNT_ZERO_FOUR_SELECTOR = probatio.All(
    selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0, max=4, mode=selector.NumberSelectorMode.SLIDER
        ),
    ),
    probatio.Coerce(int),
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


def _connection_schema(current: Mapping[str, Any]) -> probatio.Schema:
    """Return the form for what it takes to read the heating system at all.

    Where it is, which system it is, which register layout it speaks, and how
    often to ask it.
    """
    return probatio.Schema(
        {
            probatio.Required(CONF_HOST, default=current[CONF_HOST]): cv.string,
            probatio.Optional(CONF_PORT, default=current[CONF_PORT]): probatio.Port(),
            probatio.Optional(
                CONF_SCAN_INTERVAL, default=current[CONF_SCAN_INTERVAL]
            ): cv.positive_int,
            probatio.Required(
                CONF_SOLARFOCUS_SYSTEM, default=current[CONF_SOLARFOCUS_SYSTEM]
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=SOLARFOCUS_SYSTEMS, mode=selector.SelectSelectorMode.DROPDOWN
                ),
            ),
            probatio.Required(
                CONF_API_VERSION, default=current[CONF_API_VERSION]
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=SOLARFOCUS_API_VERSIONS),
            ),
        }
    )


STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
        probatio.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
        probatio.Optional(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
        probatio.Optional(
            CONF_SCAN_INTERVAL,
            default=DEFAULT_SCAN_INTERVAL,
        ): cv.positive_int,
        probatio.Required(
            CONF_SOLARFOCUS_SYSTEM, default="Vampair"
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=SOLARFOCUS_SYSTEMS, mode=selector.SelectSelectorMode.DROPDOWN
            ),
        ),
        probatio.Required(CONF_API_VERSION, default="23.020"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=SOLARFOCUS_API_VERSIONS,
                mode=selector.SelectSelectorMode.DROPDOWN,
            ),
        ),
    }
)

STEP_COMP_SELECTION_SCHEMA = probatio.Schema(
    {
        probatio.Optional(
            CONF_HEATING_CIRCUIT, default=1
        ): _COMPONENT_COUNT_ZERO_EIGHT_SELECTOR,
        probatio.Optional(CONF_BUFFER, default=1): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        probatio.Optional(CONF_BOILER, default=1): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        probatio.Optional(CONF_PHOTOVOLTAIC, default=False): bool,
        probatio.Optional(CONF_BIOMASS_BOILER, default=True): bool,
        probatio.Optional(CONF_SOLAR, default=0): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
    }
)

STEP_COMP_VAMPAIR_SELECTION_SCHEMA = probatio.Schema(
    {
        probatio.Optional(
            CONF_HEATING_CIRCUIT, default=1
        ): _COMPONENT_COUNT_ZERO_EIGHT_SELECTOR,
        probatio.Optional(CONF_BUFFER, default=1): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        probatio.Optional(CONF_BOILER, default=1): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        probatio.Optional(
            CONF_FRESH_WATER_MODULE, default=0
        ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        probatio.Optional(CONF_CIRCULATION, default=0): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        probatio.Optional(
            CONF_DIFFERENTIAL_MODULE, default=0
        ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        probatio.Optional(CONF_HEATPUMP, default=True): bool,
        probatio.Optional(CONF_PHOTOVOLTAIC, default=False): bool,
        probatio.Optional(CONF_SOLAR, default=0): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
    }
)

STEP_COMP_THERMINATOR_SELECTION_SCHEMA = probatio.Schema(
    {
        probatio.Optional(
            CONF_HEATING_CIRCUIT, default=1
        ): _COMPONENT_COUNT_ZERO_EIGHT_SELECTOR,
        probatio.Optional(CONF_BUFFER, default=1): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        probatio.Optional(CONF_BOILER, default=1): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        probatio.Optional(
            CONF_FRESH_WATER_MODULE, default=0
        ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        probatio.Optional(CONF_CIRCULATION, default=0): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        probatio.Optional(
            CONF_DIFFERENTIAL_MODULE, default=0
        ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        probatio.Optional(CONF_BIOMASS_BOILER, default=True): bool,
        probatio.Optional(CONF_PHOTOVOLTAIC, default=False): bool,
        probatio.Optional(CONF_SOLAR, default=0): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
    }
)


def _biomass_selection_schema(system: str) -> probatio.Schema:
    """Return the component form of a boiler, less what that boiler cannot have.

    A therminator maps the registers of a fresh water module and answers a flat
    zero on them, whatever is wired to it - Solarfocus confirmed as much - so
    the library refuses a configuration that claims one. Asking for a count the
    setup then fails on is worse than not asking.
    """
    if system != Systems.THERMINATOR:
        return STEP_COMP_THERMINATOR_SELECTION_SCHEMA

    return probatio.Schema(
        {
            marker: validator
            for marker, validator in STEP_COMP_THERMINATOR_SELECTION_SCHEMA.schema.items()
            if marker != CONF_FRESH_WATER_MODULE
        }
    )


def _fresh_water_modules(system: str, count: int) -> int:
    """Return how many fresh water modules an entry of this system may claim."""
    return 0 if system == Systems.THERMINATOR else count


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.

    Only the connection is checked here, so the component counts are left at
    whatever the configuration defaults to - what this asks is whether there is
    an eco manager-touch at that address, and the component step comes later.

    The client is closed on the way out whatever happens: this used to build one
    and drop it on the floor with its socket still open.
    """
    config = SolarfocusConfig(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        system=Systems(data[CONF_SOLARFOCUS_SYSTEM]),
        api_version=ApiVersion.parse(data[CONF_API_VERSION]),
    )

    detection: Detection | None = None
    try:
        async with SolarfocusClient(config) as client:
            detection = await _detect(client)
    except SolarfocusConnectionError as error:
        raise CannotConnect from error

    if data[CONF_SCAN_INTERVAL] < MINIMUM_SCAN_INTERVAL:
        raise InvalidScanInterval

    # Return info that you want to store in the config entry.
    return {"title": data["name"], "detection": detection}


async def _detect(client: SolarfocusClient) -> Detection | None:
    """Ask the controller what it is, or return nothing if it would not say.

    Advice for the forms that follow and never a condition of getting through
    them: the connection has already been made by the time this runs, and a
    controller that fumbles one of the ninety-odd reads this takes is still a
    controller the user can describe by hand, as everyone did before.
    """
    try:
        return await client.detect()
    except SolarfocusError as error:
        _LOGGER.debug("Could not detect what the controller is: %s", error)
        return None


def _detected_differently(
    detection: Detection | None, system: str, api_version: str
) -> dict[str, str] | None:
    """Return what the controller reads as, if that contradicts what was chosen.

    Only a contradiction the detection can stand behind, because the user is
    stopped for it:

    - The system counts when the heat generator identified itself, and not
      between an ecotop and a pellet elegance. Nothing in the registers
      separates those two, the detection calls both a pellet elegance, and a
      real ecotop owner told otherwise would be told wrong.
    - The version is dated by the registers a release added, so it is the
      newest release that added any. A choice counts as the same when no
      marker lies between the two: 25.100 on a controller dated 25.030 is
      as likely right as not. 25.020 and 25.030 added theirs together.
    """
    if detection is None:
        return None

    chosen_system = Systems(system)
    indistinguishable = {Systems.ECOTOP, Systems.PELLETELEGANCE}
    system_differs = (
        detection.confident
        and detection.system != chosen_system
        and not {detection.system, chosen_system} <= indistinguishable
    )

    chosen_version = ApiVersion.parse(api_version)
    dated = detection.api_version
    lowest = ApiVersion.V_25_020 if dated is ApiVersion.V_25_030 else dated
    later_markers = [version for version, _, _ in VERSION_MARKERS if version > dated]
    version_differs = chosen_version < lowest or (
        bool(later_markers) and chosen_version >= min(later_markers)
    )

    if not system_differs and not version_differs:
        return None

    return {
        "system": detection.system if detection.confident else chosen_system,
        "api_version": dated.label,
    }


def _suggested_components(detection: Detection | None, system: str) -> dict[str, Any]:
    """Return the component form filled in with what the controller reported.

    Suggestions in a form the user still reads and submits, so a count read
    wrong costs a correction rather than an entry set up wrong.
    """
    if detection is None:
        return {}

    counts = detection.counts
    suggested: dict[str, Any] = {
        CONF_HEATING_CIRCUIT: counts.heating_circuits,
        CONF_BUFFER: counts.buffers,
        CONF_BOILER: counts.boilers,
        CONF_FRESH_WATER_MODULE: _fresh_water_modules(
            system, counts.fresh_water_modules
        ),
        CONF_CIRCULATION: counts.circulations,
        CONF_DIFFERENTIAL_MODULE: counts.differential_modules,
        CONF_SOLAR: counts.solar,
        CONF_PHOTOVOLTAIC: detection.has_photovoltaic,
    }
    if not any(value for value in suggested.values()):
        # A controller that reported nothing at all was not understood, and a
        # form of zeroes is a worse start than the defaults.
        return {}

    return suggested


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solarfocus."""

    VERSION = 13
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    data: dict[str, Any]
    # What the controller reported in the user step, for the forms after it.
    _detection: Detection | None = None
    # The answer that was last questioned, so the same one is not questioned twice.
    _questioned: dict[str, Any] | None = None

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
            info = await validate_input(self.hass, user_input)
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
            self._detection = info["detection"]
            differs = _detected_differently(
                self._detection,
                user_input[CONF_SOLARFOCUS_SYSTEM],
                user_input[CONF_API_VERSION],
            )
            # Said once, with the form left as the user filled it in. The
            # controller's own screen outranks what its registers suggest, so
            # sending the same answer again is how to say it was meant.
            if differs is None or self._questioned == user_input:
                self.data = user_input
                return await self.async_step_component()

            self._questioned = dict(user_input)
            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_USER_DATA_SCHEMA, user_input
                ),
                errors={"base": "detected_differently"},
                description_placeholders=differs,
            )

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
            schema = (
                STEP_COMP_VAMPAIR_SELECTION_SCHEMA
                if self.data[CONF_SOLARFOCUS_SYSTEM] == Systems.VAMPAIR
                else _biomass_selection_schema(self.data[CONF_SOLARFOCUS_SYSTEM])
            )
            return self.async_show_form(
                step_id="component",
                data_schema=self.add_suggested_values_to_schema(
                    schema,
                    _suggested_components(
                        self._detection, self.data[CONF_SOLARFOCUS_SYSTEM]
                    ),
                ),
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
                CONF_FRESH_WATER_MODULE: _fresh_water_modules(
                    self.data[CONF_SOLARFOCUS_SYSTEM],
                    user_input.get(CONF_FRESH_WATER_MODULE, 0),
                ),
                CONF_CIRCULATION: user_input[CONF_CIRCULATION],
                CONF_DIFFERENTIAL_MODULE: user_input[CONF_DIFFERENTIAL_MODULE],
                # Not asked here - see #91. Off, the specification's polarity,
                # until an owner has a reason from the door contact itself to
                # change it under Configure.
                CONF_DOOR_CONTACT_INVERTED: False,
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
                        # A count the system it is being corrected to cannot
                        # have would fail the setup this reload leads to.
                        CONF_FRESH_WATER_MODULE: _fresh_water_modules(
                            user_input[CONF_SOLARFOCUS_SYSTEM],
                            entry.options[CONF_FRESH_WATER_MODULE],
                        ),
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
        # form and has to be carried over rather than read back from it. A
        # vampair has no door contact either, and does not ask about it, so
        # that carries over the same way rather than dropping out of options.
        vampair = self.config_entry.data[CONF_SOLARFOCUS_SYSTEM] == Systems.VAMPAIR

        return self.async_create_entry(
            title="",
            data={
                **user_input,
                CONF_HEATPUMP: user_input[CONF_HEATPUMP] if vampair else False,
                CONF_BIOMASS_BOILER: (
                    False if vampair else user_input[CONF_BIOMASS_BOILER]
                ),
                CONF_DOOR_CONTACT_INVERTED: (
                    self.config_entry.options[CONF_DOOR_CONTACT_INVERTED]
                    if vampair
                    else user_input[CONF_DOOR_CONTACT_INVERTED]
                ),
                # Not asked of a therminator, so not in the form either.
                CONF_FRESH_WATER_MODULE: _fresh_water_modules(
                    self.config_entry.data[CONF_SOLARFOCUS_SYSTEM],
                    user_input.get(CONF_FRESH_WATER_MODULE, 0),
                ),
            },
        )

    @callback
    def _show_init_form(
        self, current: Mapping[str, Any], errors: dict[str, str]
    ) -> config_entries.ConfigFlowResult:
        """Show the options form, filled in with what the entry has now."""
        # A probatio schema holds markers against validators of every shape,
        # a selector next to a plain `bool`, so there is no narrower type here.
        schema: dict[Any, Any] = {
            probatio.Optional(
                CONF_SCAN_INTERVAL, default=current[CONF_SCAN_INTERVAL]
            ): cv.positive_int,
            probatio.Optional(
                CONF_HEATING_CIRCUIT, default=current[CONF_HEATING_CIRCUIT]
            ): _COMPONENT_COUNT_ZERO_EIGHT_SELECTOR,
            probatio.Optional(
                CONF_BUFFER, default=current[CONF_BUFFER]
            ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
            probatio.Optional(
                CONF_BOILER, default=current[CONF_BOILER]
            ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
            probatio.Optional(
                CONF_CIRCULATION, default=current[CONF_CIRCULATION]
            ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
            probatio.Optional(
                CONF_DIFFERENTIAL_MODULE, default=current[CONF_DIFFERENTIAL_MODULE]
            ): _COMPONENT_COUNT_ZERO_FOUR_SELECTOR,
        }

        if self.config_entry.data[CONF_SOLARFOCUS_SYSTEM] != Systems.THERMINATOR:
            # The one system that cannot have one - see
            # `_biomass_selection_schema`.
            schema[
                probatio.Optional(
                    CONF_FRESH_WATER_MODULE,
                    default=current.get(CONF_FRESH_WATER_MODULE, 0),
                )
            ] = _COMPONENT_COUNT_ZERO_FOUR_SELECTOR

        if self.config_entry.data[CONF_SOLARFOCUS_SYSTEM] == Systems.VAMPAIR:
            schema[probatio.Optional(CONF_HEATPUMP, default=current[CONF_HEATPUMP])] = bool
        else:
            schema[
                probatio.Optional(CONF_BIOMASS_BOILER, default=current[CONF_BIOMASS_BOILER])
            ] = bool
            schema[
                probatio.Optional(
                    CONF_DOOR_CONTACT_INVERTED,
                    default=current[CONF_DOOR_CONTACT_INVERTED],
                )
            ] = bool

        schema[
            probatio.Optional(CONF_PHOTOVOLTAIC, default=current[CONF_PHOTOVOLTAIC])
        ] = bool
        schema[
            probatio.Optional(CONF_SOLAR, default=current[CONF_SOLAR])
        ] = _COMPONENT_COUNT_ZERO_FOUR_SELECTOR

        return self.async_show_form(
            step_id="init", data_schema=probatio.Schema(schema), errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidScanInterval(HomeAssistantError):
    """Error to indicate there is invalid scan interval."""
