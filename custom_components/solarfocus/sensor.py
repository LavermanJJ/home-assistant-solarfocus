"""Sensors for the Solarfocus integration."""
from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfMass,
)

from .const import (
    BOILER_COMPONENT,
    BOILER_COMPONENT_PREFIX,
    BOILER_PREFIX,
    BUFFER_COMPONENT,
    BUFFER_COMPONENT_PREFIX,
    BUFFER_PREFIX,
    CONF_BOILER,
    CONF_BUFFER,
    CONF_FRESH_WATER_MODULE,
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
    CONF_PELLETSBOILER,
    CONF_PHOTOVOLTAIC,
    CONF_SOLAR,
    DATA_COORDINATOR,
    DOMAIN,
    FRESH_WATER_MODULE_COMPONENT,
    FRESH_WATER_MODULE_COMPONENT_PREFIX,
    FRESH_WATER_MODULE_PREFIX,
    HEAT_PUMP_COMPONENT,
    HEAT_PUMP_COMPONENT_PREFIX,
    HEAT_PUMP_PREFIX,
    HEATING_CIRCUIT_COMPONENT,
    HEATING_CIRCUIT_COMPONENT_PREFIX,
    HEATING_CIRCUIT_PREFIX,
    PELLETS_BOILER_COMPONENT,
    PELLETS_BOILER_COMPONENT_PREFIX,
    PELLETS_BOILER_PREFIX,
    PHOTOVOLTAIC_COMPONENT,
    PHOTOVOLTAIC_COMPONENT_PREFIX,
    PHOTOVOLTAIC_PREFIX,
    SOLAR_COMPONENT,
    SOLAR_COMPONENT_PREFIX,
    SOLAR_PREFIX,
    VOLUME_FLOW_RATE_LITER_PER_HOUR,
)
from .coordinator import SolarfocusDataUpdateCoordinator
from .entity import SolarfocusEntity, SolarfocusEntityDescription, create_description

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    """Initialize sensor platform from config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    entities = []

    _LOGGER.debug("Sensor async_setup_entry: %s", config_entry.data)
    _LOGGER.debug("Sensor async_setup_entry: %s", config_entry.options)

    for i in range(config_entry.options[CONF_HEATING_CIRCUIT]):
        for description in HEATING_CIRCUIT_SENSOR_TYPES:
            _description = create_description(
                HEATING_CIRCUIT_PREFIX,
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
                BOILER_PREFIX,
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
                BUFFER_PREFIX,
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
                HEAT_PUMP_PREFIX,
                HEAT_PUMP_COMPONENT,
                HEAT_PUMP_COMPONENT_PREFIX,
                "",
                description,
            )

            entity = SolarfocusSensor(coordinator, _description)
            entities.append(entity)

    if config_entry.options[CONF_PELLETSBOILER]:
        for description in PELLETS_BOILER_SENSOR_TYPES:
            _description = create_description(
                PELLETS_BOILER_PREFIX,
                PELLETS_BOILER_COMPONENT,
                PELLETS_BOILER_COMPONENT_PREFIX,
                "",
                description,
            )

            entity = SolarfocusSensor(coordinator, _description)
            entities.append(entity)

    if config_entry.options[CONF_PHOTOVOLTAIC]:
        for description in PHOTOVOLTAIC_SENSOR_TYPES:
            _description = create_description(
                PHOTOVOLTAIC_PREFIX,
                PHOTOVOLTAIC_COMPONENT,
                PHOTOVOLTAIC_COMPONENT_PREFIX,
                "",
                description,
            )

            entity = SolarfocusSensor(coordinator, _description)
            entities.append(entity)

    if config_entry.options[CONF_SOLAR]:
        for description in SOLAR_SENSOR_TYPES:
            _description = create_description(
                SOLAR_PREFIX,
                SOLAR_COMPONENT,
                SOLAR_COMPONENT_PREFIX,
                "",
                description,
            )

            entity = SolarfocusSensor(coordinator, _description)
            entities.append(entity)

    for i in range(config_entry.options[CONF_FRESH_WATER_MODULE]):
        for description in FRESH_WATER_MODULE_SENSOR_TYPES:
            _description = create_description(
                FRESH_WATER_MODULE_PREFIX,
                FRESH_WATER_MODULE_COMPONENT,
                FRESH_WATER_MODULE_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusSensor(coordinator, _description)
            entities.append(entity)

    async_add_entities(entities)


@dataclass
class SolarfocusSensorEntityDescription(
    SolarfocusEntityDescription, SensorEntityDescription
):
    """Description of a Solarfocus sensor entity"""


class SolarfocusSensor(SolarfocusEntity, SensorEntity):
    """Sensor for the Solarfocus"""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolarfocusDataUpdateCoordinator,
        description: SolarfocusSensorEntityDescription,
    ) -> None:
        """Initialize a singular value sensor."""
        super().__init__(coordinator=coordinator, description=description)

    @property
    def native_value(self):
        """Return the current state."""
        component: None
        idx = -1

        if self.entity_description.component_idx:
            idx = int(self.entity_description.component_idx) - 1
            component = getattr(
                self.coordinator.api, self.entity_description.component
            )[idx]
        else:
            component = getattr(self.coordinator.api, self.entity_description.component)

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


HEATING_CIRCUIT_SENSOR_TYPES = [
    SensorEntityDescription(
        key="supply_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="room_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:home-thermometer-outline",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:water-percent",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="mixer_valve",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:valve",
    ),
    SensorEntityDescription(
        key="state",
        icon="mdi:radiator",
        device_class=SensorDeviceClass.ENUM,
        options=list(range(0, 32)) + list(range(200, 229)),
    ),
]


BUFFER_SENSOR_TYPES = [
    SensorEntityDescription(
        key="top_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="bottom_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer-low",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="state",
        icon="mdi:database",
        device_class=SensorDeviceClass.ENUM,
        options=list(range(0, 8)) + list(range(200, 209)),
    ),
    SensorEntityDescription(
        key="mode",
        icon="mdi:format-list-bulleted",
        device_class=SensorDeviceClass.ENUM,
        options=list(range(0, 3)),
    ),
]

BOILER_SENSOR_TYPES = [
    SensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer-high",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="state",
        icon="mdi:water-boiler",
        device_class=SensorDeviceClass.ENUM,
        options=list(range(0, 14)) + list(range(200, 213)),
    ),
    SensorEntityDescription(
        key="mode",
        icon="mdi:format-list-bulleted",
        device_class=SensorDeviceClass.ENUM,
        options=list(range(0, 5)),
    ),
    SensorEntityDescription(
        key="single_charge",
        icon="mdi:pump",
        device_class=SensorDeviceClass.ENUM,
        options=list(range(0,2)),
    ),
    SensorEntityDescription(
        key="circulation",
        icon="mdi:reload",
        device_class=SensorDeviceClass.ENUM,
        options=list(range(-1, 2)),
    ),
]

HEATPUMP_SENSOR_TYPES = [
    SensorEntityDescription(
        key="supply_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer-chevron-up",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="return_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer-chevron-down",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="flow_rate",
        native_unit_of_measurement=VOLUME_FLOW_RATE_LITER_PER_HOUR,
        icon="mdi:speedometer",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="compressor_speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        icon="mdi:gauge",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="thermal_energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:meter-gas",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="thermal_energy_drinking_water",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:meter-gas",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="thermal_energy_heating",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:meter-gas",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="electrical_energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:meter-electric",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="electrical_energy_drinking_water",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:meter-electric",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="electrical_energy_heating",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:meter-electric",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="electrical_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:lightning-bolt",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="thermal_power_cooling",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:snowflake",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="thermal_power_heating",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:fire",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="thermal_energy_cooling",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:meter-gas",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="electrical_energy_cooling",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:meter-electric",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="vampair_state",
        icon="mdi:heat-pump",
        device_class=SensorDeviceClass.ENUM,
        options=list(range(0, 13)),
    ),
    SensorEntityDescription(
        key="cop_cooling",
        icon="mdi:poll",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="cop_heating",
        icon="mdi:poll",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="performance_overall",
        icon="mdi:poll",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="performance_overall_heating",
        icon="mdi:poll",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="performance_overall_drinking_water",
        icon="mdi:poll",
        state_class=SensorStateClass.MEASUREMENT,
    ),
]

PHOTOVOLTAIC_SENSOR_TYPES = [
    SensorEntityDescription(
        key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:solar-power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="house_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:home-lightning-bolt-outline",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="heatpump_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:heat-pump-outline",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="grid_import",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:home-import-outline",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="grid_export",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:home-export-outline",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]

PELLETS_BOILER_SENSOR_TYPES = [
    SensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="status",
        icon="mdi:fire-circle",
        device_class=SensorDeviceClass.ENUM,
        options=list(range(0, 60)) + list(range(200, 247)) + list(range(300, 345)),
    ),
    SensorEntityDescription(
        key="message_number",
        icon="mdi:message-text-outline",
        device_class=SensorDeviceClass.ENUM,
        options=list(range(0, 88)),
    ),
    SensorEntityDescription(
        key="cleaning",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:broom",
    ),
    SensorEntityDescription(
        key="ash_container",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:trash-can-outline",
    ),
    SensorEntityDescription(
        key="outdoor_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="boiler_operating_mode",
        icon="mdi:format-list-bulleted",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENUM,
        options=list(range(0, 6)),
    ),
    SensorEntityDescription(
        key="octoplus_buffer_temperature_bottom",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer-low",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="octoplus_buffer_temperature_top",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="log_wood",
        icon="mdi:format-list-bulleted",
        device_class=SensorDeviceClass.ENUM,
        options=list(range(0, 2)),
    ),
    SensorEntityDescription(
        key="pellet_usage_last_fill",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        icon="mdi:gradient-vertical",
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pellet_usage_total",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        icon="mdi:alpha-t-box",
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="heat_energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:meter-gas",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
]

SOLAR_SENSOR_TYPES = [
    SensorEntityDescription(
        key="collector_temperature_1",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="collector_temperature_2",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="collector_supply_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="collector_return_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="flow_heat_meter",
        native_unit_of_measurement=VOLUME_FLOW_RATE_LITER_PER_HOUR,
        icon="mdi:speedometer",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="curent_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        icon="mdi:lightning-bolt",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="curent_yield_heat_meter",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        icon="mdi:meter-electric",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="today_yield",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        icon="mdi:meter-electric",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="buffer_sensor_1",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="buffer_sensor_2",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="buffer_sensor_3",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="state",
        icon="mdi:solar-power-variant",
        device_class=SensorDeviceClass.ENUM,
        options=list(range(0, 19)) + list(range(200, 223)),
    ),
]

FRESH_WATER_MODULE_SENSOR_TYPES = [
    SensorEntityDescription(
        key="state",
        icon="mdi:faucet",
        device_class=SensorDeviceClass.ENUM,
        options=list(range(0, 5)),
    ),
]
