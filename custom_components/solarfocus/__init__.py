"""The Solarfocus integration."""

from __future__ import annotations

from collections import Counter
import logging

from pysolarfocus import ApiVersions, SolarfocusAPI, Systems

from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from .const import (
    CONF_BIOMASS_BOILER,
    CONF_BOILER,
    CONF_BUFFER,
    CONF_FRESH_WATER_MODULE,
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
    CONF_PHOTOVOLTAIC,
    CONF_SOLAR,
    CONF_SOLARFOCUS_SYSTEM,
    CONTROLLER_NAME,
    DOMAIN,
    MANUFACTURER,
    build_unique_id,
    expected_device_identifiers,
    solar_count,
)
from .coordinator import (
    SolarfocusConfigEntry,
    SolarfocusDataUpdateCoordinator,
    async_delete_component_issues,
)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: SolarfocusConfigEntry) -> bool:
    """Set up Solarfocus from a config entry."""
    _async_sync_unique_id(hass, entry)
    _async_report_duplicate_entry(hass, entry)

    api = SolarfocusAPI(
        ip=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        heating_circuit_count=entry.options[CONF_HEATING_CIRCUIT],
        buffer_count=entry.options[CONF_BUFFER],
        boiler_count=entry.options[CONF_BOILER],
        fresh_water_module_count=entry.options[CONF_FRESH_WATER_MODULE],
        solar_count=solar_count(entry),
        system=Systems(entry.data[CONF_SOLARFOCUS_SYSTEM]),
        api_version=ApiVersions(entry.data[CONF_API_VERSION]),
    )
    coordinator = SolarfocusDataUpdateCoordinator(hass, entry, api)

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        # Reading every configured component once tells us whether the entry can
        # be set up at all; Home Assistant retries the setup afterwards.
        #
        # The two ways that fails are worth telling apart, because they send the
        # user to different places: nothing at the address to talk to at all, or
        # a controller that answered the connection and then none of the
        # registers. Whether the library is still connected is what says which.
        address = f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"
        if not api.is_connected:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"address": address},
            ) from coordinator.last_exception

        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_set_up",
            translation_placeholders={"address": address},
        ) from coordinator.last_exception

    hub = _async_hub_device(hass, entry, api)
    coordinator.hub_device_id = hub.id
    entry.runtime_data = coordinator

    await _async_align_solar_unique_ids(hass, entry)

    known = {
        device.id
        for device in dr.async_entries_for_config_entry(
            dr.async_get(hass), entry.entry_id
        )
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _async_inherit_the_hub_area(hass, entry, hub, known)
    _async_remove_gone_components(hass, entry)

    # Registers update listener to update config entry when options are updated.
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


@callback
def _async_sync_unique_id(hass: HomeAssistant, entry: SolarfocusConfigEntry) -> None:
    """Keep the unique id on the address the entry is actually talking to.

    The reconfigure flow can move an entry to another address, and a
    hand-edited entry can arrive at one, so the id is settled here rather than
    in the flow - where updating it would fire the update listener and reload
    the entry against the address it is about to leave.

    An entry the migration left without a unique id is given one here as soon
    as the address is free, which is how the duplicate reported below stops
    being reported: the user removes the other entry, and the one they kept
    takes the address over on its next load.
    """
    unique_id = build_unique_id(entry.data[CONF_HOST], entry.data[CONF_PORT])
    if entry.unique_id == unique_id:
        return

    if any(
        other.unique_id == unique_id and other.entry_id != entry.entry_id
        for other in hass.config_entries.async_entries(DOMAIN)
    ):
        # Another entry is on this address already: the duplicate the migration
        # deliberately left without a unique id, or a hand-edited one, which the
        # options flow refuses. Either way this entry keeps what it has rather
        # than colliding.
        if entry.unique_id is not None:
            _LOGGER.warning(
                "Not moving the unique id of %s to %s, another entry already has it",
                entry.title,
                unique_id,
            )
        return

    hass.config_entries.async_update_entry(entry, unique_id=unique_id)


@callback
def _async_report_duplicate_entry(
    hass: HomeAssistant, entry: SolarfocusConfigEntry
) -> None:
    """Tell the user about the second entry nothing here can fix.

    Two entries for one controller predate the unique id, see #185. The
    migration left the later one without one rather than colliding, which keeps
    it working - and leaves two entries polling one heating system over one
    Modbus connection, with every entity of it existing twice.

    Which of the two to remove is the user's to say: they are the one who knows
    which set of entities their dashboards and automations name.
    """
    if entry.unique_id is not None:
        # Removing the other entry and reloading this one takes the address
        # over, which is what clears this.
        ir.async_delete_issue(hass, DOMAIN, _duplicate_issue_id(entry))
        return

    ir.async_create_issue(
        hass,
        DOMAIN,
        _duplicate_issue_id(entry),
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="duplicate_entry",
        translation_placeholders={
            "title": entry.title,
            "address": build_unique_id(
                entry.data[CONF_HOST], entry.data[CONF_PORT]
            ),
        },
    )


def _duplicate_issue_id(entry: SolarfocusConfigEntry) -> str:
    """Return the issue id naming this entry as one of a duplicate pair."""
    return f"duplicate_entry_{entry.entry_id}"


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: SolarfocusConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Let the user delete a device of a component their system does not have.

    A component that is still configured is refused: deleting it would only
    have it built again on the next load, with a new device the user has to
    put back in its area.
    """
    return device.identifiers.isdisjoint(expected_device_identifiers(entry))


async def _async_align_solar_unique_ids(
    hass: HomeAssistant, entry: SolarfocusConfigEntry
) -> None:
    """Follow the one solar circuit that is keyed without its index.

    A single solar circuit keeps the unnumbered key it had before there could
    be four of them - `so_collector_temperature_1`, not `so1_...` - so raising
    the count to two renames every one of its entities, and lowering it back
    renames them again. Left alone, the set under the other key stays in the
    registry as entities that will never be written to again, on a device that
    is still configured and so is never removed with them.

    Renaming rather than removing: it is the same reading of the same circuit,
    and the entity keeps its id, its history and anything the user set on it.
    """
    count = solar_count(entry)
    if not count:
        # No solar at all: the device is not expected, and it takes its
        # entities with it when it goes.
        return

    old, new = ("so_", "so1_") if count > 1 else ("so1_", "so_")
    prefix = f"{entry.entry_id}_"
    registry = er.async_get(hass)
    taken = {registered.unique_id for registered in registry.entities.values()}

    @callback
    def _renamed(registered: er.RegistryEntry) -> dict[str, str] | None:
        if not registered.unique_id.startswith(prefix + old):
            return None

        renamed = prefix + new + registered.unique_id[len(prefix + old) :]
        if renamed in taken:
            # Both sets exist, which takes a migration that stopped halfway.
            # The one under the key in use is the one being written to.
            return None

        return {"new_unique_id": renamed}

    await er.async_migrate_entries(hass, entry.entry_id, _renamed)


@callback
def _async_inherit_the_hub_area(
    hass: HomeAssistant,
    entry: SolarfocusConfigEntry,
    hub: dr.DeviceEntry,
    known: set[str],
) -> None:
    """Put a component device in the area its controller is in.

    Everything of an entry used to be on one device, so a user who put that
    device in a room put every entity of their heating system in it. Splitting
    the components off would have taken all of them out again: a new device is
    in no area, and an automation or a voice command scoped to a room stops
    matching entities that are in none.

    Only devices that were not there before this load, which on the first load
    after the split is all of them. A device the user has since moved somewhere
    else, or deliberately taken out of an area, is not one of those and is left
    alone.
    """
    if hub.area_id is None:
        return

    registry = dr.async_get(hass)

    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if device.id in known or device.area_id is not None:
            continue

        registry.async_update_device(device.id, area_id=hub.area_id)


@callback
def _async_remove_gone_components(
    hass: HomeAssistant, entry: SolarfocusConfigEntry
) -> None:
    """Remove the devices of components this entry no longer has.

    Lowering a count from four to two leaves two devices behind. Nothing takes
    them away on their own: they still name a config entry that exists, so the
    registry keeps them, and with them every entity that was on them - reading
    the value it held when the component was last polled.

    Removing the device is what removes those entities; the entity registry
    takes them with it.
    """
    registry = dr.async_get(hass)
    expected = expected_device_identifiers(entry)

    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if not device.identifiers.isdisjoint(expected):
            continue

        _LOGGER.debug(
            "Removing device %s, its component is not configured any more",
            device.name,
        )
        registry.async_remove_device(device.id)


@callback
def _async_hub_device(
    hass: HomeAssistant, entry: SolarfocusConfigEntry, api: SolarfocusAPI
) -> dr.DeviceEntry:
    """Register the controller every component of this entry hangs off.

    This is the device the entry has had all along - same identifier, so an
    existing installation keeps the one it has, with the area it is in and the
    name the user gave it, and the components appear underneath it rather than
    beside it.

    It is registered here rather than left to an entity, because a component
    device points at it by device id, which is only known once it exists.

    The name is what the controller is called - `Solarfocus` is the make, and
    the model page of the device already says it. Which heating system this one
    belongs to is the name of the entry, not of the device: two systems in one
    Home Assistant are two entries, and a user who wants to tell their devices
    apart by name renames this one, which the registry keeps separately.
    """
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=CONTROLLER_NAME,
        model=api.system.value,
        sw_version=api.api_version.value,
        manufacturer=MANUFACTURER,
    )


@callback
def _async_identify_device_by_entry_id(
    hass: HomeAssistant, entry: SolarfocusConfigEntry
) -> None:
    """Re-identify the device of this entry by the entry id.

    The identifier is changed on a device that is already there rather than a
    new one being created: it keeps its id, and with it the area it is in, the
    name the user gave it, and every automation and dashboard that points at it
    by device.

    The old identifier is not looked for by name. It was the title of the entry
    as of the last successful setup, and a title changed since then - or changed
    while the controller was unreachable - is not the one the device carries.
    Every device of this entry is a device this migration is about.

    There can be more than one, because renaming an entry is what built a second
    device under the new title in the first place. The one the live entities sit
    on is the one that is kept; the others hold nothing and would stay in the
    registry forever otherwise, since they still name a config entry that
    exists.

    Which entities are the live ones is the same question version 10 asks, and
    it is asked here because removing a device takes its entities with it. Two
    devices left by a rename hold the same number of entities, so counting alone
    picks between them by registry order - and picking the abandoned one to keep
    would remove the live set before version 10 ever saw it.
    """
    registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(registry, entry.entry_id)
    identifier = (DOMAIN, entry.entry_id)

    if not devices or any(identifier in device.identifiers for device in devices):
        return

    registered = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    live = _async_live_entities(entry, registered)
    on_a_device = registered if live is None else live[1]
    entity_count = Counter(one.device_id for one in on_a_device)
    keep = max(devices, key=lambda device: entity_count[device.id])

    registry.async_update_device(keep.id, new_identifiers={identifier})

    if live is None or not entity_count[keep.id]:
        # Nothing here says which of these devices holds the entities the user
        # has been reading, so nothing here may remove one: a device leaves with
        # every entity registered on it. A device that holds nothing is a stray
        # row in a registry; a device removed on a guess is history the user
        # cannot get back.
        return

    for device in devices:
        if device.id != keep.id:
            _LOGGER.debug(
                "Removing device %s, left behind by a rename of %s",
                device.id,
                entry.title,
            )
            registry.async_remove_device(device.id)


@callback
def _async_entities_by_name(
    entry: SolarfocusConfigEntry, registered: list[er.RegistryEntry]
) -> dict[str, list[er.RegistryEntry]]:
    """Group the entities of this entry by the name their unique ids begin with.

    The two names an entry knows: the title it carries now, and the name it was
    created with, which sits in `data[CONF_NAME]` and which nothing renames.

    An id is attributed to the longest of them it begins with, because one can
    be a prefix of the other. An entry created as `Solarfocus_Keller` and since
    renamed to `Solarfocus` has every abandoned id beginning with the current
    title as well, and reading those as ids of the current title would migrate
    the abandoned set to `{entry_id}_Keller_...` rather than recognising it as
    the leftover it is - leaving the duplication in place for good.

    Names that no id begins with are left out, so a name is in the result only
    if there are entities under it.
    """
    names = [entry.title]
    if (created_as := entry.data.get(CONF_NAME)) is not None:
        names.append(created_as)

    prefixes = sorted({f"{name}_" for name in names}, key=len, reverse=True)
    sets: dict[str, list[er.RegistryEntry]] = {prefix: [] for prefix in prefixes}

    for one in registered:
        for prefix in prefixes:
            if one.unique_id.startswith(prefix):
                sets[prefix].append(one)
                break

    return {prefix: entities for prefix, entities in sets.items() if entities}


@callback
def _async_live_entities(
    entry: SolarfocusConfigEntry, registered: list[er.RegistryEntry]
) -> tuple[str, list[er.RegistryEntry]] | None:
    """Return the name the live entities carry, and the entities under it.

    The live set is the one the user has been reading: the one the entry
    registered the last time it was set up. A rename left the set of the
    previous title in the registry beside the new one, so there can be several,
    and only one of them is still being written.

    Under the current title, in a registry where the entry was set up at least
    once since it was last renamed - which is every registry that has never seen
    a rename, and every one where the rename happened while the entry was
    loaded. That the set under the title really is the last one registered is
    what `created_at` says: an entity outside it that the registry recorded
    later means a set was registered after this one, and then the title names an
    abandoned set rather than the live one - an entry renamed away and back
    again is read correctly this way.

    A title changed while the entry was not loaded is a title no entity carries.
    The name the entry was created with is what those entities carry instead,
    but only where that name still accounts for every entity of the entry: an
    id outside it means some later title registered a set, and the created name
    is then as abandoned as the title is.

    `None` where neither name settles it. Renaming nothing and migrating nothing
    is the only safe answer: the sets are indistinguishable from here, and the
    wrong one deleted is the user's history gone.
    """
    sets = _async_entities_by_name(entry, registered)
    title_prefix = f"{entry.title}_"

    if (under_title := sets.get(title_prefix)) is not None:
        newest = max(one.created_at for one in under_title)
        named = {one.entity_id for one in under_title}
        outside = [one for one in registered if one.entity_id not in named]
        if all(one.created_at <= newest for one in outside):
            return title_prefix, under_title

        return None

    if (created_as := entry.data.get(CONF_NAME)) is not None:
        under_created = sets.get(f"{created_as}_")
        if under_created is not None and len(under_created) == len(registered):
            return f"{created_as}_", under_created

    return None


async def _async_identify_entities_by_entry_id(
    hass: HomeAssistant, entry: SolarfocusConfigEntry
) -> bool:
    """Take the entity unique ids off the title of the entry.

    An entity was identified by the title and its key, and the title is a name
    the UI renames at any moment. Renaming an entry therefore gave every entity
    of it an id Home Assistant had never seen: the registry kept the old entity,
    holding the last value it was written, and registered a new one beside it
    under a `_2` suffix, which nobody's dashboards or automations name. An entry
    of fifteen entities came out of a rename with thirty.

    The ids are rewritten in place rather than left to the next setup to
    register anew, so an entity keeps its entity id, its area, its
    customisations and its history - the same promise the device half of this
    made in version 9.

    What the entity id is built from does not change with any of this: the name
    of the device and the English `object_id_name`, neither of which has ever
    been the title.

    Returns whether the entry may move on to version 10, which is whether the
    live set could be named at all.
    """
    registry = er.async_get(hass)
    registered = er.async_entries_for_config_entry(registry, entry.entry_id)
    if not registered:
        return True

    if (live := _async_live_entities(entry, registered)) is None:
        # Every set in the registry is under a title that is neither the current
        # one nor the one the entry was created with, so which of them is the
        # live one cannot be told from here. Renaming nothing leaves the entry
        # exactly as it is rather than picking the wrong set to keep - and it
        # stays at version 9, so this is asked again rather than the next setup
        # registering a third set beside the ones already there.
        _LOGGER.warning(
            "Not re-identifying the entities of %s, none of them carries a name"
            " this entry still knows. Rename the entry back to the name these"
            " unique ids begin with and restart to migrate it: %s",
            entry.title,
            ", ".join(sorted(one.unique_id for one in registered)),
        )
        return False

    prefix, entities = live
    keep = {one.entity_id for one in entities}

    # Everything outside the live set is what a rename left behind: an entity
    # that was last written before that rename and never will be again. It would
    # otherwise migrate to the same id as the live entity it is a copy of, and
    # the registry refuses two entities under one id.
    for stale in registered:
        if stale.entity_id not in keep:
            _LOGGER.debug(
                "Removing entity %s, left behind by a rename of %s",
                stale.entity_id,
                entry.title,
            )
            registry.async_remove(stale.entity_id)

    @callback
    def _identified(one: er.RegistryEntry) -> dict[str, str] | None:
        if one.entity_id not in keep:
            return None

        return {"new_unique_id": f"{entry.entry_id}_{one.unique_id[len(prefix) :]}"}

    await er.async_migrate_entries(hass, entry.entry_id, _identified)
    return True


async def async_update_options(
    hass: HomeAssistant, entry: SolarfocusConfigEntry
) -> None:
    """Update options from user interface."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SolarfocusConfigEntry) -> bool:
    """Unload a config entry.

    The coordinator lives on the entry, so the platforms are all there is to
    unload. The repair issues are not on the entry and outlive it, including
    the removal of the entry they name, so they are deleted here.
    """
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    ir.async_delete_issue(hass, DOMAIN, _duplicate_issue_id(entry))
    async_delete_component_issues(hass, entry)

    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: SolarfocusConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: SolarfocusConfigEntry
) -> bool:
    """Migrate old entry."""
    _LOGGER.info("Migrating from version %s", config_entry.version)

    # Every step re-reads config_entry.version so that an entry coming from an old
    # version is migrated through all following steps in one go.
    if config_entry.version == 1:
        # Config allows multiple heatings, buffers, and boilers
        # and differentiates system (vampair, therminator)
        new = {**config_entry.data}

        new[CONF_HEATING_CIRCUIT] = 1 if config_entry.data[CONF_HEATING_CIRCUIT] else 0
        new[CONF_BUFFER] = 1 if config_entry.data[CONF_BUFFER] else 0
        new[CONF_BOILER] = 1 if config_entry.data[CONF_BOILER] else 0

        new[CONF_SOLARFOCUS_SYSTEM] = config_entry.data.get(
            CONF_SOLARFOCUS_SYSTEM, Systems.VAMPAIR
        )

        hass.config_entries.async_update_entry(config_entry, data=new, version=2)

    if config_entry.version == 2:
        # Add option to configure solar
        new = {**config_entry.data}

        new[CONF_SOLAR] = False

        hass.config_entries.async_update_entry(config_entry, data=new, version=3)

    if config_entry.version == 3:
        new_data = {**config_entry.data}
        new_options = {**config_entry.options}

        # Add option to select api version
        new_options[CONF_API_VERSION] = "21.140"
        new_options[CONF_FRESH_WATER_MODULE] = 0

        # Move options from data to options
        new_options[CONF_HOST] = new_data[CONF_HOST]
        new_options[CONF_PORT] = new_data[CONF_PORT]
        new_options[CONF_SCAN_INTERVAL] = new_data[CONF_SCAN_INTERVAL]
        new_options[CONF_BOILER] = new_data[CONF_BOILER]
        new_options[CONF_BUFFER] = new_data[CONF_BUFFER]
        new_options[CONF_HEATING_CIRCUIT] = new_data[CONF_HEATING_CIRCUIT]
        new_options[CONF_PHOTOVOLTAIC] = new_data[CONF_PHOTOVOLTAIC]
        new_options[CONF_SOLAR] = new_data[CONF_SOLAR]
        new_options[CONF_HEATPUMP] = new_data[CONF_HEATPUMP]

        # The biomass boiler is still called "pelletsboiler" at this version, the
        # rename happens in the next migration step.
        biomass_boiler_key = (
            "pelletsboiler" if "pelletsboiler" in new_data else CONF_BIOMASS_BOILER
        )
        new_options["pelletsboiler"] = new_data[biomass_boiler_key]

        # Remove moved data
        del new_data[CONF_HOST]
        del new_data[CONF_PORT]
        del new_data[CONF_SCAN_INTERVAL]
        del new_data[CONF_BOILER]
        del new_data[CONF_BUFFER]
        del new_data[CONF_HEATING_CIRCUIT]
        del new_data[CONF_PHOTOVOLTAIC]
        del new_data[CONF_SOLAR]
        del new_data[CONF_HEATPUMP]
        del new_data[biomass_boiler_key]


        hass.config_entries.async_update_entry(
            config_entry, data=new_data, options=new_options, version=4
        )

    if config_entry.version == 4:
        new_data = {**config_entry.data}
        new_options = {**config_entry.options}

        # Rename pelletsboiler to biomassboiler
        new_options[CONF_BIOMASS_BOILER] = new_options.pop(
            "pelletsboiler", new_options.get(CONF_BIOMASS_BOILER, False)
        )


        hass.config_entries.async_update_entry(
            config_entry, data=new_data, options=new_options, version = 5
        )

    if config_entry.version == 5:
        new_data = {**config_entry.data}
        new_options = {**config_entry.options}

        # Convert solar from boolean to integer for multiple solar instances support
        # This maintains backwards compatibility while enabling multiple instances
        # for API versions >= 25.030
        if isinstance(new_options.get(CONF_SOLAR), bool):
            new_options[CONF_SOLAR] = 1 if new_options[CONF_SOLAR] else 0

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, options=new_options, version=6
        )

    if config_entry.version == 6:
        # Entries created before the config flow assigned a unique id have none,
        # so the duplicate check would not see them. Backfill it from the address
        # the entry is already talking to.
        unique_id = build_unique_id(
            config_entry.options[CONF_HOST], config_entry.options[CONF_PORT]
        )
        already_taken = any(
            entry.unique_id == unique_id and entry.entry_id != config_entry.entry_id
            for entry in hass.config_entries.async_entries(DOMAIN)
        )
        if already_taken:
            # Two entries for the same controller only existed because nothing
            # prevented it. Leave this one without a unique id rather than
            # creating a collision; it keeps working as before.
            _LOGGER.warning(
                "Config entry %s points at the same Solarfocus system as another"
                " entry, it is left without a unique id",
                config_entry.title,
            )

        hass.config_entries.async_update_entry(
            config_entry,
            unique_id=None if already_taken else unique_id,
            version=7,
        )

    if config_entry.version == 7:
        # Where the controller is and which register layout it speaks are what
        # it takes to read anything at all, so they belong in `data`. `options`
        # keeps what a user changes about an entry that already works: how often
        # to poll, and which components to poll.
        new_data = {**config_entry.data}
        new_options = {**config_entry.options}

        for setting in (CONF_HOST, CONF_PORT, CONF_API_VERSION):
            new_data[setting] = new_options.pop(setting)

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, options=new_options, version=8
        )

    if config_entry.version == 8:
        # The device was identified by the title of the entry, so renaming an
        # entry left its device behind and built a second one next to it. The
        # entry id is the one name an entry has that a user cannot change.
        _async_identify_device_by_entry_id(hass, config_entry)

        hass.config_entries.async_update_entry(config_entry, version=9)

    if config_entry.version == 9:
        # The other half of the same rename: an entity was identified by the
        # title as well, so a rename doubled every entity of the entry - the
        # dead one keeping the entity id and the live one taking a `_2`.
        if not await _async_identify_entities_by_entry_id(hass, config_entry):
            # The live set could not be named, so the entities are still under a
            # title. Moving to version 10 would settle that for good - the next
            # setup registers the entry id set beside them and this never runs
            # again - so the entry stays where it is and the migration fails
            # visibly instead.
            return False

        hass.config_entries.async_update_entry(config_entry, version=10)

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    _LOGGER.debug(
        "Config Entries data: %s, options: %s", config_entry.data, config_entry.options
    )

    return True
