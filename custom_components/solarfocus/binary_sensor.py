"""Binary Sensor for Solarfocus integration."""

from dataclasses import dataclass
import logging

from pysolarfocus import Systems

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    BIOMASS_BOILER_COMPONENT,
    BIOMASS_BOILER_COMPONENT_PREFIX,
    BIOMASS_BOILER_PREFIX,
    BUFFER_COMPONENT,
    BUFFER_COMPONENT_PREFIX,
    BUFFER_PREFIX,
    CONF_BIOMASS_BOILER,
    CONF_BUFFER,
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
    DATA_COORDINATOR,
    DOMAIN,
    HEAT_PUMP_COMPONENT,
    HEAT_PUMP_COMPONENT_PREFIX,
    HEAT_PUMP_PREFIX,
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
        for description in HEATING_CIRCUIT_BINARY_SENSOR_TYPES:
            _description = create_description(
                HEATING_CIRCUIT_PREFIX,
                HEATING_CIRCUIT_COMPONENT,
                HEATING_CIRCUIT_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusBinarySensorEntity(coordinator, _description)
            entities.append(entity)

    for i in range(config_entry.options[CONF_BUFFER]):
        for description in BUFFER_BINARY_SENSOR_TYPES:
            _description = create_description(
                BUFFER_PREFIX,
                BUFFER_COMPONENT,
                BUFFER_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusBinarySensorEntity(coordinator, _description)
            entities.append(entity)

    if config_entry.options[CONF_HEATPUMP]:
        for description in HEATPUMP_BINARY_SENSOR_TYPES:
            _description = create_description(
                HEAT_PUMP_PREFIX,
                HEAT_PUMP_COMPONENT,
                HEAT_PUMP_COMPONENT_PREFIX,
                "",
                description,
            )

            entity = SolarfocusBinarySensorEntity(coordinator, _description)
            entities.append(entity)

    if config_entry.options[CONF_BIOMASS_BOILER]:
        for description in BIOMASS_BOILER_BINARY_SENSOR_TYPES:
            _description = create_description(
                BIOMASS_BOILER_PREFIX,
                BIOMASS_BOILER_COMPONENT,
                BIOMASS_BOILER_COMPONENT_PREFIX,
                "",
                description,
            )

            entity = SolarfocusBinarySensorEntity(coordinator, _description)
            entities.append(entity)

    async_add_entities(filterVersionAndSystem(config_entry, entities))


@dataclass
class SolarfocusBinarySensorEntityDescription(
    SolarfocusEntityDescription, BinarySensorEntityDescription
):
    """Description of a Solarfocus binary sensor entity."""

    on_state: str = None


class SolarfocusBinarySensorEntity(SolarfocusEntity, BinarySensorEntity):
    """Representation of a Solarfocus binary sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: SolarfocusBinarySensorEntityDescription,
    ) -> None:
        """Initialize the Solarfocus number entity."""
        super().__init__(coordinator, description)

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        binary_sensor = self.entity_description.item
        value = self._get_native_value(binary_sensor)
        on_state = self.entity_description.on_state
        state = int(value) == int(on_state)
        return state


HEATING_CIRCUIT_BINARY_SENSOR_TYPES = [
    SolarfocusBinarySensorEntityDescription(
        key="limit_thermostat",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_state="0",
    ),
    SolarfocusBinarySensorEntityDescription(
        key="circulator_pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        on_state="1",
    ),
]


BUFFER_BINARY_SENSOR_TYPES = [
    SolarfocusBinarySensorEntityDescription(
        key="pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        on_state="1",
    ),
]

HEATPUMP_BINARY_SENSOR_TYPES = [
    SolarfocusBinarySensorEntityDescription(
        key="evu_lock_active",
        device_class=BinarySensorDeviceClass.LOCK,
        on_state="0",
    ),
    SolarfocusBinarySensorEntityDescription(
        key="defrost_active",
        icon="mdi:snowflake-melt",
        on_state="1",
    ),
    SolarfocusBinarySensorEntityDescription(
        key="boiler_charge",
        device_class=BinarySensorDeviceClass.RUNNING,
        on_state="1",
    ),
]

BIOMASS_BOILER_BINARY_SENSOR_TYPES = [
    SolarfocusBinarySensorEntityDescription(
        key="door_contact",
        device_class=BinarySensorDeviceClass.DOOR,
        on_state="1",
        unsupported_systems=[Systems.ECOTOP, Systems.VAMPAIR],
    ),
    SolarfocusBinarySensorEntityDescription(
        key="door_contact",
        device_class=BinarySensorDeviceClass.DOOR,
        on_state="0",
        unsupported_systems=[Systems.THERMINATOR, Systems.VAMPAIR],
    ),
]
