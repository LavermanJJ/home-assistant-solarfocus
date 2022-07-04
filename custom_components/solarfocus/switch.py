import logging
from typing import cast


from homeassistant.config_entries import ConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_HEATING_CIRCUIT, DOMAIN
from .entity import SolarfocusEntity

ON = 1
OFF = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Solarfocus config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    if config_entry.data[CONF_HEATING_CIRCUIT]:
        for description in HEATING_SWITCH_TYPES:
            entity = SolarfocusSwitchEntity(coordinator, description)
            entities.append(entity)

    async_add_entities(entities)


class SolarfocusSwitchEntity(SolarfocusEntity, SwitchEntity):
    """Representation of a Solarfocus switch entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the Solarfocus switch entity."""
        super().__init__(coordinator, description)

        title = self.coordinator._entry.title
        key = self.entity_description.key
        name = self.entity_description.name

        self.entity_id = f"switch.{title}_{key}"
        self._attr_name = f"{title} {name}"

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        _name = self.entity_description.key
        _LOGGER.info("async_turn_on - name: %s", _name)
        _updater = getattr(self.coordinator, "update_" + _name)
        await _updater(ON)
        self.async_write_ha_state()
        self._attr_is_on = True

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        _name = self.entity_description.key
        _LOGGER.info("async_turn_off - name: %s", _name)
        _updater = getattr(self.coordinator, "update_" + _name)
        await _updater(OFF)
        self.async_write_ha_state()
        self._attr_is_on = False

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        _name = self.entity_description.key
        _LOGGER.info("async_toggle - name: %s", _name)
        _updater = getattr(self.coordinator, "update_" + _name)
        await _updater(int(not self._attr_is_on))
        self.async_write_ha_state()
        self._attr_is_on = True

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._attr_is_on

    @property
    def state(self):
        """Return the current state."""
        sensor = self.entity_description.key
        value = getattr(self.coordinator.api, sensor)
        self._attr_is_on = cast(bool, int(value))
        return cast(bool, int(value))

    # async def async_set_value(self, value: float) -> None:
    #    """Update the current value."""
    #    self._attr_value = value
    #    _name = self.entity_description.key
    #    _updater = getattr(self.coordinator, "update_" + _name)


#
#    _LOGGER.info("async_set_value - name: %s, value: %f", _name, value)
#
#    await _updater(value)
#    self.async_write_ha_state()


HEATING_SWITCH_TYPES = [
    SwitchEntityDescription(
        key="hc1_cooling",
        name="Heating Circuit Cooling",
        icon="mdi:sun-snowflake-variant",
        device_class=SwitchDeviceClass.SWITCH,
    ),
]

BOILER_SWITCH_TYPES = [
    SwitchEntityDescription(
        key="bo1_single_charge",
        name="Boiler Single Charge",
        icon="mdi:sun-snowflake-variant",
    ),
]
