"""Constants for the Solarfocus integration."""

from collections.abc import Mapping
from typing import Any

from packaging import version

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

"""Version from which several solar circuits exist"""
MULTI_SOLAR_MIN_VERSION = "25.030"


def solar_count(options: Mapping[str, Any]) -> int:
    """Return how many solar circuits to build for these options.

    Solar was a boolean before it became a count, and several circuits only
    exist from api version 25.030 on - pysolarfocus rejects a higher count
    below that and the whole entry fails to load. The options let the count be
    raised regardless of the selected version, so it is capped here.
    """
    raw = options.get(CONF_SOLAR, 0)
    count = (1 if raw else 0) if isinstance(raw, bool) else int(raw or 0)

    if version.parse(
        options.get(CONF_API_VERSION, DEFAULT_API_VERSION)
    ) < version.parse(MULTI_SOLAR_MIN_VERSION):
        return min(count, 1)

    return count
