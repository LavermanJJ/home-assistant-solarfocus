"""Water Heater for Solarfocus integration"""

import logging
from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    TEMP_CELSIUS,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)


from .const import CONF_BOILER, DOMAIN
from .entity import SolarfocusEntity

_LOGGER = logging.getLogger(__name__)


PRESET_AUTO = "auto"

SOLARFOCUS_MODE_ALWAYS_OFF = 0
SOLARFOCUS_MODE_ALWAY_ON = 1
SOLARFOCUS_MODE_MO_TO_SUN = 2
SOLARFOCUS_MODE_BLOCKWISE = 3
SOLARFOCUS_MODE_DAYWISE = 4


HA_DISPLAY_MODE_ALWAY_ON = "Immer Aus"
HA_DISPLAY_MODE_ALWAYS_OFF = "Immer An"
HA_DISPLAY_MODE_MO_TO_SUN = "Montag - Sonntag"
HA_DISPLAY_MODE_BLOCKWISE = "Blockweise"
HA_DISPLAY_MODE_DAYWISE = "Tageweise"

HA_MODE_TO_SOLARFOCUS = {
    HA_DISPLAY_MODE_ALWAYS_OFF: SOLARFOCUS_MODE_ALWAYS_OFF,
    HA_DISPLAY_MODE_ALWAY_ON: SOLARFOCUS_MODE_ALWAY_ON,
    HA_DISPLAY_MODE_MO_TO_SUN: SOLARFOCUS_MODE_MO_TO_SUN,
    HA_DISPLAY_MODE_BLOCKWISE: SOLARFOCUS_MODE_BLOCKWISE,
    HA_DISPLAY_MODE_DAYWISE: SOLARFOCUS_MODE_DAYWISE,
}

SOLARFOCUS_TO_HA_MODE = {
    SOLARFOCUS_MODE_ALWAY_ON: HA_DISPLAY_MODE_ALWAYS_OFF,
    SOLARFOCUS_MODE_ALWAYS_OFF: HA_DISPLAY_MODE_ALWAY_ON,
    SOLARFOCUS_MODE_MO_TO_SUN: HA_DISPLAY_MODE_MO_TO_SUN,
    SOLARFOCUS_MODE_BLOCKWISE: HA_DISPLAY_MODE_BLOCKWISE,
    SOLARFOCUS_MODE_DAYWISE: HA_DISPLAY_MODE_DAYWISE,
}

SOLARFOCUS_TEMP_WATER_MIN = 20
SOLARFOCUS_TEMP_WATER_MAX = 80


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Solarfocus config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    if config_entry.data[CONF_BOILER]:
        for description in SOLARFOCUS_WATER_HEATER_TYPES:
            entity = SolarfocusWaterHeaterEntity(coordinator, description)
            entities.append(entity)

    async_add_entities(entities)


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
        description: EntityDescription,
    ) -> None:
        """Initialize the Solarfocus select entity."""
        super().__init__(coordinator, description)

        title = self.coordinator._entry.title
        name = self.entity_description.name
        self.entity_id = f"water_heater.{title}"
        self._attr_name = f"{name}"

    @property
    def operation_list(self) -> list[str]:
        return list(HA_MODE_TO_SOLARFOCUS)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        value = self.coordinator.api.bo1_temp
        return round(float(value), 2)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        value = self.coordinator.api.bo1_target_temperatur
        return round(float(value), 2)

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return SOLARFOCUS_TO_HA_MODE.get(self.coordinator.api.bo1_mode)

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
        """Set target temperature"""
        return PRECISION_TENTHS

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            _LOGGER.info("Set Temperature: %s", temp)
            await self.coordinator.update_bo1_target_temperatur(round(float(temp), 2))

    async def async_set_operation_mode(self, **kwargs) -> None:
        """Set new target temperature."""
        if (mode := kwargs.get(ATTR_OPERATION_MODE)) is not None:
            mapped_mode = HA_MODE_TO_SOLARFOCUS.get(mode)
            _LOGGER.info("Set Operation Mode: %s (mapped to: %s)", mode, mapped_mode)
            await self.coordinator.update_bo1_mode_holding(mapped_mode)


SOLARFOCUS_WATER_HEATER_TYPES = [
    EntityDescription(
        key="bo_temperature",
        name="Water Heater",
    )
]
