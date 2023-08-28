"""Water Heater for Solarfocus integration."""

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    WaterHeaterEntity,
    WaterHeaterEntityEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    STATE_OFF,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    BOILER_COMPONENT,
    BOILER_COMPONENT_PREFIX,
    BOILER_PREFIX,
    CONF_BOILER,
    DATA_COORDINATOR,
    DOMAIN,
)
from .entity import SolarfocusEntity, SolarfocusEntityDescription, create_description

_LOGGER = logging.getLogger(__name__)


PRESET_AUTO = "auto"

SOLARFOCUS_MODE_ALWAYS_OFF = 0
SOLARFOCUS_MODE_ALWAYS_ON = 1
SOLARFOCUS_MODE_MO_TO_SUN = 2
SOLARFOCUS_MODE_BLOCKWISE = 3
SOLARFOCUS_MODE_DAYWISE = 4

HA_DISPLAY_MODE_ALWAYS_ON = "An"
HA_DISPLAY_MODE_MO_TO_SUN = "Montag - Sonntag"
HA_DISPLAY_MODE_BLOCKWISE = "Blockweise"
HA_DISPLAY_MODE_DAYWISE = "Tageweise"

SOLARFOCUS_TO_HA_MODE = {
    SOLARFOCUS_MODE_ALWAYS_ON: HA_DISPLAY_MODE_ALWAYS_ON,
    SOLARFOCUS_MODE_ALWAYS_OFF: STATE_OFF,
    SOLARFOCUS_MODE_MO_TO_SUN: HA_DISPLAY_MODE_MO_TO_SUN,
    SOLARFOCUS_MODE_BLOCKWISE: HA_DISPLAY_MODE_BLOCKWISE,
    SOLARFOCUS_MODE_DAYWISE: HA_DISPLAY_MODE_DAYWISE,
}

HA_MODE_TO_SOLARFOCUS = {value: key for key, value in SOLARFOCUS_TO_HA_MODE.items()}

SOLARFOCUS_TEMP_WATER_MIN = 20
SOLARFOCUS_TEMP_WATER_MAX = 80


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Solarfocus config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    entities = []

    for i in range(config_entry.options[CONF_BOILER]):
        for description in WATER_HEATER_TYPES:
            _description = create_description(
                BOILER_PREFIX,
                BOILER_COMPONENT,
                BOILER_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusWaterHeaterEntity(coordinator, _description)
            entities.append(entity)

    async_add_entities(entities)


@dataclass
class SolarfocusWaterHeaterEntityDescription(
    SolarfocusEntityDescription, WaterHeaterEntityEntityDescription
):
    """Description of a Solarfocus number entity."""


class SolarfocusWaterHeaterEntity(SolarfocusEntity, WaterHeaterEntity):
    """Representation of a Solarfocus number entity."""

    _attr_has_entity_name = True

    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: SolarfocusWaterHeaterEntityDescription,
    ) -> None:
        """Initialize the Solarfocus select entity."""
        super().__init__(coordinator, description)

    @property
    def operation_list(self) -> list[str]:
        """Return list of operations."""
        return list(HA_MODE_TO_SOLARFOCUS)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._get_native_value("temperature")

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._get_native_value("target_temperature")

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        mode = self._get_native_value("mode")
        _LOGGER.debug("Current_operation: %s", mode)
        return SOLARFOCUS_TO_HA_MODE.get(mode)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return SOLARFOCUS_TEMP_WATER_MIN

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return SOLARFOCUS_TEMP_WATER_MAX

    @property
    def target_temperature_step(self) -> float:
        """Set target temperature."""
        return PRECISION_TENTHS

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._set_native_value("target_temperature", temp)
            _LOGGER.debug("Set Temperature: %s", temp)

    async def async_set_operation_mode(self, **kwargs) -> None:
        """Set new target temperature."""
        if (mode := kwargs.get(ATTR_OPERATION_MODE)) is not None:
            mapped_mode = HA_MODE_TO_SOLARFOCUS.get(mode)
            self._set_native_value("holding_mode", mapped_mode)
            _LOGGER.debug("Set Operation Mode: %s (mapped to: %s)", mode, mapped_mode)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn water heater on."""
        self._set_native_value("holding_mode", SOLARFOCUS_MODE_ALWAYS_ON)
        _LOGGER.debug("async_turn_on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn water heater off."""
        self._set_native_value("holding_mode", SOLARFOCUS_MODE_ALWAYS_OFF)
        _LOGGER.debug("async_turn_off")


WATER_HEATER_TYPES = [
    SolarfocusWaterHeaterEntityDescription(
        key="domestic_hot_water",
    )
]
