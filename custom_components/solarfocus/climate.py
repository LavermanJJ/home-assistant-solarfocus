"""Climate for Solarfocus integration"""

import logging
from config.custom_components.solarfocus import coordinator
from homeassistant.components.climate.const import (
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_SLEEP,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)


from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityDescription,
)

from .const import CONF_HEATING_CIRCUIT, DOMAIN
from .entity import SolarfocusEntity

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
    PRESET_COMFORT: 0,
    PRESET_ECO: 1,
    PRESET_AUTO: 2,
    PRESET_OFF: 3,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Solarfocus config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    if config_entry.data[CONF_HEATING_CIRCUIT]:
        for description in CLIMATE_TYPES:
            entity = SolarfocusClimateEntity(coordinator, description)
            entities.append(entity)

    async_add_entities(entities)


class SolarfocusClimateEntity(SolarfocusEntity, ClimateEntity):
    """Representation of a Solarfocus number entity."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the Solarfocus select entity."""
        super().__init__(coordinator, description)

        name = self.entity_description.name
        self.entity_id = f"climate.heating_circuit"
        self._attr_name = f"{name}"

    @property
    def max_temp(self) -> float:
        if self.coordinator.api.hc1_cooling:
            return 35
        return 45

    @property
    def min_temp(self) -> float:
        if self.coordinator.api.hc1_cooling:
            return 7
        return 22

    @property
    def target_temperature(self) -> float:
        value = self.coordinator.api.hc1_target_temperatur
        return round(float(value), 2)

    @property
    def current_temperature(self) -> float:
        """return current temperature"""
        value = self.coordinator.api.hc1_supply_temp
        return round(float(value), 2)

    @property
    def hvac_mode(self):
        """Return hvac target hvac state."""
        value = self.coordinator.api.hc1_cooling

        if value:
            return HVACMode.COOL

        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:

        state = self.coordinator.api.hc1_state

        if state in [0]:
            return HVACAction.OFF
        if state in [6, 7, 9, 10, 27, 28, 30]:
            return HVACAction.IDLE
        if state in [23, 24, 31]:
            return HVACAction.COOLING
        return HVACAction.HEATING

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        modes = []
        modes.append(HVACMode.COOL)
        modes.append(HVACMode.HEAT)
        return modes

    @property
    def preset_mode(self) -> str:
        mode = self.coordinator.api.hc1_mode_holding
        return SOLARFOCUS_MODE_TO_PRESET.get(mode)

    @property
    def preset_modes(self) -> list[str]:
        presets = []
        presets.append(PRESET_COMFORT)
        presets.append(PRESET_ECO)
        presets.append(PRESET_AUTO)
        presets.append(PRESET_AWAY)
        return presets

    @property
    def current_humidity(self) -> int:
        return self.coordinator.api.hc1_humidity

    @property
    def temperature_unit(self) -> str:
        return TEMP_CELSIUS

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        _LOGGER.info("Set HVAC Mode: %s", hvac_mode)
        if hvac_mode == HVACMode.COOL:
            await self.coordinator.update_hc1_cooling("1")
        if hvac_mode == HVACMode.HEAT:
            await self.coordinator.update_hc1_cooling("0")

    async def async_set_preset_mode(self, preset_mode):
        """Set new target preset mode."""
        mode = PRESET_TO_SOLARFOCUS_MODE.get(preset_mode)
        _LOGGER.info("Set Preset Mode: %s (mapped mode: %s)", preset_mode, mode)
        await self.coordinator.update_hc1_mode_holding(mode)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            _LOGGER.info("Set Temperature: %s", temp)
            await self.coordinator.update_hc1_target_temperatur(round(float(temp), 2))


CLIMATE_TYPES = [
    ClimateEntityDescription(
        key="heating",
        name="Heating Circuit",
        icon="mdi:thermostat",
    )
]
