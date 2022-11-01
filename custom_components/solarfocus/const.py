"""Constants for the Solarfocus integration."""

from typing import Final

DOMAIN = "solarfocus"
UPDATE_LISTENER = "update-listener"
DATA_COORDINATOR = "data-coordinator"

"""Default values for configuration"""
DEFAULT_HOST = "solarfocus.local"
DEFAULT_PORT = 502
DEFAULT_NAME = "Solarfocus"
DEFAULT_SCAN_INTERVAL = 10

"""Configuration and options"""
CONF_SOLARFOCUS_SYSTEM = "system"
CONF_HEATING_CIRCUIT = "heating_circuit"
CONF_BUFFER = "buffer"
CONF_BOILER = "boiler"
CONF_HEATPUMP = "heatpump"
CONF_PHOTOVOLTAIC = "photovoltaic"
CONF_PELLETSBOILER = "pelletsboiler"
CONF_SOLAR = "solar"

"""Custom Measurement Units"""
VOLUME_FLOW_RATE_LITER_PER_HOUR: Final = "l/h"

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

PELLETS_BOILER_PREFIX = "Biomass boiler"
PELLETS_BOILER_COMPONENT = "pelletsboiler"
PELLETS_BOILER_COMPONENT_PREFIX = "pb"

PHOTOVOLTAIC_PREFIX = "Photovoltaic"
PHOTOVOLTAIC_COMPONENT = "photovoltaic"
PHOTOVOLTAIC_COMPONENT_PREFIX = "pv"

SOLAR_PREFIX = "Solar"
SOLAR_COMPONENT = "solar"
SOLAR_COMPONENT_PREFIX = "so"
