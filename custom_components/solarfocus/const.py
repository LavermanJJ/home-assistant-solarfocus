"""Constants for the Solarfocus integration."""

from typing import NamedTuple

from packaging import version

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_VERSION

DOMAIN = "solarfocus"

"""Default values for configuration"""
DEFAULT_HOST = "solarfocus"
DEFAULT_PORT = 502
DEFAULT_NAME = "Solarfocus"
DEFAULT_SCAN_INTERVAL = 10
DEFAULT_API_VERSION = "21.140"

"""Configuration and options"""
CONF_SOLARFOCUS_SYSTEM = "system"
CONF_HEATING_CIRCUIT = "heating_circuit"
CONF_BUFFER = "buffer"
CONF_BOILER = "boiler"
CONF_HEATPUMP = "heatpump"
CONF_PHOTOVOLTAIC = "photovoltaic"
CONF_BIOMASS_BOILER = "biomassboiler"
CONF_SOLAR = "solar"
CONF_FRESH_WATER_MODULE = "fresh_water_module"
CONF_CIRCULATION = "circulation"
CONF_DIFFERENTIAL_MODULE = "differential_module"
CONF_DOOR_CONTACT_INVERTED = "door_contact_inverted"

"""Entity naming"""
HEATING_CIRCUIT_PREFIX = "Heating circuit"
HEATING_CIRCUIT_COMPONENT = "heating_circuits"
HEATING_CIRCUIT_COMPONENT_PREFIX = "hc"

BOILER_PREFIX = "Boiler"
BOILER_COMPONENT = "boilers"
BOILER_COMPONENT_PREFIX = "bo"

BUFFER_PREFIX = "Buffer"
BUFFER_COMPONENT = "buffers"
BUFFER_COMPONENT_PREFIX = "bu"

HEAT_PUMP_PREFIX = "Heat pump"
HEAT_PUMP_COMPONENT = "heat_pump"
HEAT_PUMP_COMPONENT_PREFIX = "hp"

BIOMASS_BOILER_PREFIX = "Biomass boiler"
BIOMASS_BOILER_COMPONENT = "biomass_boiler"
BIOMASS_BOILER_COMPONENT_PREFIX = "bb"

PHOTOVOLTAIC_PREFIX = "Photovoltaic"
PHOTOVOLTAIC_COMPONENT = "photovoltaic"
PHOTOVOLTAIC_COMPONENT_PREFIX = "pv"

SOLAR_PREFIX = "Solar"
SOLAR_COMPONENT = "solar"
SOLAR_COMPONENT_PREFIX = "so"

FRESH_WATER_MODULE_PREFIX = "Fresh water module"
FRESH_WATER_MODULE_COMPONENT = "fresh_water_modules"
FRESH_WATER_MODULE_COMPONENT_PREFIX = "fm"

CIRCULATION_PREFIX = "Circulation"
CIRCULATION_COMPONENT = "circulations"
CIRCULATION_COMPONENT_PREFIX = "ci"

DIFFERENTIAL_MODULE_PREFIX = "Differential module"
DIFFERENTIAL_MODULE_COMPONENT = "differential_modules"
DIFFERENTIAL_MODULE_COMPONENT_PREFIX = "dm"

MANUFACTURER = "Solarfocus"

# What the controller every component hangs off is called. `Solarfocus` is the
# make and the device page says so already; this is the product, and it is the
# same box whichever heating system is wired to it.
CONTROLLER_NAME = "eco manager-touch"


class ComponentDevice(NamedTuple):
    """What an entity description's component prefix says about its device.

    The option and the translation key spell the same word today, and used to
    be the same field for it. They answer to different things: the option is
    the name the entry stores a component under, which is also what a failed
    read is reported as, and the translation key is what `strings.json` calls
    the device. Renaming one silently rewired the other - a device key of
    `heat_pump` would have left the entities of a heat pump that cannot be read
    available for good, because nothing compares them but the entity itself.
    """

    # The entry option this component is configured by, and the name
    # `failed_components` reports it as when it cannot be read.
    option: str
    # The key `strings.json` translates the device name under.
    translation_key: str
    # The model shown on the device page - a heating circuit has no model of
    # its own to report, and a device page with nothing on it says less than
    # the word.
    model: str


# The device the entities of a component belong to, keyed by the prefix every
# entity description already carries.
COMPONENT_DEVICES: dict[str, ComponentDevice] = {
    HEATING_CIRCUIT_COMPONENT_PREFIX: ComponentDevice(
        CONF_HEATING_CIRCUIT, "heating_circuit", HEATING_CIRCUIT_PREFIX
    ),
    BUFFER_COMPONENT_PREFIX: ComponentDevice(CONF_BUFFER, "buffer", BUFFER_PREFIX),
    BOILER_COMPONENT_PREFIX: ComponentDevice(CONF_BOILER, "boiler", BOILER_PREFIX),
    FRESH_WATER_MODULE_COMPONENT_PREFIX: ComponentDevice(
        CONF_FRESH_WATER_MODULE, "fresh_water_module", FRESH_WATER_MODULE_PREFIX
    ),
    CIRCULATION_COMPONENT_PREFIX: ComponentDevice(
        CONF_CIRCULATION, "circulation", CIRCULATION_PREFIX
    ),
    DIFFERENTIAL_MODULE_COMPONENT_PREFIX: ComponentDevice(
        CONF_DIFFERENTIAL_MODULE, "differential_module", DIFFERENTIAL_MODULE_PREFIX
    ),
    SOLAR_COMPONENT_PREFIX: ComponentDevice(CONF_SOLAR, "solar", SOLAR_PREFIX),
    HEAT_PUMP_COMPONENT_PREFIX: ComponentDevice(
        CONF_HEATPUMP, "heatpump", HEAT_PUMP_PREFIX
    ),
    PHOTOVOLTAIC_COMPONENT_PREFIX: ComponentDevice(
        CONF_PHOTOVOLTAIC, "photovoltaic", PHOTOVOLTAIC_PREFIX
    ),
    BIOMASS_BOILER_COMPONENT_PREFIX: ComponentDevice(
        CONF_BIOMASS_BOILER, "biomassboiler", BIOMASS_BOILER_PREFIX
    ),
}

# The entry option a component is configured by -> the prefix its devices are
# identified by. `COMPONENT_DEVICES` is keyed the other way round, by what an
# entity description carries; a failed read names the option, and the devices
# of it are found by the prefix.
COMPONENT_PREFIXES: dict[str, str] = {
    device.option: prefix for prefix, device in COMPONENT_DEVICES.items()
}

# The components a heating system has at most one of, which is why their device
# identifier carries no index where every other component's does.
SINGLE_COMPONENTS = frozenset({CONF_HEATPUMP, CONF_PHOTOVOLTAIC, CONF_BIOMASS_BOILER})

# How many of each component an entry can ever have been configured with, which
# is what the options form offers. It is not what this entry has: a repair issue
# has to be answered for every instance a *previous* configuration could have
# raised one for, or lowering a count would leave the issue of the instance that
# is gone standing forever with nothing left to clear it.
COMPONENT_MAX_COUNT: dict[str, int] = {
    CONF_HEATING_CIRCUIT: 8,
    CONF_BUFFER: 4,
    CONF_BOILER: 4,
    CONF_FRESH_WATER_MODULE: 4,
    CONF_CIRCULATION: 4,
    CONF_DIFFERENTIAL_MODULE: 4,
    CONF_SOLAR: 4,
    CONF_HEATPUMP: 1,
    CONF_PHOTOVOLTAIC: 1,
    CONF_BIOMASS_BOILER: 1,
}


def component_instances(option: str) -> list[tuple[str, str]]:
    """Return every instance of one component an entry could have configured.

    The pair an entity carries and a failed read is reported as: the option and
    the index as a string, blank for the components that exist once.
    """
    if option in SINGLE_COMPONENTS:
        return [(option, "")]

    return [
        (option, str(index + 1)) for index in range(COMPONENT_MAX_COUNT[option])
    ]

# Version from which several solar circuits exist.
MULTI_SOLAR_MIN_VERSION = "25.030"


def solar_count(entry: ConfigEntry) -> int:
    """Return how many solar circuits to build for this entry.

    Solar was a boolean before it became a count, and several circuits only
    exist from api version 25.030 on - the library rejects a higher count
    below that and the whole entry fails to load. The options let the count be
    raised regardless of the selected version, so it is capped here.

    The count is an option and the version is data, so this takes the entry
    rather than either half of it.
    """
    raw = entry.options.get(CONF_SOLAR, 0)
    count = (1 if raw else 0) if isinstance(raw, bool) else int(raw or 0)

    if version.parse(
        entry.data.get(CONF_API_VERSION, DEFAULT_API_VERSION)
    ) < version.parse(MULTI_SOLAR_MIN_VERSION):
        return min(count, 1)

    return count


# The api version a component's registers arrived in, for those that are not in
# every version the integration offers. Below it the library builds no such
# component at all - the attribute the entities would read is not there - and
# its update call returns success without asking the controller anything.
COMPONENT_MIN_VERSION: dict[str, str] = {
    CONF_CIRCULATION: "25.030",
    CONF_DIFFERENTIAL_MODULE: "25.030",
}


def component_count(entry: ConfigEntry, option: str) -> int:
    """Return how many of a component this entry builds, the version counted in.

    What the options hold is what the user says their heating system has, and
    for a component that a later api version brought that is not the same as
    what the entry has: below `COMPONENT_MIN_VERSION` there is nothing to read
    whatever the count says, so everything that asks how many there are - the
    devices expected in the registry, the entities built, the components the
    coordinator counts as configured - has to ask this rather than the option.

    A component that every version has answers with its option, and one
    configured by a switch rather than a count answers 1 or 0.

    See `solar_count` for the one component that is capped rather than dropped:
    solar itself predates the version its further circuits arrived in.
    """
    raw = entry.options.get(option, 0)
    count = (1 if raw else 0) if isinstance(raw, bool) else int(raw or 0)

    minimum = COMPONENT_MIN_VERSION.get(option)
    if minimum is not None and version.parse(
        entry.data.get(CONF_API_VERSION, DEFAULT_API_VERSION)
    ) < version.parse(minimum):
        return 0

    return count


def build_unique_id(host: str, port: int) -> str:
    """Return the unique id identifying one eco manager-touch.

    Modbus TCP offers nothing to identify the controller itself, so the address
    it is reached at is the only thing telling two installations apart.
    """
    return f"{host}:{port}"


def component_device_identifiers(
    entry: ConfigEntry, option: str
) -> list[tuple[str, str]]:
    """Return the identifier of every device of one component, in order.

    One device per instance: four buffers are `Buffer 1` to `Buffer 4`, and the
    identifier of a component that exists once is the bare prefix. How many
    there are is what the entry builds rather than what the options hold, so a
    component the selected api version does not have has no devices.

    The identifier is what both the devices expected in the registry and the
    devices a repair issue is about are looked up by, so they are built here
    once rather than spelled out twice.
    """
    prefix = COMPONENT_PREFIXES[option]
    count = (
        solar_count(entry) if option == CONF_SOLAR else component_count(entry, option)
    )

    if option in SINGLE_COMPONENTS:
        return [(DOMAIN, f"{entry.entry_id}_{prefix}")] if count else []

    return [(DOMAIN, f"{entry.entry_id}_{prefix}{index + 1}") for index in range(count)]


def expected_device_identifiers(entry: ConfigEntry) -> set[tuple[str, str]]:
    """Return the devices this entry should have, the controller included.

    What a user configures is how many of each component their heating system
    has, so lowering a count is what makes a device stale. There is nothing in
    the registry that says which those are - a device of a component that is
    gone looks exactly like one of a component that is there - so the set is
    built from the configuration and everything outside it is stale.
    """
    identifiers = {(DOMAIN, entry.entry_id)}
    for option in COMPONENT_PREFIXES:
        identifiers |= set(component_device_identifiers(entry, option))

    return identifiers
