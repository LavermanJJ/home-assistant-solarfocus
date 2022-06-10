"""Constants for the Solarfocus integration."""

from datetime import timedelta
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import TEMP_CELSIUS

DOMAIN = "solarfocus"

DEFAULT_HOST = "solarfocus"
DEFAULT_PORT = 502
DEFAULT_NAME = "solarfocus"


"""Fixed constants."""
SCAN_INTERVAL = timedelta(seconds=10)

"""Supported sensor types."""

SENSOR_TYPES = [
    SensorEntityDescription(
        key="hc1_supply_temp",
        name="HC1 Supply Temperatur",
        native_unit_of_measurement=TEMP_CELSIUS,
        icon="mdi:thermometer",
    )
]
