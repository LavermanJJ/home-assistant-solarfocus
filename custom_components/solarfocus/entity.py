"""Entity for Solarfocus integration."""


import copy
from dataclasses import dataclass
import logging

from packaging import version
from pysolarfocus import Systems

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_VERSION
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import COMPONENT_DEVICES, CONF_SOLARFOCUS_SYSTEM, DOMAIN, MANUFACTURER
from .coordinator import SolarfocusDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class SolarfocusEntityDescription(EntityDescription):
    """Description of a Solarfocus entity."""

    item: str | None = None
    component: str | None = None
    component_prefix: str | None = None
    component_idx: str | None = None
    object_id_name: str | None = None
    # The index as a device name shows it, " 1" or blank - see `create_description`
    device_idx: str = ""
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

    # The name the user reads is not built here any more. `has_entity_name` makes
    # it the name of the entity, and a name built from the key is English
    # whatever language Home Assistant is in, so it comes from the translation of
    # `translation_key` instead.
    #
    # The index is not in the entity name either. It belongs to the device the
    # entity is on - `Supply temperature` on `Heating circuit 2` - so it is
    # carried here for the device name to put back. The space belongs to it: a
    # single solar circuit keeps the unnumbered name it has always had, and
    # `format` does not tidy up after an empty placeholder.
    _description.device_idx = f" {idx}" if idx else ""

    # What the entity id is built from. Home Assistant composes it out of the
    # name of the device and this, so the component and the index are not in it
    # either - the device supplies both. The words of the key rather than the
    # translated name, so this half of the id stays English in every language.
    _description.object_id_name = description.key.replace("_", " ")

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
    api_version = version.parse(config_entry.data[CONF_API_VERSION])

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
        self._entry_id = coordinator._entry.entry_id
        self._state = None
        self.entity_description = description


    @property
    def device_info(self) -> DeviceInfo:
        """Return the component this entity belongs to, as its own device.

        Every heating circuit, buffer, boiler, fresh water module and solar
        circuit is a device, as are the heat pump, the photovoltaic and the
        biomass boiler, and all of them hang off the controller. What that buys
        is an area per component, a page per component instead of one page
        holding every entity of a heating system, and a name the index has been
        lifted out of - `Top temperature` on `Buffer 1`, rather than
        `Buffer 1 Top temperature` on `Solarfocus`.

        The identifier of a component is always indexed, `..._so1` even where
        the name says only `Solar`, so raising the count of a component renames
        its first device rather than orphaning it.

        The entity `unique_id` is still built from the title of the entry. That
        is the other half of the rename problem and a migration of its own, see
        #212.
        """
        description = self.entity_description
        translation_key, model = COMPONENT_DEVICES[description.component_prefix]

        return DeviceInfo(
            identifiers={
                (DOMAIN, f"{self._entry_id}_{description.component_prefix}"
                 f"{description.component_idx or ''}")
            },
            translation_key=translation_key,
            # Blank for the components that exist once, and for the single
            # solar circuit that keeps the unnumbered name it had before there
            # could be four of them.
            translation_placeholders={"idx": description.device_idx},
            model=model,
            manufacturer=MANUFACTURER,
            via_device_id=self.coordinator.hub_device_id,
        )

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

    @property
    def suggested_object_id(self) -> str | None:
        """Return the entity half of the entity id.

        Home Assistant composes an id out of the name of the device and this,
        honouring whatever the installation has configured an id to be made of.
        The device half is translated like any device name; this half is the
        words of the key, so the part that names the reading stays English in
        every language - `sensor.heizkreis_1_supply_temperature`, never
        `..._vorlauftemperatur`.
        """
        return self.entity_description.object_id_name

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

        raw_value = entity.value
        if isinstance(raw_value, (int, float)) and raw_value < 0:
            # Modbus transmits registers as unsigned words, negative values have
            # to be written as two's complement (16 bit per register). The signed
            # value is restored afterwards, reading the register turns it back
            # into a signed one.
            entity.value = raw_value + (1 << (16 * entity.count))
            entity.commit()
            entity.value = raw_value
        else:
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
