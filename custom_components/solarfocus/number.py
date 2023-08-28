"""Numbers for Solarfocus integration."""

from dataclasses import dataclass
import logging

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    BOILER_COMPONENT,
    BOILER_COMPONENT_PREFIX,
    BOILER_PREFIX,
    CONF_BOILER,
    CONF_HEATING_CIRCUIT,
    DATA_COORDINATOR,
    DOMAIN,
    HEATING_CIRCUIT_COMPONENT,
    HEATING_CIRCUIT_COMPONENT_PREFIX,
    HEATING_CIRCUIT_PREFIX,
)
from .entity import (
    SolarfocusEntity,
    SolarfocusEntityDescription,
    create_description,
    filterVersionAndSystem,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Solarfocus config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    entities = []

    for i in range(config_entry.options[CONF_HEATING_CIRCUIT]):
        for description in HEATING_CIRCUIT_NUMBER_TYPES:
            _description = create_description(
                HEATING_CIRCUIT_PREFIX,
                HEATING_CIRCUIT_COMPONENT,
                HEATING_CIRCUIT_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusNumberEntity(coordinator, _description)
            entities.append(entity)

    for i in range(config_entry.options[CONF_BOILER]):
        for description in BOILER_NUMBER_TYPES:
            _description = create_description(
                BOILER_PREFIX,
                BOILER_COMPONENT,
                BOILER_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusNumberEntity(coordinator, _description)
            entities.append(entity)

    async_add_entities(filterVersionAndSystem(config_entry, entities))


@dataclass
class SolarfocusNumberEntityDescription(
    SolarfocusEntityDescription, NumberEntityDescription
):
    """Description of a Solarfocus number entity."""


class SolarfocusNumberEntity(SolarfocusEntity, NumberEntity):
    """Representation of a Solarfocus number entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: SolarfocusNumberEntityDescription,
    ) -> None:
        """Initialize the Solarfocus number entity."""
        super().__init__(coordinator, description)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        number = self.entity_description.item
        return self._set_native_value(number, value)

    @property
    def native_value(self):
        """Return the current state."""
        number = self.entity_description.item
        return self._get_native_value(number)


HEATING_CIRCUIT_NUMBER_TYPES = [
    SolarfocusNumberEntityDescription(
        key="target_supply_temperature",
        icon="mdi:thermostat",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=0.0,
        native_max_value=80.0,
        native_step=0.5,
    ),
    SolarfocusNumberEntityDescription(
        key="target_room_temperatur",
        icon="mdi:thermostat",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=0.0,
        native_max_value=45.0,
        native_step=0.5,
    ),
]

BOILER_NUMBER_TYPES = [
    SolarfocusNumberEntityDescription(
        key="target_temperature",
        icon="mdi:thermostat",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=20.0,
        native_max_value=80.0,
        native_step=1,
    ),
]
