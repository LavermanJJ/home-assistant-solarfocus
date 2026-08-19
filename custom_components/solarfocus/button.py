"""Buttons for Solarfocus integration."""

from dataclasses import dataclass
import logging
from typing import override

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BOILER_COMPONENT, BOILER_COMPONENT_PREFIX, CONF_BOILER
from .coordinator import SolarfocusConfigEntry, SolarfocusDataUpdateCoordinator
from .entity import (
    SolarfocusEntity,
    SolarfocusEntityDescription,
    create_description,
    filterVersionAndSystem,
)

_LOGGER = logging.getLogger(__name__)

# Every write is a read-modify-commit sequence on a component, so two of them
# running at once can interleave on the same registers. This limits Home
# Assistant to one in-flight service call per platform; it does not cover the
# reads the coordinator does, which is why writes re-read their component.
PARALLEL_UPDATES = 1

# The value that triggers the action. The register is a number, and it is read
# back as one by the sensor of the same name, so write it as one: a bool would
# survive in the component until the next successful read.
PRESSED = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SolarfocusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Solarfocus config entry."""
    coordinator = config_entry.runtime_data
    entities = []

    for i in range(config_entry.options[CONF_BOILER]):
        for description in BOILER_BUTTON_TYPES:
            _description = create_description(
                BOILER_COMPONENT,
                BOILER_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusButtonEntity(coordinator, _description)
            entities.append(entity)

    async_add_entities(filterVersionAndSystem(config_entry, entities))


@dataclass(frozen=True, kw_only=True)
class SolarfocusButtonEntityDescription(
    SolarfocusEntityDescription, ButtonEntityDescription
):
    """Description of a Solarfocus number entity."""


class SolarfocusButtonEntity(SolarfocusEntity, ButtonEntity):
    """Representation of a Solarfocus button entity."""

    entity_description: SolarfocusButtonEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolarfocusDataUpdateCoordinator,
        description: SolarfocusButtonEntityDescription,
    ) -> None:
        """Initialize the Solarfocus number entity."""
        super().__init__(coordinator, description)

    @override
    async def async_press(self) -> None:
        """Update the current value."""
        button = self.entity_description.item
        return self._set_native_value(button, PRESSED)


BOILER_BUTTON_TYPES = [
    SolarfocusButtonEntityDescription(
        key="single_charge",
    ),
    SolarfocusButtonEntityDescription(
        key="circulation",
    ),
]
