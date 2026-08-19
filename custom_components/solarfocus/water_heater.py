"""Water Heater for Solarfocus integration."""

from dataclasses import dataclass
import logging
from typing import Any, cast, override

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    STATE_OFF,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BOILER_COMPONENT, BOILER_COMPONENT_PREFIX, CONF_BOILER
from .coordinator import SolarfocusConfigEntry, SolarfocusDataUpdateCoordinator
from .entity import SolarfocusEntity, SolarfocusEntityDescription, create_description

_LOGGER = logging.getLogger(__name__)

# Every write is a read-modify-commit sequence on a component, so two of them
# running at once can interleave on the same registers. This limits Home
# Assistant to one in-flight service call per platform; it does not cover the
# reads the coordinator does, which is why writes re-read their component.
PARALLEL_UPDATES = 1


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
    config_entry: SolarfocusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Solarfocus config entry."""
    coordinator = config_entry.runtime_data
    entities = []

    for i in range(config_entry.options[CONF_BOILER]):
        for description in WATER_HEATER_TYPES:
            _description = create_description(
                BOILER_COMPONENT,
                BOILER_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusWaterHeaterEntity(coordinator, _description)
            entities.append(entity)

    async_add_entities(entities)


@dataclass(frozen=True, kw_only=True)
class SolarfocusWaterHeaterEntityDescription(
    SolarfocusEntityDescription, WaterHeaterEntityDescription
):
    """Description of a Solarfocus number entity."""


class SolarfocusWaterHeaterEntity(SolarfocusEntity, WaterHeaterEntity):
    """Representation of a Solarfocus number entity."""

    entity_description: SolarfocusWaterHeaterEntityDescription

    _attr_has_entity_name = True

    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.ON_OFF
    )

    def __init__(
        self,
        coordinator: SolarfocusDataUpdateCoordinator,
        description: SolarfocusWaterHeaterEntityDescription,
    ) -> None:
        """Initialize the Solarfocus select entity."""
        super().__init__(coordinator, description)

    @property
    @override
    def operation_list(self) -> list[str]:
        """Return list of operations."""
        return list(HA_MODE_TO_SOLARFOCUS)

    @property
    @override
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    @override
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return cast(float | None, self._get_native_value("temperature"))

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return cast(float | None, self._get_native_value("target_temperature"))

    @property
    @override
    def current_operation(self) -> str | None:
        """Return current operation ie. heat, cool, idle."""
        mode = self._get_native_value("mode")
        _LOGGER.debug("Current_operation: %s", mode)
        return SOLARFOCUS_TO_HA_MODE.get(mode)

    @property
    @override
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return SOLARFOCUS_TEMP_WATER_MIN

    @property
    @override
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return SOLARFOCUS_TEMP_WATER_MAX

    @property
    @override
    def target_temperature_step(self) -> float:
        """Set target temperature."""
        return PRECISION_TENTHS

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._set_native_value("target_temperature", temp)
            _LOGGER.debug("Set Temperature: %s", temp)

    @override
    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target temperature."""
        mapped_mode = HA_MODE_TO_SOLARFOCUS.get(operation_mode)
        self._set_native_value("holding_mode", mapped_mode)
        _LOGGER.debug(
            "Set Operation Mode: %s (mapped to: %s)", operation_mode, mapped_mode
        )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn water heater on."""
        self._set_native_value("holding_mode", SOLARFOCUS_MODE_ALWAYS_ON)
        _LOGGER.debug("async_turn_on")

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn water heater off."""
        self._set_native_value("holding_mode", SOLARFOCUS_MODE_ALWAYS_OFF)
        _LOGGER.debug("async_turn_off")


WATER_HEATER_TYPES = [
    SolarfocusWaterHeaterEntityDescription(
        key="domestic_hot_water",
    )
]
