"""Constants for the Solarfocus integration."""

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
HEAT_PUMP_COMPONENT = "heatpump"
HEAT_PUMP_COMPONENT_PREFIX = "hp"

BIOMASS_BOILER_PREFIX = "Biomass boiler"
BIOMASS_BOILER_COMPONENT = "biomassboiler"
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

MANUFACTURER = "Solarfocus"

# The device the entities of a component belong to, keyed by the prefix every
# entity description already carries: the key its name is translated under, and
# the model shown on its device page - a heating circuit has no model of its own
# to report, and a device page with nothing on it says less than the word.
COMPONENT_DEVICES: dict[str, tuple[str, str]] = {
    HEATING_CIRCUIT_COMPONENT_PREFIX: (CONF_HEATING_CIRCUIT, HEATING_CIRCUIT_PREFIX),
    BUFFER_COMPONENT_PREFIX: (CONF_BUFFER, BUFFER_PREFIX),
    BOILER_COMPONENT_PREFIX: (CONF_BOILER, BOILER_PREFIX),
    FRESH_WATER_MODULE_COMPONENT_PREFIX: (
        CONF_FRESH_WATER_MODULE,
        FRESH_WATER_MODULE_PREFIX,
    ),
    SOLAR_COMPONENT_PREFIX: (CONF_SOLAR, SOLAR_PREFIX),
    HEAT_PUMP_COMPONENT_PREFIX: (CONF_HEATPUMP, HEAT_PUMP_PREFIX),
    PHOTOVOLTAIC_COMPONENT_PREFIX: (CONF_PHOTOVOLTAIC, PHOTOVOLTAIC_PREFIX),
    BIOMASS_BOILER_COMPONENT_PREFIX: (CONF_BIOMASS_BOILER, BIOMASS_BOILER_PREFIX),
}

"""Version from which several solar circuits exist"""
MULTI_SOLAR_MIN_VERSION = "25.030"


def solar_count(entry: ConfigEntry) -> int:
    """Return how many solar circuits to build for this entry.

    Solar was a boolean before it became a count, and several circuits only
    exist from api version 25.030 on - pysolarfocus rejects a higher count
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


def build_unique_id(host: str, port: int) -> str:
    """Return the unique id identifying one eco manager-touch.

    Modbus TCP offers nothing to identify the controller itself, so the address
    it is reached at is the only thing telling two installations apart.
    """
    return f"{host}:{port}"


def expected_device_identifiers(entry: ConfigEntry) -> set[tuple[str, str]]:
    """Return the devices this entry should have, the controller included.

    What a user configures is how many of each component their heating system
    has, so lowering a count is what makes a device stale. There is nothing in
    the registry that says which those are - a device of a component that is
    gone looks exactly like one of a component that is there - so the set is
    built from the configuration and everything outside it is stale.
    """
    counted = {
        HEATING_CIRCUIT_COMPONENT_PREFIX: entry.options[CONF_HEATING_CIRCUIT],
        BUFFER_COMPONENT_PREFIX: entry.options[CONF_BUFFER],
        BOILER_COMPONENT_PREFIX: entry.options[CONF_BOILER],
        FRESH_WATER_MODULE_COMPONENT_PREFIX: entry.options[CONF_FRESH_WATER_MODULE],
        # The count the library was built with, not the one the options hold
        SOLAR_COMPONENT_PREFIX: solar_count(entry),
    }
    once = {
        HEAT_PUMP_COMPONENT_PREFIX: entry.options[CONF_HEATPUMP],
        PHOTOVOLTAIC_COMPONENT_PREFIX: entry.options[CONF_PHOTOVOLTAIC],
        BIOMASS_BOILER_COMPONENT_PREFIX: entry.options[CONF_BIOMASS_BOILER],
    }

    identifiers = {(DOMAIN, entry.entry_id)}
    for prefix, count in counted.items():
        identifiers |= {
            (DOMAIN, f"{entry.entry_id}_{prefix}{index + 1}")
            for index in range(int(count))
        }
    identifiers |= {
        (DOMAIN, f"{entry.entry_id}_{prefix}") for prefix, on in once.items() if on
    }

    return identifiers
