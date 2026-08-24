"""Binary Sensor for Solarfocus integration."""

from dataclasses import dataclass, replace
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
    CONF_DOOR_CONTACT_INVERTED,
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
        # See #91: the door contact reads backwards on an installation wired
        # the other way round at its 3-pin terminal, which nothing read over
        # Modbus can tell apart from a correctly wired one. This is the escape
        # hatch for that installation - every other one leaves it off and
        # reads register 2405 the way the specification documents it.
        door_contact_inverted = config_entry.options[CONF_DOOR_CONTACT_INVERTED]
        for description in BIOMASS_BOILER_BINARY_SENSOR_TYPES:
            if description.key == "door_contact" and door_contact_inverted:
                description = replace(description, on_state="0")

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

# Register 2405 answers 1 open, 0 closed - the specification says so, and #91
# confirmed it by measuring an EcoTop directly (register 2405 on QModMaster,
# the controller's own display, and pysolarfocus all agreed) after it turned
# out this integration had the EcoTop the other way round since #79/#80. A
# Pellet Elegance (15 kW, v25.110) was read at the door for #217 and agrees.
#
# The other Pellet Elegance in the #217 thread read 2 in both door positions,
# on a boiler whose owner reports the contact does not work; 2 is neither
# state, so an unfitted contact reads "closed" rather than flapping, which is
# the right way for it to fail.
#
# `CONF_DOOR_CONTACT_INVERTED` exists because the door contact is wired
# through a 3-pin terminal - normally-open or normally-closed is an
# installer's choice, not something a register read can tell apart - so a
# boiler still reading backwards after this is a wiring fact about one
# installation, not evidence the specification is wrong again.
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
            Systems.THERMINATOR, Systems.PELLETELEGANCE, Systems.ECOTOP
        ),
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
