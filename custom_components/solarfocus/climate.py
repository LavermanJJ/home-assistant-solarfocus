"""Climate for Solarfocus integration."""

from dataclasses import dataclass
import logging

from homeassistant.components.climate import ClimateEntity, ClimateEntityDescription
from homeassistant.components.climate.const import (
    PRESET_COMFORT,
    PRESET_ECO,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_HEATING_CIRCUIT,
    DATA_COORDINATOR,
    DOMAIN,
    HEATING_CIRCUIT_COMPONENT,
    HEATING_CIRCUIT_COMPONENT_PREFIX,
    HEATING_CIRCUIT_PREFIX,
)
from .entity import SolarfocusEntity, SolarfocusEntityDescription, create_description

_LOGGER = logging.getLogger(__name__)


PRESET_AUTO = "auto"
PRESET_OFF = "off"

SOLARFOCUS_MODE_TO_PRESET = {
    0: PRESET_COMFORT,
    1: PRESET_ECO,
    2: PRESET_AUTO,
    3: PRESET_OFF,
}

PRESET_TO_SOLARFOCUS_MODE = {
    value: key for key, value in SOLARFOCUS_MODE_TO_PRESET.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Solarfocus config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    entities = []

    for i in range(config_entry.options[CONF_HEATING_CIRCUIT]):
        for description in CLIMATE_TYPES:
            _description = create_description(
                HEATING_CIRCUIT_PREFIX,
                HEATING_CIRCUIT_COMPONENT,
                HEATING_CIRCUIT_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusClimateEntity(coordinator, _description)
            entities.append(entity)

    async_add_entities(entities)


@dataclass
class SolarfocusClimateEntityDescription(
    SolarfocusEntityDescription, ClimateEntityDescription
):
    """Description of a Solarfocus number entity."""


class SolarfocusClimateEntity(SolarfocusEntity, ClimateEntity):
    """Representation of a Solarfocus number entity."""

    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE
        # | ClimateEntityFeature.TARGET_TEMPERATURE
    )

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: SolarfocusClimateEntityDescription,
    ) -> None:
        """Initialize the Solarfocus select entity."""
        super().__init__(coordinator, description)

    @property
    def max_temp(self) -> float:
        """Return max temperature."""
        if self._get_native_value("cooling"):
            return 35.0
        return 45.0

    @property
    def min_temp(self) -> float:
        """Return minimum temperature."""
        if self._get_native_value("cooling"):
            return 7.0
        return 22.0

    @property
    def target_temperature(self) -> float:
        """Return target supply temperature."""
        value = self._get_native_value("target_supply_temperature")
        return round(float(value), 2)

    @property
    def current_temperature(self) -> float:
        """Return current temperature."""
        # if self._get_native_value("target_room_temperatur"):
        #    return self._get_native_value("room_temperature")

        return self._get_native_value("supply_temperature")

    @property
    def hvac_mode(self):
        """Return hvac target hvac state."""
        if self._get_native_value("state") in [0]:
            return HVACMode.OFF

        # value = self._get_native_value("cooling")
        # if value:
        #    return HVACMode.COOL

        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        """Return hvac action."""
        state = self._get_native_value("state")

        if state in [
            0,
            6,
            7,
            9,
            10,
            11,
            27,
            28,
            30,
            200,
            202,
            212,
            214,
            215,
            227,
            228,
            211,
        ]:
            return HVACAction.OFF
        if state in [31]:
            return HVACAction.IDLE
        # if state in [23, 24]:
        #     return HVACAction.COOLING
        return HVACAction.HEATING

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        modes = []
        modes.append(HVACMode.OFF)
        # modes.append(HVACMode.COOL)
        modes.append(HVACMode.HEAT)
        return modes

    @property
    def preset_mode(self) -> str:
        """Return preset mode."""
        mode = self._get_native_value("mode")
        return SOLARFOCUS_MODE_TO_PRESET.get(mode)

    @property
    def preset_modes(self) -> list[str]:
        """Return available preset modes."""
        presets = []
        presets.append(PRESET_COMFORT)
        presets.append(PRESET_ECO)
        presets.append(PRESET_AUTO)
        presets.append(PRESET_OFF)
        return presets

    # @property
    # def current_humidity(self) -> int:
    #    return self._get_native_value("humidity")

    @property
    def temperature_unit(self) -> str:
        """Return temperature unit."""
        return UnitOfTemperature.CELSIUS

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        _LOGGER.info("Set HVAC Mode: %s", hvac_mode)
        if hvac_mode == HVACMode.OFF:
            self._set_native_value("mode", "3")

        # if hvac_mode == HVACMode.COOL:
        #    if self._get_native_value("state") in [0]:
        #        self._set_native_value("mode", "0")
        #    self._set_native_value("cooling", "1")

        if hvac_mode == HVACMode.HEAT:
            if self._get_native_value("state") in [0]:
                self._set_native_value("mode", "0")
            self._set_native_value("cooling", "0")

    async def async_set_preset_mode(self, preset_mode):
        """Set new target preset mode."""
        mode = PRESET_TO_SOLARFOCUS_MODE.get(preset_mode)
        _LOGGER.info("Set Preset Mode: %s (mapped mode: %s)", preset_mode, mode)
        self._set_native_value("mode", mode)

    # async def async_set_temperature(self, **kwargs):
    #     """Set new target temperature."""
    #     if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
    #         _LOGGER.info("Set Temperature: %s", temp)
    #         self._set_native_value("target_supply_temperature", temp)


CLIMATE_TYPES = [
    SolarfocusClimateEntityDescription(
        key="thermostat",
    )
]
