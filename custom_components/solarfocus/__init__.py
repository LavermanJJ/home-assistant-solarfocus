"""The Solarfocus integration."""

from __future__ import annotations

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
from .coordinator import SolarfocusConfigEntry, SolarfocusDataUpdateCoordinator

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

    api = SolarfocusAPI(
        ip=entry.options[CONF_HOST],
        port=entry.options[CONF_PORT],
        heating_circuit_count=entry.options[CONF_HEATING_CIRCUIT],
        buffer_count=entry.options[CONF_BUFFER],
        boiler_count=entry.options[CONF_BOILER],
        fresh_water_module_count=entry.options[CONF_FRESH_WATER_MODULE],
        solar_count=solar_count(entry.options),
        system=Systems(entry.data[CONF_SOLARFOCUS_SYSTEM]),
        api_version=ApiVersions(entry.options[CONF_API_VERSION]),
    )
    coordinator = SolarfocusDataUpdateCoordinator(hass, entry, api)

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        # Reading every configured component once tells us whether the entry can
        # be set up at all; Home Assistant retries the setup afterwards.
        raise ConfigEntryNotReady(
            f"Cannot read from the Solarfocus system at "
            f"{entry.options[CONF_HOST]}:{entry.options[CONF_PORT]}"
        ) from coordinator.last_exception

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Registers update listener to update config entry when options are updated.
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


@callback
def _async_sync_unique_id(hass: HomeAssistant, entry: SolarfocusConfigEntry) -> None:
    """Keep the unique id on the address the entry is actually talking to.

    The address can be changed in the options. Doing this here rather than in
    the options flow keeps the update out of the flow, where it would fire the
    update listener and reload the entry against the options it is about to
    replace. Saving options reloads the entry, so this runs right after.
    """
    if entry.unique_id is None:
        # A duplicate the migration deliberately left without one.
        return

    unique_id = build_unique_id(entry.options[CONF_HOST], entry.options[CONF_PORT])
    if entry.unique_id == unique_id:
        return

    if any(
        other.unique_id == unique_id and other.entry_id != entry.entry_id
        for other in hass.config_entries.async_entries(DOMAIN)
    ):
        # The options flow refuses this, so it takes a hand-edited entry to get
        # here. Leave the old unique id rather than colliding.
        _LOGGER.warning(
            "Not moving the unique id of %s to %s, another entry already has it",
            entry.title,
            unique_id,
        )
        return

    hass.config_entries.async_update_entry(entry, unique_id=unique_id)


async def async_update_options(
    hass: HomeAssistant, entry: SolarfocusConfigEntry
) -> None:
    """Update options from user interface."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SolarfocusConfigEntry) -> bool:
    """Unload a config entry.

    The coordinator lives on the entry, so unloading the platforms is all there
    is to clean up.
    """
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


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

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    _LOGGER.debug(
        "Config Entries data: %s, options: %s", config_entry.data, config_entry.options
    )

    return True
