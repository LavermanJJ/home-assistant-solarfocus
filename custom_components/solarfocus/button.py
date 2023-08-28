"""Buttons for Solarfocus integration."""

from dataclasses import dataclass
import logging

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
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
from .entity import (
    SolarfocusEntity,
    SolarfocusEntityDescription,
    create_description,
    filterVersionAndSystem,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Solarfocus config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    entities = []

    for i in range(config_entry.options[CONF_BOILER]):
        for description in BOILER_BUTTON_TYPES:
            _description = create_description(
                BOILER_PREFIX,
                BOILER_COMPONENT,
                BOILER_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusButtonEntity(coordinator, _description)
            entities.append(entity)

    async_add_entities(filterVersionAndSystem(config_entry, entities))


@dataclass
class SolarfocusButtonEntityDescription(
    SolarfocusEntityDescription, ButtonEntityDescription
):
    """Description of a Solarfocus number entity."""


class SolarfocusButtonEntity(SolarfocusEntity, ButtonEntity):
    """Representation of a Solarfocus button entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: SolarfocusButtonEntityDescription,
    ) -> None:
        """Initialize the Solarfocus number entity."""
        super().__init__(coordinator, description)

    async def async_press(self) -> None:
        """Update the current value."""
        button = self.entity_description.item
        return self._set_native_value(button, True)


BOILER_BUTTON_TYPES = [
    SolarfocusButtonEntityDescription(
        key="single_charge",
        icon="mdi:water-boiler",
    ),
    SolarfocusButtonEntityDescription(
        key="circulation",
        icon="mdi:reload",
    ),
]
