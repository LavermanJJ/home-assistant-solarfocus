"""Numbers for Solarfocus integration"""

import logging

from homeassistant.components.sensor import SensorDeviceClass

from homeassistant.config_entries import ConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_BOILER, CONF_HEATING_CIRCUIT, DOMAIN
from .entity import SolarfocusEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Solarfocus config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    if config_entry.data[CONF_HEATING_CIRCUIT]:
        for description in HEATING_CIRCUIT_NUMBER_TYPES:
            entity = SolarfocusNumberEntity(coordinator, description)
            entities.append(entity)

    if config_entry.data[CONF_BOILER]:
        for description in BOILER_NUMBER_TYPES:
            entity = SolarfocusNumberEntity(coordinator, description)
            entities.append(entity)

    async_add_entities(entities)


class SolarfocusNumberEntity(SolarfocusEntity, NumberEntity):
    """Representation of a Solarfocus number entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the Solarfocus number entity."""
        super().__init__(coordinator, description)

        title = self.coordinator._entry.title
        key = self.entity_description.key
        name = self.entity_description.name

        self.entity_id = f"number.{title}_{key}"
        self._attr_name = f"{title} {name}"

    async def async_set_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_value = value
        _name = self.entity_description.key
        _updater = getattr(self.coordinator, "update_" + _name)

        _LOGGER.info("async_set_value - name: %s, value: %f", _name, value)

        await _updater(value)
        self.async_write_ha_state()


HEATING_CIRCUIT_NUMBER_TYPES = [
    NumberEntityDescription(
        key="hc1_target_temperatur",
        name="Heating Circuit Target Supply Temperature",
        icon="mdi:thermostat",
        device_class=SensorDeviceClass.TEMPERATURE,
        min_value=7.0,
        max_value=35.0,
        step=0.5,
        # mode=NumberMode("slider"),
    ),
    # NumberEntityDescription(
    #    key="hc1_target_temperatur",
    #    name="Heating Circuit Target Supply Temperature",
    #    icon="mdi:thermostat",
    #    device_class=SensorDeviceClass.TEMPERATURE,
    #    min_value=7.0,
    #    max_value=35.0,
    #    step=0.5,
    #    # mode=NumberMode("slider"),
    # ),
]

BOILER_NUMBER_TYPES = [
    NumberEntityDescription(
        key="bo1_target_temperatur",
        name="Boiler Target Temperature",
        icon="mdi:thermostat",
        device_class=SensorDeviceClass.TEMPERATURE,
        min_value=20.0,
        max_value=80.0,
        step=1,
    ),
]
