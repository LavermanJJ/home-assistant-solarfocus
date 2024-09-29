"""Selects for Solarfocus integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    BOILER_COMPONENT,
    BOILER_COMPONENT_PREFIX,
    BOILER_PREFIX,
    CONF_BOILER,
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
    DATA_COORDINATOR,
    DOMAIN,
    HEAT_PUMP_COMPONENT,
    HEAT_PUMP_COMPONENT_PREFIX,
    HEAT_PUMP_PREFIX,
    HEATING_CIRCUIT_COMPONENT,
    HEATING_CIRCUIT_COMPONENT_PREFIX,
    HEATING_CIRCUIT_PREFIX,
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

    for i in range(config_entry.options[CONF_HEATING_CIRCUIT]):
        for description in HEATING_CIRCUIT_SELECT_TYPES:
            _description = create_description(
                HEATING_CIRCUIT_PREFIX,
                HEATING_CIRCUIT_COMPONENT,
                HEATING_CIRCUIT_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusSelectEntity(coordinator, _description)
            entities.append(entity)

    for i in range(config_entry.options[CONF_BOILER]):
        for description in BOILER_SELECT_TYPES:
            _description = create_description(
                BOILER_PREFIX,
                BOILER_COMPONENT,
                BOILER_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusSelectEntity(coordinator, _description)
            entities.append(entity)

    if config_entry.options[CONF_HEATPUMP]:
        for description in HEATPUMP_SELECT_TYPES:
            _description = create_description(
                HEAT_PUMP_PREFIX,
                HEAT_PUMP_COMPONENT,
                HEAT_PUMP_COMPONENT_PREFIX,
                "",
                description,
            )

            entity = SolarfocusSelectEntity(coordinator, _description)
            entities.append(entity)

    async_add_entities(filterVersionAndSystem(config_entry, entities))


@dataclass
class SolarfocusSelectEntityDescription(
    SolarfocusEntityDescription, SelectEntityDescription
):
    """Description of a Solarfocus select entity."""

    current_option: str | None = None
    # kept for compatibility reasons. Removing it would make 2022.11 the min
    # required version.
    solarfocus_options: list[str] = None


class SolarfocusSelectEntity(SolarfocusEntity, SelectEntity):
    """Representation of a Solarfocus select entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: SolarfocusSelectEntityDescription,
    ) -> None:
        """Initialize the Solarfocus select entity."""
        super().__init__(coordinator, description)
        self._attr_options = description.solarfocus_options

    async def async_select_option(self, option: str) -> None:
        """Update the current selected option."""
        self._attr_current_option = option
        select = self.entity_description.item
        return self._set_native_value(select, option)

    @property
    def current_option(self) -> str:
        """Return current option."""
        select = self.entity_description.item
        return str(self._get_native_value(select))


HEATPUMP_SELECT_TYPES = [
    SolarfocusSelectEntityDescription(
        key="smart_grid",
        icon="mdi:leaf",
        current_option="2",
        solarfocus_options=[
            "1",
            "2",
            "3",
            "4",
        ],
    ),
]

HEATING_CIRCUIT_SELECT_TYPES = [
    SolarfocusSelectEntityDescription(
        key="cooling",
        icon="mdi:snowflake",
        entity_registry_enabled_default=False,
        current_option="0",
        solarfocus_options=[
            "0",
            "1",
        ],
    ),
    SolarfocusSelectEntityDescription(
        key="mode",
        icon="mdi:radiator",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        current_option="3",
        solarfocus_options=[
            "0",
            "1",
            "2",
            "3",
        ],
    ),
]

BOILER_SELECT_TYPES = [
    SolarfocusSelectEntityDescription(
        key="holding_mode",
        icon="mdi:water-boiler",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        current_option="0",
        solarfocus_options=[
            "0",
            "1",
            "2",
            "3",
            "4",
        ],
    ),
]
