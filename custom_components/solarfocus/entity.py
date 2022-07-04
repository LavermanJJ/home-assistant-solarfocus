"""Entity for Solarfocus integration"""


import logging
from homeassistant.const import Platform
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DOMAIN, SENSORS_DISABLED_BY_DEFAULT
from .coordinator import SolarfocusDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class SolarfocusEntity(Entity):
    """Defines a base Solarfocus entity."""

    _attr_should_poll = True

    def __init__(
        self,
        coordinator: SolarfocusDataUpdateCoordinator,
        description: EntityDescription,
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
        return {
            "identifiers": {(DOMAIN, device)},
            "name": "Solarfocus eco manager-touch",
            "model": "eco manager-touch",
            "sw_version": "21.040",
            "manufacturer": "Solarfocus",
        }

    @property
    def state(self):
        """Return the current state."""
        sensor = self.entity_description.key
        value = getattr(self.coordinator.api, sensor)
        if isinstance(value, float):
            try:
                rounded_value = round(float(value), 2)
                return rounded_value
            except ValueError:
                return value
        return value

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        sensor = self.entity_description.key
        return f"{self._name}_{sensor}"

    @property
    def entity_registry_enabled_default(self):
        """Return if this entity is enabled by default."""
        if self.platform.domain == Platform.SENSOR:
            enable = not self.entity_description.key in SENSORS_DISABLED_BY_DEFAULT
            return enable
        return True

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update entity."""
        await self.coordinator.async_request_refresh()
