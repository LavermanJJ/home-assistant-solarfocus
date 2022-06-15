"""Sensors for the Solarfocus integration."""
import logging
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import (
    SolarfocusDataUpdateCoordinator,
    SolarfocusEntity,
)

from .const import (
    BOILER_SENSOR_TYPES,
    BUFFER_SENSOR_TYPES,
    CONF_BOILER,
    CONF_BUFFER,
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
    CONF_PHOTOVOLTAIC,
    DOMAIN,
    HEATPUMP_SENSOR_TYPES,
    HEATING_CIRCUIT_SENSOR_TYPES,
    PV_SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
):
    """Initialize sensor platform from config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    if config_entry.data[CONF_HEATING_CIRCUIT]:
        for description in HEATING_CIRCUIT_SENSOR_TYPES:
            entity = SolarfocusSensor(coordinator, description)
            entities.append(entity)

    if config_entry.data[CONF_BUFFER]:
        for description in BUFFER_SENSOR_TYPES:
            entity = SolarfocusSensor(coordinator, description)
            entities.append(entity)

    if config_entry.data[CONF_BOILER]:
        for description in BOILER_SENSOR_TYPES:
            entity = SolarfocusSensor(coordinator, description)
            entities.append(entity)

    if config_entry.data[CONF_HEATPUMP]:
        for description in HEATPUMP_SENSOR_TYPES:
            entity = SolarfocusSensor(coordinator, description)
            entities.append(entity)

    if config_entry.data[CONF_PHOTOVOLTAIC]:
        for description in PV_SENSOR_TYPES:
            entity = SolarfocusSensor(coordinator, description)
            entities.append(entity)

    async_add_entities(entities)


class SolarfocusSensor(SolarfocusEntity, SensorEntity):
    """Sensor for the Heating Circuit"""

    def __init__(
        self,
        coordinator: SolarfocusDataUpdateCoordinator,
        description: SensorEntityDescription,
    ):
        """Initialize a singular value sensor."""
        super().__init__(coordinator=coordinator, description=description)

        title = self.coordinator._entry.title
        key = self.entity_description.key
        name = self.entity_description.name
        self.entity_id = f"sensor.{title}_{key}"
        self._attr_name = f"{title} {name}"
