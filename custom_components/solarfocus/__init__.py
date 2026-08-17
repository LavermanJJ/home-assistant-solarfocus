"""The Solarfocus integration."""

from __future__ import annotations

from collections import Counter
import logging

from pysolarfocus import ApiVersions, SolarfocusAPI, Systems

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
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
    DOMAIN,
    build_unique_id,
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

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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


@callback
def _async_identify_device_by_entry_id(
    hass: HomeAssistant, entry: ConfigEntry
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
    device under the new title in the first place. The one the entities are on
    is the one that is kept; the others hold nothing and would stay in the
    registry forever otherwise, since they still name a config entry that
    exists.
    """
    registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(registry, entry.entry_id)
    identifier = (DOMAIN, entry.entry_id)

    if not devices or any(identifier in device.identifiers for device in devices):
        return

    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    entity_count = Counter(entity.device_id for entity in entities)
    keep = max(devices, key=lambda device: entity_count[device.id])

    registry.async_update_device(keep.id, new_identifiers={identifier})

    for device in devices:
        if device.id != keep.id:
            _LOGGER.debug(
                "Removing device %s, left behind by a rename of %s",
                device.id,
                entry.title,
            )
            registry.async_remove_device(device.id)


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


async def async_migrate_entry(hass, config_entry: ConfigEntry):
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

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    _LOGGER.debug(
        "Config Entries data: %s, options: %s", config_entry.data, config_entry.options
    )

    return True
