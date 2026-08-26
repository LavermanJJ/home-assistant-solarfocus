"""Entity for Solarfocus integration."""


from collections.abc import Generator
from dataclasses import dataclass, replace
import logging
from typing import Any, override

from aiosolarfocus import ComponentId, Systems
from aiosolarfocus.components.base import Component

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
    # The systems whose reading of this register nobody has checked. Not a
    # claim about the register map - the library owns that, and knows exactly
    # what a firmware and a system have. This is the narrower thing it cannot
    # know: that the register is there and answers, and that what it means on
    # that system has never been measured. See the biomass boiler's door
    # contact, the only one.
    unverified_systems: list[Systems] | None = None


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
        # The key with no override, which is all but three of them. An entity
        # whose register the library renamed keeps the key its entity id, its
        # history and its translation are built from, and names the register
        # separately - see the heat pump's seasonal performance figures.
        item=description.item or description.key,
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

    Naming the systems a reading has been checked on says far more plainly than
    listing the ones it has not, and it keeps a system added to the enum later
    out of a reading nobody has measured on it.
    """
    return [system for system in Systems if system not in supported]


def supported_entities[_EntityT: SolarfocusEntity](
    config_entry: SolarfocusConfigEntry, entities: list[_EntityT]
) -> Generator[_EntityT]:
    """Drop the entities this controller has nothing behind.

    The library resolves the register map against the firmware and the system,
    so `supports` is the whole answer to what this controller has: it replaces a
    `min_required_version` and an `unsupported_systems` list carried on every
    description, which were a second copy of the register document and drifted
    from it - a Therminator on 21.140 was offered a `log_wood` sensor for a
    register that firmware does not map, and an Ecotop a buffer `x35_temperature`
    the document gives to the Therminator alone.

    A derived value counts as supported when the registers it is worked out from
    are, which is why this asks the component rather than the register map.

    Two kinds of entity are passed through rather than asked about: the ones
    that read no single register - the climate entity, the water heater - and
    the ones that read no register at all, on the controller rather than on a
    component. `component` is blank on the latter, and there is nothing to ask.
    """
    system = config_entry.data[CONF_SOLARFOCUS_SYSTEM]

    for entity in entities:
        description = entity.entity_description

        unverified = description.unverified_systems
        if unverified is not None and system in unverified:
            continue

        if not description.component or entity.reads_no_single_register:
            yield entity
        elif entity.component.supports(description.item):
            yield entity


class SolarfocusEntity(Entity):
    """Defines a base Solarfocus entity."""

    _attr_should_poll = True
    has_entity_name = True

    #: Whether this entity's `item` names one register of its component. The
    #: climate entity and the water heater read and write several under a key
    #: that is a label rather than a register name, so what they need is the
    #: component, not a register on it - and there is nothing for
    #: `supported_entities` to ask about.
    reads_no_single_register = False

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
        description = self.entity_description
        instance = (
            COMPONENT_DEVICES[description.component_prefix].option,
            description.component_idx,
        )

        return (
            self.coordinator.last_update_success
            and instance not in self.coordinator.failed_components
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

    @property
    def component(self) -> Component:
        """Return the component instance this entity reads and writes.

        `of` answers with a list whatever the component is, including the ones
        a controller only has one of, so which of the two an entity is on stops
        being something this has to know: an index the description does not
        carry is the first and only one.
        """
        description = self.entity_description
        index = int(description.component_idx or 1) - 1

        return self.coordinator.client.of(ComponentId(description.component))[index]

    async def _async_set_native_value(self, item: str, value: Any) -> None:
        """Write a value to one register of the component this entity is on.

        Class access on a register gives its specification, instance access
        gives the reading - so this is the register named by the description,
        handed back to the component it was declared on.

        Everything that used to be here has moved into the library: the two's
        complement of a negative value, and the re-read of the whole component
        afterwards. A write that the controller took updates the component's
        own cache, so the new value is readable straight away.
        """
        component = self.component
        _LOGGER.debug(
            "_async_set_native_value - component: %s, entity: %s, value: %s",
            self.entity_description.component,
            item,
            value,
        )

        await component.write(getattr(type(component), item), value)

        self.async_write_ha_state()

    def _get_native_value(self, item: str) -> Any:
        """Read the value of one register of the component this entity is on.

        Not a coroutine: the reading is already decoded and in hand, and only
        the calls that talk to the controller are awaited.

        `None` is a real answer - the register is not on this firmware or
        system, it has not been read yet or its last read failed, or the channel
        is reporting an open sensor rather than a measurement. Every caller here
        wants the same thing for all three.
        """
        native_value = getattr(self.component, item)

        _LOGGER.debug(
            "_get_native_value - component: %s, entity: %s, value: %s",
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
