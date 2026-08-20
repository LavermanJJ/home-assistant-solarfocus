"""Numbers for Solarfocus integration."""

from dataclasses import dataclass
import logging
from typing import Any, override

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_HEATPUMP, HEAT_PUMP_COMPONENT, HEAT_PUMP_COMPONENT_PREFIX
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

ON = 1
OFF = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SolarfocusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Solarfocus config entry."""
    coordinator = config_entry.runtime_data
    entities = []

    if config_entry.options[CONF_HEATPUMP]:
        for description in HEATPUMP_SWITCH_TYPES:
            _description = create_description(
                HEAT_PUMP_COMPONENT,
                HEAT_PUMP_COMPONENT_PREFIX,
                "",
                description,
            )

            entity = SolarfocusSwitchEntity(coordinator, _description)
            entities.append(entity)

    async_add_entities(filterVersionAndSystem(config_entry, entities))


@dataclass(frozen=True, kw_only=True)
class SolarfocusSwitchEntityDescription(
    SolarfocusEntityDescription, SwitchEntityDescription
):
    """Description of a Solarfocus switch entity."""


class SolarfocusSwitchEntity(SolarfocusEntity, SwitchEntity):
    """Representation of a Solarfocus switch entity."""

    entity_description: SolarfocusSwitchEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolarfocusDataUpdateCoordinator,
        description: SolarfocusSwitchEntityDescription,
    ) -> None:
        """Initialize the Solarfocus number entity."""
        super().__init__(coordinator, description)

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the switch."""
        switch = self.entity_description.item
        # The register holds 0 or 1. A register that could not be read keeps
        # whatever it last held, so there is no third answer to give here -
        # the entity goes unavailable with its component instead.
        return bool(self._get_native_value(switch))

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        switch = self.entity_description.item
        return self._set_native_value(switch, ON)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        switch = self.entity_description.item
        return self._set_native_value(switch, OFF)


HEATPUMP_SWITCH_TYPES = [
    SolarfocusSwitchEntityDescription(
        key="evu_lock", device_class=SwitchDeviceClass.SWITCH
    ),
]
