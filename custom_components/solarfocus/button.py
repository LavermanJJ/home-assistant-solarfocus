"""Buttons for Solarfocus integration"""

import logging
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription


from homeassistant.config_entries import ConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_BOILER, DOMAIN
from .entity import SolarfocusEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Solarfocus config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    if config_entry.data[CONF_BOILER]:
        for description in BOILER_BUTTON_TYPES:
            entity = SolarfocusButtonEntity(coordinator, description)
            entities.append(entity)

    async_add_entities(entities)


class SolarfocusButtonEntity(SolarfocusEntity, ButtonEntity):
    """Representation of a Solarfocus button entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the Solarfocus number entity."""
        super().__init__(coordinator, description)

        title = self.coordinator._entry.title
        key = self.entity_description.key
        name = self.entity_description.name

        self.entity_id = f"number.{title}_{key}"
        self._attr_name = f"{title} {name}"

    async def async_press(self) -> None:
        """Update the current value."""

        _name = self.entity_description.key
        _updater = getattr(self.coordinator, "trigger_" + _name)
        _LOGGER.debug("async_press: %s", _name)

        await _updater()


BOILER_BUTTON_TYPES = [
    ButtonEntityDescription(
        key="bo1_enable_single_charge",
        name="Boiler Trigger Single Charge",
        icon="mdi:water-boiler",
    ),
    ButtonEntityDescription(
        key="bo1_enable_circulation",
        name="Boiler Trigger Circulation",
        icon="mdi:reload",
    ),
]
