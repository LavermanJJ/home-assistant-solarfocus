"""Entity for Solarfocus integration"""


import copy
from dataclasses import dataclass
import logging

from homeassistant.helpers.entity import Entity, EntityDescription

from .coordinator import SolarfocusDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class SolarfocusEntityDescription(EntityDescription):
    """Description of a Solarfocus entity"""

    item: str = None
    component: str = None
    component_prefix: str = None
    component_idx: str = None


def create_description(
    name_prefix: str,
    component: str,
    prefix: str,
    idx: str,
    description: SolarfocusEntityDescription,
) -> SolarfocusEntityDescription:
    """Create Description"""
    _description = copy.copy(description)

    _description.item = description.key
    _description.component_idx = idx
    _description.component = component
    _description.component_prefix = prefix

    _name = name_prefix + " " + idx + " " + description.key.replace("_", " ")
    _description.name = " ".join(
        _name.split()
    )  # remove double space in case of missing idx

    _description.key = "".join(
        filter(
            None,
            (
                prefix,
                idx,
                "_",
                _description.item,
            ),
        )
    )

    return _description


class SolarfocusEntity(Entity):
    """Defines a base Solarfocus entity."""

    _attr_should_poll = True
    has_entity_name = True

    def __init__(
        self,
        coordinator: SolarfocusDataUpdateCoordinator,
        description: SolarfocusEntityDescription,
    ) -> None:
        """Initialize the Atag entity."""
        self.coordinator = coordinator
        self._name = coordinator._entry.title
        self._state = None
        self.entity_description = description

    @property
    def device_info(self) -> dict:
        """Return info for device registry."""
        device = self._name
        model = self.coordinator.api.system
        return {
            "identifiers": {(DOMAIN, device)},
            "name": "Solarfocus",
            "model": {model},
            "sw_version": "21.040",
            "manufacturer": "Solarfocus",
        }

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        _LOGGER.debug("Unique_id - %s", self.entity_description.key)
        return f"{self._name}_{self.entity_description.key}"

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update entity."""
        await self.coordinator.async_request_refresh()
