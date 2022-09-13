"""Binary Sensor for Solarfocus integration"""

from dataclasses import dataclass
import logging
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
    CONF_BUFFER,
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
    CONF_PELLETSBOILER,
    DOMAIN,
)
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
        for description in HEATING_CIRCUIT_BINARY_SENSOR_TYPES:
            entity = SolarfocusBinarySensorEntity(coordinator, description)
            entities.append(entity)

    if config_entry.data[CONF_BUFFER]:
        for description in BUFFER_BINARY_SENSOR_TYPES:
            entity = SolarfocusBinarySensorEntity(coordinator, description)
            entities.append(entity)

    if config_entry.data[CONF_HEATPUMP]:
        for description in HEATPUMP_BINARY_SENSOR_TYPES:
            entity = SolarfocusBinarySensorEntity(coordinator, description)
            entities.append(entity)

    if config_entry.data[CONF_PELLETSBOILER]:
        for description in PB_BINARY_SENSOR_TYPES:
            entity = SolarfocusBinarySensorEntity(coordinator, description)
            entities.append(entity)

    async_add_entities(entities)


@dataclass
class SolarfocusBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Description of a Solarfocus binary sensor entity"""

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
        sensor = self.entity_description.key
        value = getattr(self.coordinator.api, sensor)
        on_state = self.entity_description.on_state
        state = int(value) == int(on_state)

        return state


HEATING_CIRCUIT_BINARY_SENSOR_TYPES = [
    SolarfocusBinarySensorEntityDescription(
        key="hc1_limit_thermostat",
        name="Heating limit thermostat",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_state="0",
    ),
    SolarfocusBinarySensorEntityDescription(
        key="hc1_circulator_pump",
        name="Heating circulator pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        on_state="1",
    ),
]


BUFFER_BINARY_SENSOR_TYPES = [
    SolarfocusBinarySensorEntityDescription(
        key="bu1_pump",
        name="Buffer pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        on_state="1",
    ),
]

HEATPUMP_BINARY_SENSOR_TYPES = [
    SolarfocusBinarySensorEntityDescription(
        key="hp_evu_lock_active",
        name="Heatpump evu lock",
        device_class=BinarySensorDeviceClass.LOCK,
        on_state="0",
    ),
    SolarfocusBinarySensorEntityDescription(
        key="hp_defrost_active",
        name="Heatpump defrost",
        icon="mdi:snowflake-melt",
        on_state="1",
    ),
    SolarfocusBinarySensorEntityDescription(
        key="hp_boiler_charge",
        name="Heatpump boiler charge",
        device_class=BinarySensorDeviceClass.RUNNING,
        on_state="1",
    ),
]

PB_BINARY_SENSOR_TYPES = [
    SolarfocusBinarySensorEntityDescription(
        key="pb_door_contact",
        name="Pelletsboiler door",
        device_class=BinarySensorDeviceClass.DOOR,
        on_state="1",
    ),
]
