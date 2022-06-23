"""Demo platform that offers a fake select entity."""
from __future__ import annotations
from dataclasses import dataclass
import logging


from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
    DOMAIN,
)
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

    if config_entry.data[CONF_HEATING_CIRCUIT]:
        for description in HEATING_CIRCUIT_SELECT_TYPES:
            entity = SolarfocusSelectEntity(coordinator, description)
            entities.append(entity)

    if config_entry.data[CONF_HEATPUMP]:
        for description in HEATPUMP_SELECT_TYPES:
            entity = SolarfocusSelectEntity(coordinator, description)
            entities.append(entity)

    async_add_entities(entities)


@dataclass
class SolarfocusSelectEntityDescription(EntityDescription):
    """Description of a Solarfocus select entity"""

    current_option: str | None = None
    options: list[str] = None


class SolarfocusSelectEntity(SolarfocusEntity, SelectEntity):
    """Representation of a Solarfocus select entity."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: SolarfocusSelectEntityDescription,
    ) -> None:
        """Initialize the Solarfocus select entity."""
        super().__init__(coordinator, description)

        title = self.coordinator._entry.title
        key = self.entity_description.key
        name = self.entity_description.name

        self.entity_id = f"select.{title}_{key}"
        self._attr_name = f"{title} {name}"
        self._attr_current_option = description.current_option
        self._attr_options = description.options

    async def async_select_option(self, option: str) -> None:
        """Update the current selected option."""
        self._attr_current_option = option
        _name = self.entity_description.key
        _updater = getattr(self.coordinator, "update_" + _name)

        _LOGGER.debug("async_select_option - name: %s, option: %s", _name, option)

        await _updater(option)
        self.async_write_ha_state()


HEATPUMP_SELECT_TYPES = [
    SolarfocusSelectEntityDescription(
        key="hp_smart_grid",
        name="Heatpump SmartGrid",
        icon="mdi:leaf",
        device_class="solarfocus__hpsmartgrid",
        current_option="2",
        options=[
            "2",
            "4",
        ],
    ),
]

HEATING_CIRCUIT_SELECT_TYPES = [
    SolarfocusSelectEntityDescription(
        key="hc1_cooling",
        name="Heating Circuit Cooling",
        icon="mdi:snowflake",
        device_class="solarfocus__hccooling",
        current_option="0",
        options=[
            "0",
            "1",
        ],
    ),
    SolarfocusSelectEntityDescription(
        key="hc1_mode_holding",
        name="Heating Circuit Mode",
        icon="mdi:radiator",
        device_class="solarfocus__hcmode",
        current_option="3",
        options=[
            "0",
            "1",
            "2",
            "3",
        ],
    ),
]
