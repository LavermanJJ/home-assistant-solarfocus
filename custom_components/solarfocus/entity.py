"""Entity for Solarfocus integration."""


from collections.abc import Generator
from dataclasses import dataclass, replace
import logging
from typing import Any, override

from packaging import version
from pysolarfocus import Systems

from homeassistant.const import CONF_API_VERSION
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import COMPONENT_DEVICES, CONF_SOLARFOCUS_SYSTEM, DOMAIN, MANUFACTURER
from .coordinator import SolarfocusConfigEntry, SolarfocusDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SolarfocusEntityDescription(EntityDescription):
    """Description of a Solarfocus entity.

    Frozen, like every description in Home Assistant. A description is shared
    by every entity built from it until `create_description` binds a copy to
    one instance of a component, and something shared is something no entity
    should be able to write to.
    """

    # Blank on the descriptions the tables below declare, filled in by
    # `create_description` on every description an entity is actually built
    # from. `component_idx` stays blank for the components that exist once.
    item: str = ""
    component: str = ""
    component_prefix: str = ""
    component_idx: str = ""
    object_id_name: str = ""
    # The index as a device name shows it, " 1" or blank - see `create_description`
    device_idx: str = ""
    min_required_version: str = "21.140"
    unsupported_systems: list[Systems] | None = None


def create_description[_DescriptionT: SolarfocusEntityDescription](
    component: str,
    prefix: str,
    idx: str,
    description: _DescriptionT,
) -> _DescriptionT:
    """Return a copy of a description, bound to one instance of a component.

    The display name of the component is not needed here any more: the device
    an entity sits on carries it, and the name of the device is translated.

    Generic in the description so a platform gets its own description type back
    rather than this base one, and can read the fields it added to it.
    """
    # The name the user reads is not built here any more. `has_entity_name` makes
    # it the name of the entity, and a name built from the key is English
    # whatever language Home Assistant is in, so it comes from the translation of
    # `translation_key` instead.
    #
    # The index is not in the entity name either. It belongs to the device the
    # entity is on - `Supply temperature` on `Heating circuit 2` - so it is
    # carried in `device_idx` for the device name to put back. The space belongs
    # to it: a single solar circuit keeps the unnumbered name it has always had,
    # and `format` does not tidy up after an empty placeholder.
    #
    # `object_id_name` is what the entity id is built from. Home Assistant
    # composes it out of the name of the device and this, so the component and
    # the index are not in it either - the device supplies both. The words of the
    # key rather than the translated name, so this half of the id stays English
    # in every language.
    return replace(
        description,
        item=description.key,
        component=component,
        component_prefix=prefix,
        component_idx=idx,
        device_idx=f" {idx}" if idx else "",
        object_id_name=description.key.replace("_", " "),
        key="".join(filter(None, (prefix, idx, "_", description.key))),
        translation_key="".join(filter(None, (prefix, "_", description.key))),
    )


def every_system_but(*supported: Systems) -> list[Systems]:
    """Return every system except the ones given.

    Some registers are documented for a single system - the register document
    writes them "Kesselbetriebsart therminator" or "Speichertemperatur Oben
    octoplus". Naming the system that has the register says that far more
    plainly than listing the four that do not, and it keeps a system added to
    the enum later out of a register the document never granted it.
    """
    return [system for system in Systems if system not in supported]


def filterVersionAndSystem[_EntityT: SolarfocusEntity](
    config_entry: SolarfocusConfigEntry, entities: list[_EntityT]
) -> Generator[_EntityT]:
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


class SolarfocusEntity(Entity):
    """Defines a base Solarfocus entity."""

    _attr_should_poll = True
    has_entity_name = True

    entity_description: SolarfocusEntityDescription

    def __init__(
        self,
        coordinator: SolarfocusDataUpdateCoordinator,
        description: SolarfocusEntityDescription,
    ) -> None:
        """Initialize the Atag entity."""
        self.coordinator = coordinator
        self._name = coordinator._entry.title
        self._entry_id = coordinator._entry.entry_id
        self._state: str | None = None
        self.entity_description = description

    @property
    @override
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

        device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{self._entry_id}_{description.component_prefix}"
                 f"{description.component_idx}")
            },
            translation_key=translation_key,
            # Blank for the components that exist once, and for the single
            # solar circuit that keeps the unnumbered name it had before there
            # could be four of them.
            translation_placeholders={"idx": description.device_idx},
            model=model,
            manufacturer=MANUFACTURER,
        )

        # `async_setup_entry` registers the controller before it forwards the
        # entry to the platforms, so this is set by the time an entity is asked
        # for its device. Left out rather than passed as `None` if it is not:
        # an explicit `None` reads as "no via device" and would unlink a
        # component from the controller it hangs off.
        if (hub_device_id := self.coordinator.hub_device_id) is not None:
            device_info["via_device_id"] = hub_device_id

        return device_info

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    @override
    def unique_id(self) -> str:
        """Return a unique ID to use for this entity."""
        _LOGGER.debug("Unique_id - %s", self.entity_description.key)
        return f"{self._name}_{self.entity_description.key}"

    @property
    @override
    def translation_key(self) -> str:
        """Return a translation key to use for this entity."""
        _LOGGER.debug("Translation_key - %s", self.entity_description.translation_key)
        return f"{self.entity_description.translation_key}"

    @property
    @override
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

    @override
    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        await super().async_added_to_hass()

        self._async_follow_the_poll()

    @callback
    def _async_follow_the_poll(self) -> None:
        """Write this entity on every refresh of the coordinator.

        Its own hook rather than the body of `async_added_to_hass`, so the one
        kind of entity that has nothing to hear from a poll can leave this out
        without cutting the chain of hooks Home Assistant itself hangs there.
        """
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        """Update entity."""
        await self.coordinator.async_request_refresh()

    def _set_native_value(self, item: str, value: Any) -> None:
        """Write a value to one register of the component this entity is on."""
        # The library builds its components at runtime, so what a component and
        # its registers are is only known to it - `Any` is the honest type here.
        component: Any
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

    def _get_native_value(self, item: str) -> Any:
        """Read the value of one register of the component this entity is on."""
        component: Any
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


class SolarfocusControllerEntity(SolarfocusEntity):
    """An entity of the controller itself rather than of one of its components.

    The service menu codes are the only things this integration reports without
    reading a register: they are arithmetic on the date and on what the display
    of the controller shows. So they belong to the controller, they exist
    whatever components the entry has configured, and none of what a component
    entity does with the coordinator applies to them.
    """

    # There is nothing to poll: these follow the calendar and the user, not the
    # heating system.
    _attr_should_poll = False

    @property
    @override
    def available(self) -> bool:
        """Return True - these do not depend on the controller answering.

        A heating system that cannot be read is exactly when its service menu is
        wanted, so they stay available while every other entity of the entry
        goes unavailable with the poll.

        Only once the entry is set up, though: a heating system that does not
        answer the very first read leaves the whole entry retrying its setup,
        and an entry that never sets up has no entities to keep available.
        """
        return True

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return the controller, which is what these entities belong to.

        The identifier only: `async_setup_entry` registers the device with its
        name, model and software version, and repeating any of that here would
        be a second place to change it.
        """
        return DeviceInfo(identifiers={(DOMAIN, self._entry_id)})

    @callback
    @override
    def _async_follow_the_poll(self) -> None:
        """Do not follow the poll, unlike every entity of a component.

        There is no reading behind these, so a refresh of the coordinator has
        nothing to tell them. Everything else `async_added_to_hass` does is left
        alone - that chain is what restores the number the user last entered.
        """
