"""Numbers for Solarfocus integration."""

from dataclasses import dataclass
import logging

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTemperature
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
    CONF_PHOTOVOLTAIC,
    HEATING_CIRCUIT_COMPONENT,
    HEATING_CIRCUIT_COMPONENT_PREFIX,
    HEATING_CIRCUIT_PREFIX,
    PHOTOVOLTAIC_COMPONENT,
    PHOTOVOLTAIC_COMPONENT_PREFIX,
    PHOTOVOLTAIC_PREFIX,
)
from .coordinator import SolarfocusConfigEntry
from .entity import (
    SolarfocusEntity,
    SolarfocusEntityDescription,
    create_description,
    filterVersionAndSystem,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SolarfocusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Solarfocus config entry."""
    coordinator = config_entry.runtime_data
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

    if config_entry.options[CONF_PHOTOVOLTAIC]:
        for description in PHOTOVOLTAIC_NUMBER_TYPES:
            _description = create_description(
                PHOTOVOLTAIC_PREFIX,
                PHOTOVOLTAIC_COMPONENT,
                PHOTOVOLTAIC_COMPONENT_PREFIX,
                "",
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
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=0.0,
        native_max_value=80.0,
        native_step=0.5,
    ),
    SolarfocusNumberEntityDescription(
        key="target_room_temperature",
        icon="mdi:thermostat",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=0.0,
        native_max_value=45.0,
        native_step=0.5,
    ),
    SolarfocusNumberEntityDescription(
        key="indoor_temperature_external",
        icon="mdi:thermostat",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=0.0,
        native_max_value=45.0,
        native_step=0.5,
    ),
    SolarfocusNumberEntityDescription(
        key="indoor_humidity_external",
        icon="mdi:water-percent",
        device_class=NumberDeviceClass.HUMIDITY,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0.0,
        native_max_value=100.0,
        native_step=1.0,
    ),
]

BOILER_NUMBER_TYPES = [
    SolarfocusNumberEntityDescription(
        key="target_temperature",
        icon="mdi:thermostat",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=20.0,
        native_max_value=80.0,
        native_step=1,
    ),
]

PHOTOVOLTAIC_NUMBER_TYPES = [
    SolarfocusNumberEntityDescription(
        key="smart_meter",
        icon="mdi:meter-electric-outline",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=-32768,
        native_max_value=32767,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    SolarfocusNumberEntityDescription(
        key="photovoltaic",
        icon="mdi:solar-power",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=0,
        native_max_value=32767,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    SolarfocusNumberEntityDescription(
        key="grid_im_export",
        icon="mdi:transmission-tower",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=-32768,
        native_max_value=32767,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    SolarfocusNumberEntityDescription(
        key="hems_target_electrical_power",
        icon="mdi:home-lightning-bolt",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=0,
        native_max_value=32767,
        native_step=1,
        mode=NumberMode.BOX,
        min_required_version="26.020",
    ),
]
