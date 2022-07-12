"""Sensors for the Solarfocus integration."""
import logging

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
)

from .const import (
    CONF_BOILER,
    CONF_BUFFER,
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
    CONF_PHOTOVOLTAIC,
    DOMAIN,
)
from .coordinator import SolarfocusDataUpdateCoordinator
from .entity import SolarfocusEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
):
    """Initialize sensor platform from config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    if config_entry.data[CONF_HEATING_CIRCUIT]:
        for description in HEATING_CIRCUIT_SENSOR_TYPES:
            entity = SolarfocusSensor(coordinator, description)
            entities.append(entity)

    if config_entry.data[CONF_BUFFER]:
        for description in BUFFER_SENSOR_TYPES:
            entity = SolarfocusSensor(coordinator, description)
            entities.append(entity)

    if config_entry.data[CONF_BOILER]:
        for description in BOILER_SENSOR_TYPES:
            entity = SolarfocusSensor(coordinator, description)
            entities.append(entity)

    if config_entry.data[CONF_HEATPUMP]:
        for description in HEATPUMP_SENSOR_TYPES:
            entity = SolarfocusSensor(coordinator, description)
            entities.append(entity)

    if config_entry.data[CONF_PHOTOVOLTAIC]:
        for description in PV_SENSOR_TYPES:
            entity = SolarfocusSensor(coordinator, description)
            entities.append(entity)

    async_add_entities(entities)


class SolarfocusSensor(SolarfocusEntity, SensorEntity):
    """Sensor for the Solarfocus"""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolarfocusDataUpdateCoordinator,
        description: SensorEntityDescription,
    ):
        """Initialize a singular value sensor."""
        super().__init__(coordinator=coordinator, description=description)

        title = self.coordinator._entry.title
        key = self.entity_description.key
        name = self.entity_description.name

"""Supported sensor types."""
HEATING_CIRCUIT_SENSOR_TYPES = [
    SensorEntityDescription(
        key="hc1_supply_temp",
        name="Heating supply temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="hc1_room_temp",
        name="Heating room temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        icon="mdi:home-thermometer-outline",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="hc1_humidity",
        name="Heating humidity",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:water-percent",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="hc1_limit_thermostat",
        name="Heating limit thermostat",
        icon="mdi:thermostat",
        device_class="solarfocus__limit",
    ),
    SensorEntityDescription(
        key="hc1_circulator_pump",
        name="Heating circulator pump",
        icon="mdi:pump",
    ),
    SensorEntityDescription(
        key="hc1_mixer_valve",
        name="Heating mixer valve",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:valve",
    ),
    SensorEntityDescription(
        key="hc1_state",
        name="Heating state",
        icon="mdi:radiator",
        device_class="solarfocus__hcstate",
    ),
]


BUFFER_SENSOR_TYPES = [
    SensorEntityDescription(
        key="bu1_top_temp",
        name="Buffer top temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="bu1_bottom_temp",
        name="Buffer bottom temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        icon="mdi:thermometer-low",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="bu1_pump",
        name="Buffer pump",
        icon="mdi:pump",
        device_class="solarfocus__pump",
    ),
    SensorEntityDescription(
        key="bu1_state",
        name="Buffer state",
        icon="mdi:database",
        device_class="solarfocus__bustate",
    ),
    SensorEntityDescription(
        key="bu1_mode",
        name="Buffer mode",
        icon="mdi:format-list-bulleted",
        device_class="solarfocus__bumode",
    ),
]

BOILER_SENSOR_TYPES = [
    SensorEntityDescription(
        key="bo1_temp",
        name="Boiler temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        icon="mdi:thermometer-high",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="bo1_state",
        name="Boiler state",
        icon="mdi:water-boiler",
        device_class="solarfocus__bostate",
    ),
    SensorEntityDescription(
        key="bo1_mode",
        name="Boiler mode",
        icon="mdi:format-list-bulleted",
        device_class="solarfocus__bomode",
    ),
    SensorEntityDescription(
        key="bo1_single_charge",
        name="Boiler single charge request",
        icon="mdi:pump",
    ),
    SensorEntityDescription(
        key="bo1_ciruclation",
        name="Boiler circulation",
        icon="mdi:reload",
        device_class="solarfocus__bocirculation",
    ),
]

HEATPUMP_SENSOR_TYPES = [
    SensorEntityDescription(
        key="hp_supply_temp",
        name="Heatpump supply temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="hp_return_temp",
        name="Heatpump return temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="hp_flow_rate",
        name="Heatpump flow rate",
        native_unit_of_measurement=VOLUME_FLOW_RATE_LITER_PER_HOUR,
        icon="mdi:speedometer",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="hp_compressor_speed",
        name="Heatpump compressor speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MIN,
        icon="mdi:gauge",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="hp_evu_lock_active",
        name="Heatpump evu lock",
        icon="mdi:lock",
        device_class="solarfocus__evu",
    ),
    SensorEntityDescription(
        key="hp_defrost_active",
        name="Heatpump defrost",
        icon="mdi:snowflake-melt",
        device_class="solarfocus__defrost",
    ),
    SensorEntityDescription(
        key="hp_boiler_charge",
        name="Heatpump boiler charge",
        icon="mdi:water-boiler",
        device_class="solarfocus__boiler",
    ),
    SensorEntityDescription(
        key="hp_thermal_energy_total",
        name="Heat pump total thermal energy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:meter-gas-outline",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="hp_thermal_energy_drinking_water",
        name="Heat pump drinking water thermal energy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:meter-gas-outline",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="hp_thermal_energy_heating",
        name="Heat pump heating thermal energy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:meter-gas-outline",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="hp_electrical_energy_total",
        name="Heat pump total electrical energy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:meter-electric-outline",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="hp_electrical_energy_drinking_water",
        name="Heat pump drinking water electrical energy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:meter-electric-outline",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="hp_eletrical_energy_heating",
        name="Heat pump heating electrical energy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:meter-electric-outline",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="hp_electrical_power",
        name="Heat pump electrical power",
        native_unit_of_measurement=POWER_WATT,
        icon="mdi:lightning-bolt",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="hp_thermal_power_cooling",
        name="Heat pump cooling thermal power",
        native_unit_of_measurement=POWER_WATT,
        icon="mdi:snowflake",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="hp_thermal_power_heating",
        name="Heat pump heating thermal power",
        native_unit_of_measurement=POWER_WATT,
        icon="mdi:fire",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="hp_thermal_energy_cooling",
        name="Heat pump cooling thermal energy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:meter-gas-outline",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="hp_electrical_energy_cooling",
        name="Heat pump cooling electrical energy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:meter-gas-outline",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="hp_cop",
        name="Heat pump coefficient of performance",
        icon="mdi:poll",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="hp_vampair_state",
        name="Heat pump state",
        icon="mdi:heat-pump-outline",
        device_class="solarfocus__hpstate",
    ),
]

PV_SENSOR_TYPES = [
    SensorEntityDescription(
        key="pv_power",
        name="Photovoltaic power",
        native_unit_of_measurement=POWER_WATT,
        icon="mdi:solar-power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pv_house_consumption",
        name="Photovoltaic house consumption",
        native_unit_of_measurement=POWER_WATT,
        icon="mdi:home-lightning-bolt-outline",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pv_heatpump_consumption",
        name="Photovoltaic heatpump consumption",
        native_unit_of_measurement=POWER_WATT,
        icon="mdi:heat-pump-outline",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pv_grid_import",
        name="Photovoltaic grid import",
        native_unit_of_measurement=POWER_WATT,
        icon="mdi:home-import-outline",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pv_grid_export",
        name="Photovoltaic grid export",
        native_unit_of_measurement=POWER_WATT,
        icon="mdi:home-export-outline",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]
