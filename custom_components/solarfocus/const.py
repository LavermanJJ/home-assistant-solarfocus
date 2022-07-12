"""Constants for the Solarfocus integration."""

from typing import Final



DOMAIN = "solarfocus"

"""Default values for configuration"""
DEFAULT_HOST = "solarfocus.local"
DEFAULT_PORT = 502
DEFAULT_NAME = "Solarfocus"
DEFAULT_SCAN_INTERVAL = 10

"""Configuration and options"""
CONF_HEATING_CIRCUIT = "heating_circuit"
CONF_BUFFER = "buffer"
CONF_BOILER = "boiler"
CONF_HEATPUMP = "heatpump"
CONF_PHOTOVOLTAIC = "photovoltaic"

"""Custom Measurement Units"""
VOLUME_FLOW_RATE_LITER_PER_HOUR: Final = "l/h"
REVOLUTIONS_PER_MIN: Final = "rpm"


"""Service keys"""
FIELD_SMARTGRID_STATE = "state"
FIELD_SMARTGRID_STATE_DEFAULT = "2"
FIELD_HEATING_MODE = "mode"
FIELD_HEATING_MODE_DEFAULT = "3"
FIELD_HEATING_OPERATION_MODE = "mode"
FIELD_HEATING_OPERATION_MODE_DEFAULT = "0"
FIELD_BOILER_MODE = "mode"
FIELD_BOILER_MODE_DEFAULT = "0"


