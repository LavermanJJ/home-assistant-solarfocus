"""Numbers for Solarfocus integration."""

from dataclasses import dataclass
import logging

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_HEATPUMP,
    DATA_COORDINATOR,
    DOMAIN,
    HEAT_PUMP_COMPONENT,
    HEAT_PUMP_COMPONENT_PREFIX,
    HEAT_PUMP_PREFIX,
)
from .entity import (
    SolarfocusEntity,
    SolarfocusEntityDescription,
    create_description,
    filterVersionAndSystem,
)

_LOGGER = logging.getLogger(__name__)

ON = 1
OFF = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Solarfocus config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    entities = []

    if config_entry.options[CONF_HEATPUMP]:
        for description in HEATPUMP_SWITCH_TYPES:
            _description = create_description(
                HEAT_PUMP_PREFIX,
                HEAT_PUMP_COMPONENT,
                HEAT_PUMP_COMPONENT_PREFIX,
                "",
                description,
            )

            entity = SolarfocusSwitchEntity(coordinator, _description)
            entities.append(entity)

    async_add_entities(filterVersionAndSystem(config_entry, entities))


@dataclass
class SolarfocusSwitchEntityDescription(
    SolarfocusEntityDescription, SwitchEntityDescription
):
    """Description of a Solarfocus switch entity."""


class SolarfocusSwitchEntity(SolarfocusEntity, SwitchEntity):
    """Representation of a Solarfocus switch entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: SolarfocusSwitchEntityDescription,
    ) -> None:
        """Initialize the Solarfocus number entity."""
        super().__init__(coordinator, description)

    @property
    def is_on(self):
        """Return the state of the switch."""
        switch = self.entity_description.item
        return self._get_native_value(switch)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        switch = self.entity_description.item
        return self._set_native_value(switch, ON)

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        switch = self.entity_description.item
        return self._set_native_value(switch, OFF)


HEATPUMP_SWITCH_TYPES = [
    SolarfocusSwitchEntityDescription(
        key="evu_lock", icon="mdi:lock", device_class=SwitchDeviceClass.SWITCH
    ),
]
