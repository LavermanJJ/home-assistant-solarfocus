"""Numbers for Solarfocus integration."""

from dataclasses import dataclass
import logging
from typing import cast, override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    BOILER_COMPONENT,
    BOILER_COMPONENT_PREFIX,
    CONF_BOILER,
    CONF_HEATING_CIRCUIT,
    CONF_PHOTOVOLTAIC,
    HEATING_CIRCUIT_COMPONENT,
    HEATING_CIRCUIT_COMPONENT_PREFIX,
    PHOTOVOLTAIC_COMPONENT,
    PHOTOVOLTAIC_COMPONENT_PREFIX,
)
from .coordinator import SolarfocusConfigEntry, SolarfocusDataUpdateCoordinator
from .entity import (
    SolarfocusControllerEntity,
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
    # The controller has an entity of its own, which is not a number of a
    # component, so the list is of what they have in common.
    entities: list[SolarfocusEntity] = []

    for i in range(config_entry.options[CONF_HEATING_CIRCUIT]):
        for description in HEATING_CIRCUIT_NUMBER_TYPES:
            _description = create_description(
                HEATING_CIRCUIT_COMPONENT,
                HEATING_CIRCUIT_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusNumberEntity(coordinator, _description)
            entities.append(entity)

    for i in range(config_entry.options[CONF_BOILER]):
        for description in BOILER_NUMBER_TYPES:
            _description = create_description(
                BOILER_COMPONENT,
                BOILER_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusNumberEntity(coordinator, _description)
            entities.append(entity)

    if config_entry.options[CONF_PHOTOVOLTAIC]:
        for description in PHOTOVOLTAIC_NUMBER_TYPES:
            _description = create_description(
                PHOTOVOLTAIC_COMPONENT,
                PHOTOVOLTAIC_COMPONENT_PREFIX,
                "",
                description,
            )

            entity = SolarfocusNumberEntity(coordinator, _description)
            entities.append(entity)

    # The controller is a device of its own, and the number the installer menu
    # shows is on it: it is typed in rather than read, so it exists whatever the
    # entry has configured.
    entities.append(
        SolarfocusDisplayedNumberEntity(coordinator, DISPLAYED_NUMBER_TYPE)
    )

    async_add_entities(supported_entities(config_entry, entities))


@dataclass(frozen=True, kw_only=True)
class SolarfocusNumberEntityDescription(
    SolarfocusEntityDescription, NumberEntityDescription
):
    """Description of a Solarfocus number entity."""


class SolarfocusNumberEntity(SolarfocusEntity, NumberEntity):
    """Representation of a Solarfocus number entity."""

    entity_description: SolarfocusNumberEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolarfocusDataUpdateCoordinator,
        description: SolarfocusNumberEntityDescription,
    ) -> None:
        """Initialize the Solarfocus number entity."""
        super().__init__(coordinator, description)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        number = self.entity_description.item
        await self._async_set_native_value(number, value)

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current state."""
        number = self.entity_description.item
        return cast(float | None, self._get_native_value(number))


class SolarfocusDisplayedNumberEntity(SolarfocusControllerEntity, RestoreNumber):
    """The number the installer menu of the controller shows.

    The only writable entity here that writes nothing: the value goes to the
    sensor that multiplies it, not to a register, because the display is asking
    the user for it rather than answering.
    """

    entity_description: SolarfocusNumberEntityDescription

    @property
    @override
    def native_value(self) -> float | None:
        """Return the number last entered, or None while there is none."""
        return self.coordinator.displayed_number.value

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Take the number that is on the display."""
        self.coordinator.displayed_number.set(value)
        self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Take back the number that was entered before the restart.

        The display keeps showing the same number until the installer menu is
        left, so a restart in the middle of that is not a reason to type it
        again. Writing it back to the shared value is what makes the sensor
        report it too.
        """
        await super().async_added_to_hass()

        if (restored := await self.async_get_last_number_data()) is not None:
            self.coordinator.displayed_number.set(restored.native_value)


# What the display shows, entered by hand. No register behind it, so it names no
# component and carries no `item`.
DISPLAYED_NUMBER_TYPE = SolarfocusNumberEntityDescription(
    key="installer_code_input",
    translation_key="installer_code_input",
    object_id_name="installer code input",
    # Configuration rather than diagnostic: this is the one entity of the two
    # that is written to, and Home Assistant reads diagnostic as something a
    # device reports rather than something anyone changes.
    entity_category=EntityCategory.CONFIG,
    # Off unless it is asked for, like the code it feeds: entering it is a thing
    # an installer does once.
    entity_registry_enabled_default=False,
    native_min_value=0,
    # The installer menu shows up to four digits, so 9999 is the highest there
    # is to type - and a wider range would only let a typo through.
    native_max_value=9999,
    native_step=1,
    # A box rather than a slider: the number is read off the display and typed
    # in, not searched for by dragging.
    mode=NumberMode.BOX,
)


HEATING_CIRCUIT_NUMBER_TYPES = [
    SolarfocusNumberEntityDescription(
        key="target_supply_temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=0.0,
        native_max_value=80.0,
        native_step=0.5,
    ),
    SolarfocusNumberEntityDescription(
        key="target_room_temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=0.0,
        native_max_value=45.0,
        native_step=0.5,
    ),
    SolarfocusNumberEntityDescription(
        key="indoor_temperature_external",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=0.0,
        native_max_value=45.0,
        native_step=0.5,
    ),
    SolarfocusNumberEntityDescription(
        key="indoor_humidity_external",
        device_class=NumberDeviceClass.HUMIDITY,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0.0,
        native_max_value=100.0,
        native_step=1.0,
    ),
]

BOILER_NUMBER_TYPES = [
    SolarfocusNumberEntityDescription(
        key="target_temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=20.0,
        native_max_value=80.0,
        native_step=1,
    ),
]

PHOTOVOLTAIC_NUMBER_TYPES = [
    SolarfocusNumberEntityDescription(
        key="smart_meter",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=-32768,
        native_max_value=32767,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    SolarfocusNumberEntityDescription(
        key="photovoltaic",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=0,
        native_max_value=32767,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    SolarfocusNumberEntityDescription(
        key="grid_im_export",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=-32768,
        native_max_value=32767,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    SolarfocusNumberEntityDescription(
        key="hems_target_electrical_power",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=0,
        native_max_value=32767,
        native_step=1,
        mode=NumberMode.BOX,
    ),
]
