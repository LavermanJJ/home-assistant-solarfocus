"""Entity for Solarfocus integration."""


import copy
from dataclasses import dataclass
import logging

from packaging import version
from pysolarfocus import Systems

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_VERSION
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import CONF_SOLARFOCUS_SYSTEM, DOMAIN
from .coordinator import SolarfocusDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class SolarfocusEntityDescription(EntityDescription):
    """Description of a Solarfocus entity."""

    item: str | None = None
    component: str | None = None
    component_prefix: str | None = None
    component_idx: str | None = None
    min_required_version: str = "21.140"
    unsupported_systems: list[Systems] | None = None


def create_description(
    name_prefix: str,
    component: str,
    prefix: str,
    idx: str,
    description: SolarfocusEntityDescription,
) -> SolarfocusEntityDescription:
    """Create Description."""
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

    _description.translation_key = "".join(
        filter(
            None,
            (
                prefix,
                "_",
                _description.item,
            ),
        )
    )

    return _description


def filterVersionAndSystem(config_entry: ConfigEntry, entities):
    """Filter entities not compatible to version or system."""
    api_version = version.parse(config_entry.options[CONF_API_VERSION])

    filtered_entities = filter(
        lambda entity: version.parse(entity.entity_description.min_required_version)
        <= api_version,
        entities,
    )

    current_system = config_entry.data[CONF_SOLARFOCUS_SYSTEM]

    for entity in filtered_entities:
        unsupported_systems = entity.entity_description.unsupported_systems
        if unsupported_systems is None:
            yield entity
        elif current_system not in unsupported_systems:
            yield entity

    return filtered_entities


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
        model = self.coordinator.api.system.value
        api_version = self.coordinator.api.api_version.value
        return {
            "identifiers": {(DOMAIN, device)},
            "name": "Solarfocus",
            "model": {model},
            "sw_version": {api_version},
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

    @property
    def translation_key(self):
        """Return a translation key to use for this entity."""
        _LOGGER.debug("Translation_key - %s", self.entity_description.translation_key)
        return f"{self.entity_description.translation_key}"

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update entity."""
        await self.coordinator.async_request_refresh()

    def _set_native_value(self, item, value):
        component: None
        idx = -1

        if self.entity_description.component_idx:
            idx = int(self.entity_description.component_idx) - 1
            component = getattr(
                self.coordinator.api, self.entity_description.component
            )[idx]
        else:
            component = getattr(self.coordinator.api, self.entity_description.component)
        _LOGGER.debug(
            "_set_native_value - idx: %s, component: %s, entity: %s",
            idx,
            self.entity_description.component,
            item,
        )
        entity = getattr(component, item)
        entity.set_unscaled_value(value)
        entity.commit()
        component.update()

        self.async_write_ha_state()

    def _get_native_value(self, item):
        component: None
        idx = -1

        if self.entity_description.component_idx:
            idx = int(self.entity_description.component_idx) - 1
            component = getattr(
                self.coordinator.api, self.entity_description.component
            )[idx]
        else:
            component = getattr(self.coordinator.api, self.entity_description.component)

        native_value = getattr(component, item).scaled_value

        _LOGGER.debug(
            "_get_native_value - idx: %s, component: %s, entity: %s, value: %s",
            idx,
            self.entity_description.component,
            item,
            native_value,
        )

        return native_value
