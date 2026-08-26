"""Selects for Solarfocus integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    BOILER_COMPONENT,
    BOILER_COMPONENT_PREFIX,
    CONF_BOILER,
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
    HEAT_PUMP_COMPONENT,
    HEAT_PUMP_COMPONENT_PREFIX,
    HEATING_CIRCUIT_COMPONENT,
    HEATING_CIRCUIT_COMPONENT_PREFIX,
)
from .coordinator import SolarfocusConfigEntry, SolarfocusDataUpdateCoordinator
from .entity import (
    SolarfocusEntity,
    SolarfocusEntityDescription,
    create_description,
    supported_entities,
)

_LOGGER = logging.getLogger(__name__)

# Every write is a read-modify-commit sequence on a component, so two of them
# running at once can interleave on the same registers. This limits Home
# Assistant to one in-flight service call per platform; it does not cover the
# reads the coordinator does, which is why writes re-read their component.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SolarfocusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Solarfocus config entry."""
    coordinator = config_entry.runtime_data
    entities = []

    for i in range(config_entry.options[CONF_HEATING_CIRCUIT]):
        for description in HEATING_CIRCUIT_SELECT_TYPES:
            _description = create_description(
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
                HEAT_PUMP_COMPONENT,
                HEAT_PUMP_COMPONENT_PREFIX,
                "",
                description,
            )

            entity = SolarfocusSelectEntity(coordinator, _description)
            entities.append(entity)

    async_add_entities(supported_entities(config_entry, entities))


@dataclass(frozen=True, kw_only=True)
class SolarfocusSelectEntityDescription(
    SolarfocusEntityDescription, SelectEntityDescription
):
    """Description of a Solarfocus select entity."""

    current_option: str | None = None
    # kept for compatibility reasons. Removing it would make 2022.11 the min
    # required version.
    solarfocus_options: list[str]


class SolarfocusSelectEntity(SolarfocusEntity, SelectEntity):
    """Representation of a Solarfocus select entity."""

    entity_description: SolarfocusSelectEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolarfocusDataUpdateCoordinator,
        description: SolarfocusSelectEntityDescription,
    ) -> None:
        """Initialize the Solarfocus select entity."""
        super().__init__(coordinator, description)
        self._attr_options = description.solarfocus_options

    @override
    async def async_select_option(self, option: str) -> None:
        """Update the current selected option.

        The options are the strings of the numbers the controller works in, so
        the number is what goes to the register: the library encodes an int or
        a member of the register's own enumeration, and refuses a string.
        """
        self._attr_current_option = option
        select = self.entity_description.item
        await self._async_set_native_value(select, int(option))

    @property
    @override
    def current_option(self) -> str | None:
        """Return current option, or None while the register has no reading.

        A closed set of values decodes to a member of the library's enumeration,
        which is an `IntEnum` and so prints as its number - which is what the
        options are. `int()` first regardless, so a register that decodes to
        something else does not report an option that is not on the list.
        """
        value = self._get_native_value(self.entity_description.item)

        return None if value is None else str(int(value))


HEATPUMP_SELECT_TYPES = [
    SolarfocusSelectEntityDescription(
        key="smart_grid",
        current_option="2",
        solarfocus_options=[
            "0",
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
        entity_registry_enabled_default=False,
        current_option="0",
        solarfocus_options=[
            "0",
            "1",
        ],
    ),
    SolarfocusSelectEntityDescription(
        key="mode",
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
    SolarfocusSelectEntityDescription(
        key="heating_mode",
        entity_category=EntityCategory.CONFIG,
        current_option="0",
        solarfocus_options=[
            "0",
            "1",
            "2",
        ],
    ),
]

BOILER_SELECT_TYPES = [
    SolarfocusSelectEntityDescription(
        key="holding_mode",
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
