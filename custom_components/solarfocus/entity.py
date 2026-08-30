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
        """
        description = self.entity_description
        device = COMPONENT_DEVICES[description.component_prefix]

        device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{self._entry_id}_{description.component_prefix}"
                 f"{description.component_idx}")
            },
            translation_key=device.translation_key,
            # Blank for the components that exist once, and for the single
            # solar circuit that keeps the unnumbered name it had before there
            # could be four of them.
            translation_placeholders={"idx": description.device_idx},
            model=device.model,
            manufacturer=MANUFACTURER,
            # The controller every component hangs off, named by its
            # identifiers rather than by its device id.
            #
            # `via_device_id` is what Home Assistant asks for now, and it is
            # what this used to pass - but the key only exists from core
            # 2026.8, and `hacs.json` offers this integration from 2025.1. On
            # anything older the device registry refuses the keyword outright,
            # which takes down the whole entity: every component sensor, number,
            # select, switch, button, climate and water heater fails to be
            # added, leaving an installation with the two entities of the
            # controller and no component devices at all. See #242, where a
            # Pellet Elegance on core 2026.3.4 lost all 173 of them.
            #
            # `via_device` is deprecated in favour of it and is removed in core
            # 2027.8, so this has to become `via_device_id` before then -
            # together with a minimum core version that has the key.
            via_device=(DOMAIN, self._entry_id),
        )

        return device_info

    @property
    @override
    def available(self) -> bool:
        """Return True if the component this entity sits on was read.

        Two ways to be unavailable, and the entry only knows about the first:
        the whole system stopped answering, so the refresh failed, or this one
        component did while the rest of the system read fine. The second used to
        show as nothing at all - a partial failure is a successful refresh, so
        the component that answers nothing kept the last value it ever returned,
        which reads as a heating system that has stopped moving rather than as a
        component that is not there.

        One device per component is what makes this worth splitting: a component
        that cannot be read greys out its own page and leaves the rest of the
        system alone.

        Writable entities go with it. A component whose registers do not answer
        is not a component to be writing to, and Home Assistant drops
        unavailable entities from service calls, so a `switch`, `number` or
        `select` on it stops accepting writes - the entities of every component
        that does answer keep taking them.
        """
        return self.coordinator.last_update_success and (
            COMPONENT_DEVICES[self.entity_description.component_prefix].option
            not in self.coordinator.failed_components
        )

    @property
    @override
    def unique_id(self) -> str:
        """Return the name the entity registry knows this entity by.

        The entry id, which is the one name an entry has that a user cannot
        change. It used to be the title, and a title is a name the UI offers to
        rename at any moment: every entity of the entry came back from a rename
        with an id Home Assistant had never seen, so the registry kept the old
        one holding its last value and registered a new one beside it, under a
        `_2` suffix because the entity id it wanted was taken.

        Version 10 of the entry rewrites the ids that were built from a title,
        so an entity that has been read since before this keeps its history and
        everything the user set on it.
        """
        return f"{self._entry_id}_{self.entity_description.key}"

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
