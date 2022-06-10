"""Sensors for the Solarfocus integration."""
import logging
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.components.solarfocus import (
    SolarfocusDataUpdateCoordinator,
    SolarfocusEntity,
)
from homeassistant.components.solarfocus.const import SENSOR_TYPES
from homeassistant.config_entries import ConfigEntry

from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
):
    """Initialize sensor platform from config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    for description in SENSOR_TYPES:
        entity = SolarfocusSensor(coordinator, description)
        entities.append(entity)

    async_add_entities(entities)


class SolarfocusSensor(SolarfocusEntity, SensorEntity):
    """Sensor for the single values (e.g. supply temp, ...)."""

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
