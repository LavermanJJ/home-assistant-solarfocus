"""Numbers for Solarfocus integration"""

from dataclasses import dataclass
import logging

from homeassistant.components.sensor import SensorDeviceClass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
)
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
from .entity import SolarfocusEntity, SolarfocusEntityDescription, create_description

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Solarfocus config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    entities = []

    for i in range(config_entry.data[CONF_HEATING_CIRCUIT]):
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

    for i in range(config_entry.data[CONF_BOILER]):
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

    async_add_entities(entities)


@dataclass
class SolarfocusNumberEntityDescription(
    SolarfocusEntityDescription, NumberEntityDescription
):
    """Description of a Solarfocus number entity"""


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
        self._attr_native_value = value

        idx = int(self.entity_description.component_idx) - 1
        component = getattr(self.coordinator.api, self.entity_description.component)[
            idx
        ]
        name = self.entity_description.item
        _LOGGER.debug(
            "Async_set_native_value - idx: %s, component: %s, sensor: %s",
            idx,
            self.entity_description.component,
            name,
        )
        number = getattr(component, name)
        number.set_unscaled_value(value)
        number.commit()
        component.update()

        self.async_write_ha_state()

    @property
    def native_value(self):
        """Return the current state."""
        idx = int(self.entity_description.component_idx) - 1
        component = getattr(self.coordinator.api, self.entity_description.component)[
            idx
        ]
        sensor = self.entity_description.item
        _LOGGER.debug(
            "Native_value - idx: %s, component: %s, sensor: %s",
            idx,
            self.entity_description.component,
            sensor,
        )
        value = getattr(component, sensor).scaled_value
        if isinstance(value, float):
            try:
                rounded_value = round(float(value), 2)
                return rounded_value
            except ValueError:
                return value
        return value


HEATING_CIRCUIT_NUMBER_TYPES = [
    SolarfocusNumberEntityDescription(
        key="target_supply_temperature",
        icon="mdi:thermostat",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=TEMP_CELSIUS,
        native_min_value=0.0,
        native_max_value=35.0,
        native_step=0.5,
    ),
]

BOILER_NUMBER_TYPES = [
    SolarfocusNumberEntityDescription(
        key="target_temperature",
        icon="mdi:thermostat",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=TEMP_CELSIUS,
        native_min_value=20.0,
        native_max_value=80.0,
        native_step=1,
    ),
]
