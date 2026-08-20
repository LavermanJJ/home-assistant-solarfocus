"""Sensors for the Solarfocus integration."""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime
import logging
from typing import cast, override

from pysolarfocus import Systems

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfEnergy,
    UnitOfMass,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import (
    BIOMASS_BOILER_COMPONENT,
    BIOMASS_BOILER_COMPONENT_PREFIX,
    BOILER_COMPONENT,
    BOILER_COMPONENT_PREFIX,
    BUFFER_COMPONENT,
    BUFFER_COMPONENT_PREFIX,
    CONF_BIOMASS_BOILER,
    CONF_BOILER,
    CONF_BUFFER,
    CONF_FRESH_WATER_MODULE,
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
    CONF_PHOTOVOLTAIC,
    CONF_SOLAR,
    FRESH_WATER_MODULE_COMPONENT,
    FRESH_WATER_MODULE_COMPONENT_PREFIX,
    HEAT_PUMP_COMPONENT,
    HEAT_PUMP_COMPONENT_PREFIX,
    HEATING_CIRCUIT_COMPONENT,
    HEATING_CIRCUIT_COMPONENT_PREFIX,
    PHOTOVOLTAIC_COMPONENT,
    PHOTOVOLTAIC_COMPONENT_PREFIX,
    SOLAR_COMPONENT,
    SOLAR_COMPONENT_PREFIX,
    solar_count,
)
from .coordinator import SolarfocusConfigEntry, SolarfocusDataUpdateCoordinator
from .entity import (
    SolarfocusControllerEntity,
    SolarfocusEntity,
    SolarfocusEntityDescription,
    create_description,
    every_system_but,
    filterVersionAndSystem,
)
from .service_menu import installer_code, service_code

_LOGGER = logging.getLogger(__name__)

# Read-only platform: the coordinator polls the heating system, the entities
# themselves never call into it, so there is nothing to limit.
PARALLEL_UPDATES = 0


def enum_options(*groups: Iterable[int]) -> list[str]:
    """Return the states an enum sensor can report, as Home Assistant sees them.

    The state of an entity is a string, and the options of an enum sensor are the
    states it can take, so they have to be strings too. Listing the raw numbers
    instead leaves the state of the sensor outside of its own options, which is
    what the automation editor offers to compare against (issue #193).
    """
    return [str(value) for group in groups for value in group]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SolarfocusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize sensor platform from config entry."""
    coordinator = config_entry.runtime_data
    # The controller has entities of its own, which are not sensors of a
    # component, so the list is of what they have in common.
    entities: list[SolarfocusEntity] = []

    _LOGGER.debug("Sensor async_setup_entry: %s", config_entry.data)
    _LOGGER.debug("Sensor async_setup_entry: %s", config_entry.options)

    for i in range(config_entry.options[CONF_HEATING_CIRCUIT]):
        for description in HEATING_CIRCUIT_SENSOR_TYPES:
            _description = create_description(
                HEATING_CIRCUIT_COMPONENT,
                HEATING_CIRCUIT_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusSensor(coordinator, _description)
            entities.append(entity)

    for i in range(config_entry.options[CONF_BOILER]):
        for description in BOILER_SENSOR_TYPES:
            _description = create_description(
                BOILER_COMPONENT,
                BOILER_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusSensor(coordinator, _description)
            entities.append(entity)

    for i in range(config_entry.options[CONF_BUFFER]):
        for description in BUFFER_SENSOR_TYPES:
            _description = create_description(
                BUFFER_COMPONENT,
                BUFFER_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusSensor(coordinator, _description)
            entities.append(entity)

    if config_entry.options[CONF_HEATPUMP]:
        for description in HEATPUMP_SENSOR_TYPES:
            _description = create_description(
                HEAT_PUMP_COMPONENT,
                HEAT_PUMP_COMPONENT_PREFIX,
                "",
                description,
            )

            entity = SolarfocusSensor(coordinator, _description)
            entities.append(entity)

    if config_entry.options[CONF_BIOMASS_BOILER]:
        for description in BIOMASS_BOILER_SENSOR_TYPES:
            _description = create_description(
                BIOMASS_BOILER_COMPONENT,
                BIOMASS_BOILER_COMPONENT_PREFIX,
                "",
                description,
            )

            entity = SolarfocusSensor(coordinator, _description)
            entities.append(entity)

    if config_entry.options[CONF_PHOTOVOLTAIC]:
        for description in PHOTOVOLTAIC_SENSOR_TYPES:
            _description = create_description(
                PHOTOVOLTAIC_COMPONENT,
                PHOTOVOLTAIC_COMPONENT_PREFIX,
                "",
                description,
            )

            entity = SolarfocusSensor(coordinator, _description)
            entities.append(entity)

    if config_entry.options[CONF_SOLAR]:
        # The same count the library was built with, see `solar_count`
        count = solar_count(config_entry)

        for i in range(count):
            for description in SOLAR_SENSOR_TYPES:
                # Always use index since solar is now always a list in pysolarfocus
                # But for single instance, don't show the number in the entity name
                idx = str(i + 1)
                _description = create_description(
                    SOLAR_COMPONENT,
                    SOLAR_COMPONENT_PREFIX,
                    idx,
                    description,
                )

                if count == 1:
                    # One solar circuit keeps the unnumbered name and key it had
                    # before there could be four of them. The index stays on the
                    # description, the library addresses the component with it.
                    _description = replace(
                        _description,
                        device_idx="",
                        key=_description.key.replace("so1_", "so_"),
                    )

                entity = SolarfocusSensor(coordinator, _description)
                entities.append(entity)

    for i in range(config_entry.options[CONF_FRESH_WATER_MODULE]):
        for description in FRESH_WATER_MODULE_SENSOR_TYPES:
            _description = create_description(
                FRESH_WATER_MODULE_COMPONENT,
                FRESH_WATER_MODULE_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusSensor(coordinator, _description)
            entities.append(entity)

    # The controller is a device of its own, and the service menu codes are on
    # it: they are arithmetic rather than a reading of any component, so they
    # exist whatever the entry has configured.
    entities.append(SolarfocusServiceCodeSensor(coordinator, SERVICE_CODE_SENSOR_TYPE))
    entities.append(
        SolarfocusInstallerCodeSensor(coordinator, INSTALLER_CODE_SENSOR_TYPE)
    )

    async_add_entities(filterVersionAndSystem(config_entry, entities))


@dataclass(frozen=True, kw_only=True)
class SolarfocusSensorEntityDescription(
    SolarfocusEntityDescription, SensorEntityDescription
):
    """Description of a Solarfocus sensor entity."""


class SolarfocusSensor(SolarfocusEntity, SensorEntity):
    """Sensor for the Solarfocus."""

    entity_description: SolarfocusSensorEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolarfocusDataUpdateCoordinator,
        description: SolarfocusSensorEntityDescription,
    ) -> None:
        """Initialize a singular value sensor."""
        super().__init__(coordinator=coordinator, description=description)

    @property
    @override
    def native_value(self) -> StateType:
        """Return native value."""
        sensor = self.entity_description.item
        value = self._get_native_value(sensor)

        if self.device_class is SensorDeviceClass.ENUM and value is not None:
            # The state of an enum sensor has to be one of its options, and those
            # are the strings of the values the heating system reports. Going
            # through int() first keeps a register that holds a bool or a float
            # off the failing path: str(True) is "True" and str(3.0) is "3.0",
            # neither of which is an option, and core rejects the whole entity
            # for it.
            return str(int(value))

        return cast(StateType, value)


class SolarfocusControllerSensor(SolarfocusControllerEntity, SensorEntity):
    """A sensor of the controller itself, recomputed when the date turns over."""

    entity_description: SolarfocusSensorEntityDescription

    @override
    async def async_added_to_hass(self) -> None:
        """Write the new value when the date turns over.

        Both codes are weighted with the day of the week, so both change at
        midnight and neither changes with a poll. Local midnight, tracked as a
        wall clock time rather than as a span of 24 hours, so the day they
        change on is the day the controller is on across a daylight saving
        change.
        """
        await super().async_added_to_hass()

        self.async_on_remove(
            async_track_time_change(
                self.hass, self._async_new_day, hour=0, minute=0, second=0
            )
        )

    @callback
    def _async_new_day(self, now: datetime) -> None:
        """Report the code of the day that just started."""
        self.async_write_ha_state()


class SolarfocusServiceCodeSensor(SolarfocusControllerSensor):
    """The service code of the controller, for the day it is read on."""

    @property
    @override
    def native_value(self) -> StateType:
        """Return the code of today."""
        return service_code(dt_util.now())


class SolarfocusInstallerCodeSensor(SolarfocusControllerSensor):
    """The installer code, for the number the display of the controller shows.

    Half of a pair: the number it multiplies has no register behind it and no
    other source than `Installer code input`, so this one reports nothing at all
    while that entity is disabled. Enabling the two goes together.
    """

    @override
    async def async_added_to_hass(self) -> None:
        """Also follow the number, which is the other half of this code."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self.coordinator.displayed_number.subscribe(self.async_write_ha_state)
        )

    @property
    @override
    def native_value(self) -> StateType:
        """Return the code for what is on the display, if that has been entered.

        Unknown until it is: there is no number to multiply, and reporting a 0
        would read as a code rather than as the absence of one.
        """
        displayed = self.coordinator.displayed_number.value
        if displayed is None:
            return None

        return installer_code(displayed, dt_util.now())


# The two entities of this integration that read no register, so they name no
# component and carry no `item` - `native_value` computes them. Diagnostic: they
# say something about the controller rather than about the heating.
SERVICE_CODE_SENSOR_TYPE = SolarfocusSensorEntityDescription(
    key="service_code",
    translation_key="service_code",
    object_id_name="service code",
    entity_category=EntityCategory.DIAGNOSTIC,
)

INSTALLER_CODE_SENSOR_TYPE = SolarfocusSensorEntityDescription(
    key="installer_code",
    translation_key="installer_code",
    object_id_name="installer code",
    entity_category=EntityCategory.DIAGNOSTIC,
    # Off unless it is asked for: it reports nothing until the number from the
    # display has been entered, and that is a thing an installer does once.
    # Enabling this one alone leaves it unknown - the number entity that feeds
    # it is disabled by default too, and it is the only way in.
    entity_registry_enabled_default=False,
)


HEATING_CIRCUIT_SENSOR_TYPES = [
    SolarfocusSensorEntityDescription(
        key="supply_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SolarfocusSensorEntityDescription(
        key="room_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="mixer_valve",
        native_unit_of_measurement=PERCENTAGE,
    ),
    SolarfocusSensorEntityDescription(
        key="state",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(range(32), range(200, 229)),
    ),
]


BUFFER_SENSOR_TYPES = [
    SolarfocusSensorEntityDescription(
        key="top_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="bottom_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="state",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(range(8), range(200, 209)),
    ),
    SolarfocusSensorEntityDescription(
        key="mode",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(range(3)),
    ),
    SolarfocusSensorEntityDescription(
        key="x35_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        unsupported_systems=[
            Systems.VAMPAIR,
            Systems.PELLETELEGANCE,
            Systems.OCTOPLUS,
        ],
    ),
    SolarfocusSensorEntityDescription(
        key="external_top_temperature_x44",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        min_required_version="22.090",
        entity_registry_enabled_default=False,
        unsupported_systems=[Systems.THERMINATOR, Systems.ECOTOP],
    ),
    SolarfocusSensorEntityDescription(
        key="external_middle_temperature_x36",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        min_required_version="22.090",
        entity_registry_enabled_default=False,
        unsupported_systems=[Systems.THERMINATOR, Systems.ECOTOP],
    ),
    SolarfocusSensorEntityDescription(
        key="external_bottom_temperature_x35",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        min_required_version="22.090",
        entity_registry_enabled_default=False,
        unsupported_systems=[Systems.THERMINATOR, Systems.ECOTOP],
    ),
]

BOILER_SENSOR_TYPES = [
    SolarfocusSensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SolarfocusSensorEntityDescription(
        key="state",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(range(0, 14), range(200, 213)),
    ),
    SolarfocusSensorEntityDescription(
        key="mode",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(range(0, 5)),
        entity_registry_enabled_default=False,
    ),
    SolarfocusSensorEntityDescription(
        key="single_charge",
        device_class=SensorDeviceClass.ENUM,
        # -1 ("Locked") is a valid reading, same as for circulation below
        options=enum_options(range(-1, 2)),
    ),
    SolarfocusSensorEntityDescription(
        key="circulation",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(range(-1, 2)),
    ),
]

HEATPUMP_SENSOR_TYPES = [
    SolarfocusSensorEntityDescription(
        key="outdoor_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="supply_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="return_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="flow_rate",
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="compressor_speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="thermal_energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SolarfocusSensorEntityDescription(
        key="thermal_energy_drinking_water",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SolarfocusSensorEntityDescription(
        key="thermal_energy_heating",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SolarfocusSensorEntityDescription(
        key="electrical_energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SolarfocusSensorEntityDescription(
        key="electrical_energy_drinking_water",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SolarfocusSensorEntityDescription(
        key="electrical_energy_heating",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SolarfocusSensorEntityDescription(
        key="electrical_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="thermal_power_cooling",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="thermal_power_heating",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="thermal_energy_cooling",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SolarfocusSensorEntityDescription(
        key="electrical_energy_cooling",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SolarfocusSensorEntityDescription(
        key="vampair_state",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(range(0, 13)),
    ),
    SolarfocusSensorEntityDescription(
        key="cop_cooling",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SolarfocusSensorEntityDescription(
        key="cop_heating",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SolarfocusSensorEntityDescription(
        key="performance_overall",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SolarfocusSensorEntityDescription(
        key="performance_overall_heating",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SolarfocusSensorEntityDescription(
        key="performance_overall_drinking_water",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
]

PHOTOVOLTAIC_SENSOR_TYPES = [
    SolarfocusSensorEntityDescription(
        key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="house_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="heatpump_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="grid_import",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="grid_export",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]

BIOMASS_BOILER_SENSOR_TYPES = [
    SolarfocusSensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(range(0, 60), range(200, 247), range(300, 345)),
    ),
    SolarfocusSensorEntityDescription(
        key="message_number",
        device_class=SensorDeviceClass.ENUM,
        # The 200-range mirrors the 0-range as "acknowledged", and 2010 is a
        # standalone code. All three blocks are translated, so all three have to
        # be listed or core rejects the state -- see issue #165.
        options=enum_options(range(0, 88), range(200, 288), [2010]),
    ),
    SolarfocusSensorEntityDescription(
        key="cleaning",
        native_unit_of_measurement=PERCENTAGE,
    ),
    SolarfocusSensorEntityDescription(
        key="ash_container",
        native_unit_of_measurement=PERCENTAGE,
    ),
    SolarfocusSensorEntityDescription(
        key="outdoor_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="boiler_operating_mode",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(range(0, 6)),
        unsupported_systems=every_system_but(Systems.THERMINATOR),
    ),
    SolarfocusSensorEntityDescription(
        key="octoplus_buffer_temperature_bottom",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        # Register 2410 is the buffer only on an octoplus. On every other
        # Sigmatek boiler bar the vampair it is the return flow temperature -
        # a different measurement at the same address, which has an entity of
        # its own below rather than this one under a name that would misread it.
        unsupported_systems=every_system_but(Systems.OCTOPLUS),
    ),
    SolarfocusSensorEntityDescription(
        key="return_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        # The other half of register 2410, and the reason gating the buffer
        # bottom to the octoplus was only half the fix: the boilers that were
        # reporting a return flow temperature under the buffer's name get it
        # back under its own. The document grants it to "alle anderen Sigmatek
        # Kessel (ohne vampair)" bar the therminator, where 2410 is nicht
        # belegt - which leaves the EcoTop and the Pellet Elegance.
        unsupported_systems=every_system_but(
            Systems.ECOTOP, Systems.PELLETELEGANCE
        ),
    ),
    SolarfocusSensorEntityDescription(
        key="octoplus_buffer_temperature_top",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        unsupported_systems=every_system_but(Systems.OCTOPLUS),
    ),
    SolarfocusSensorEntityDescription(
        key="log_wood",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(range(0, 2)),
        unsupported_systems=every_system_but(Systems.THERMINATOR),
    ),
    SolarfocusSensorEntityDescription(
        key="pellet_usage_last_fill",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        min_required_version="23.010",
    ),
    SolarfocusSensorEntityDescription(
        key="pellet_usage_total",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        min_required_version="23.010",
    ),
    SolarfocusSensorEntityDescription(
        key="heat_energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        min_required_version="23.010",
    ),
]

SOLAR_SENSOR_TYPES = [
    SolarfocusSensorEntityDescription(
        key="collector_temperature_1",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="collector_temperature_2",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="collector_supply_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="collector_return_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="flow_heat_meter",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="current_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="current_yield_heat_meter",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SolarfocusSensorEntityDescription(
        key="today_yield",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SolarfocusSensorEntityDescription(
        key="buffer_sensor_1",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="buffer_sensor_2",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="buffer_sensor_3",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarfocusSensorEntityDescription(
        key="state",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(range(0, 19), range(200, 223)),
    ),
]

FRESH_WATER_MODULE_SENSOR_TYPES = [
    SolarfocusSensorEntityDescription(
        key="state",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(range(0, 5)),
        min_required_version="23.020",
    ),
    SolarfocusSensorEntityDescription(
        key="supply_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        min_required_version="23.040",
    ),
    SolarfocusSensorEntityDescription(
        key="flow_rate",
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        min_required_version="23.040",
    ),
    SolarfocusSensorEntityDescription(
        key="target_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        min_required_version="23.040",
    ),
]
