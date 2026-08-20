"""Binary Sensor for Solarfocus integration."""

from dataclasses import dataclass
import logging
from typing import override

from pysolarfocus import Systems

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    BIOMASS_BOILER_COMPONENT,
    BIOMASS_BOILER_COMPONENT_PREFIX,
    BUFFER_COMPONENT,
    BUFFER_COMPONENT_PREFIX,
    CIRCULATION_COMPONENT,
    CIRCULATION_COMPONENT_PREFIX,
    CONF_BIOMASS_BOILER,
    CONF_BUFFER,
    CONF_CIRCULATION,
    CONF_DIFFERENTIAL_MODULE,
    CONF_FRESH_WATER_MODULE,
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
    CONF_PHOTOVOLTAIC,
    DIFFERENTIAL_MODULE_COMPONENT,
    DIFFERENTIAL_MODULE_COMPONENT_PREFIX,
    FRESH_WATER_MODULE_COMPONENT,
    FRESH_WATER_MODULE_COMPONENT_PREFIX,
    HEAT_PUMP_COMPONENT,
    HEAT_PUMP_COMPONENT_PREFIX,
    HEATING_CIRCUIT_COMPONENT,
    HEATING_CIRCUIT_COMPONENT_PREFIX,
    PHOTOVOLTAIC_COMPONENT,
    PHOTOVOLTAIC_COMPONENT_PREFIX,
    component_count,
)
from .coordinator import SolarfocusConfigEntry, SolarfocusDataUpdateCoordinator
from .entity import (
    SolarfocusEntity,
    SolarfocusEntityDescription,
    create_description,
    every_system_but,
    filterVersionAndSystem,
)

_LOGGER = logging.getLogger(__name__)

# Read-only platform: the coordinator polls the heating system, the entities
# themselves never call into it, so there is nothing to limit.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SolarfocusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Solarfocus config entry."""
    coordinator = config_entry.runtime_data
    entities = []

    for i in range(config_entry.options[CONF_HEATING_CIRCUIT]):
        for description in HEATING_CIRCUIT_BINARY_SENSOR_TYPES:
            _description = create_description(
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
                BIOMASS_BOILER_COMPONENT,
                BIOMASS_BOILER_COMPONENT_PREFIX,
                "",
                description,
            )

            entity = SolarfocusBinarySensorEntity(coordinator, _description)
            entities.append(entity)

    if config_entry.options[CONF_PHOTOVOLTAIC]:
        for description in PHOTOVOLTAIC_BINARY_SENSOR_TYPES:
            _description = create_description(
                PHOTOVOLTAIC_COMPONENT,
                PHOTOVOLTAIC_COMPONENT_PREFIX,
                "",
                description,
            )

            entity = SolarfocusBinarySensorEntity(coordinator, _description)
            entities.append(entity)

    for i in range(config_entry.options[CONF_FRESH_WATER_MODULE]):
        for description in FRESH_WATER_MODULE_BINARY_SENSOR_TYPES:
            _description = create_description(
                FRESH_WATER_MODULE_COMPONENT,
                FRESH_WATER_MODULE_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusBinarySensorEntity(coordinator, _description)
            entities.append(entity)

    for i in range(component_count(config_entry, CONF_CIRCULATION)):
        for description in CIRCULATION_BINARY_SENSOR_TYPES:
            _description = create_description(
                CIRCULATION_COMPONENT,
                CIRCULATION_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusBinarySensorEntity(coordinator, _description)
            entities.append(entity)

    for i in range(component_count(config_entry, CONF_DIFFERENTIAL_MODULE)):
        for description in DIFFERENTIAL_MODULE_BINARY_SENSOR_TYPES:
            _description = create_description(
                DIFFERENTIAL_MODULE_COMPONENT,
                DIFFERENTIAL_MODULE_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusBinarySensorEntity(coordinator, _description)
            entities.append(entity)

    async_add_entities(filterVersionAndSystem(config_entry, entities))


@dataclass(frozen=True, kw_only=True)
class SolarfocusBinarySensorEntityDescription(
    SolarfocusEntityDescription, BinarySensorEntityDescription
):
    """Description of a Solarfocus binary sensor entity."""

    # Every binary sensor names the register value it reads as `on`.
    on_state: str


class SolarfocusBinarySensorEntity(SolarfocusEntity, BinarySensorEntity):
    """Representation of a Solarfocus binary sensor entity."""

    entity_description: SolarfocusBinarySensorEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolarfocusDataUpdateCoordinator,
        description: SolarfocusBinarySensorEntityDescription,
    ) -> None:
        """Initialize the Solarfocus number entity."""
        super().__init__(coordinator, description)

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        binary_sensor = self.entity_description.item
        value = self._get_native_value(binary_sensor)
        on_state = self.entity_description.on_state
        return int(value) == int(on_state)


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
        on_state="1",
    ),
    SolarfocusBinarySensorEntityDescription(
        key="boiler_charge",
        device_class=BinarySensorDeviceClass.RUNNING,
        on_state="1",
    ),
]

# Register 2405 is reported the other way round on a therminator than on an
# EcoTop, which is why the door is described twice. Both descriptions carry the
# same key, so they build the same `unique_id` and only one of the two may ever
# survive the system filter: each names the systems it was measured on.
#
# A Pellet Elegance (15 kW, v25.110) was read at the door for #217 and answers
# 1 open, 0 closed - the therminator way round, so it joins that description.
# The other Pellet Elegance in that thread reads 2 in both positions, on a
# boiler whose owner reports the contact does not work; 2 is neither state
# below, so it stays "closed" rather than flapping, which is the right way for
# an unfitted contact to fail.
#
# The Octoplus is still unmeasured and so still has no door contact. Guessing
# between two polarities gives a sensor that is confidently wrong half the
# time, which is worse than not having one.
BIOMASS_BOILER_BINARY_SENSOR_TYPES = [
    SolarfocusBinarySensorEntityDescription(
        key="door_contact",
        device_class=BinarySensorDeviceClass.DOOR,
        on_state="1",
        unsupported_systems=every_system_but(
            Systems.THERMINATOR, Systems.PELLETELEGANCE
        ),
    ),
    SolarfocusBinarySensorEntityDescription(
        key="door_contact",
        device_class=BinarySensorDeviceClass.DOOR,
        on_state="0",
        unsupported_systems=every_system_but(Systems.ECOTOP),
    ),
]

PHOTOVOLTAIC_BINARY_SENSOR_TYPES = [
    SolarfocusBinarySensorEntityDescription(
        key="overcharge_possible",
        on_state="1",
    ),
    SolarfocusBinarySensorEntityDescription(
        key="overcharge_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        on_state="1",
    ),
]

FRESH_WATER_MODULE_BINARY_SENSOR_TYPES = [
    SolarfocusBinarySensorEntityDescription(
        key="valve",
        device_class=BinarySensorDeviceClass.OPENING,
        on_state="1",
        min_required_version="23.040",
    ),
]

CIRCULATION_BINARY_SENSOR_TYPES = [
    SolarfocusBinarySensorEntityDescription(
        key="pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        on_state="1",
        min_required_version="25.030",
    ),
]

# The relay each control loop switches, which is the output the differential
# module exists for - a pump or a valve, whatever the installer wired to it.
DIFFERENTIAL_MODULE_BINARY_SENSOR_TYPES = [
    SolarfocusBinarySensorEntityDescription(
        key="relay_control_loop_o1",
        device_class=BinarySensorDeviceClass.RUNNING,
        on_state="1",
        min_required_version="25.030",
    ),
    SolarfocusBinarySensorEntityDescription(
        key="relay_control_loop_o2",
        device_class=BinarySensorDeviceClass.RUNNING,
        on_state="1",
        min_required_version="25.030",
    ),
]
