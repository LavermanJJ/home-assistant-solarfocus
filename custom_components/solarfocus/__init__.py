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
from homeassistant.core import HomeAssistant
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
    DATA_COORDINATOR,
    DOMAIN,
)
from .coordinator import SolarfocusDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BUTTON,
    Platform.BINARY_SENSOR,
    Platform.WATER_HEATER,
    Platform.CLIMATE,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Solarfocus from a config entry."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})

    api = SolarfocusAPI(
        ip=entry.options[CONF_HOST],
        port=entry.options[CONF_PORT],
        heating_circuit_count=entry.options[CONF_HEATING_CIRCUIT],
        buffer_count=entry.options[CONF_BUFFER],
        boiler_count=entry.options[CONF_BOILER],
        system=Systems(entry.data[CONF_SOLARFOCUS_SYSTEM]),
        api_version=ApiVersions(entry.options[CONF_API_VERSION]),
    )
    coordinator = SolarfocusDataUpdateCoordinator(hass, entry, api)

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    # Registers update listener to update config entry when options are updated.
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    # unsub_options_update_listener = entry.add_update_listener(async_update_options)
    # Store a reference to the unsubscribe function to cleanup if an entry is unloaded.

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        # UPDATE_LISTENER: unsub_options_update_listener,
    }

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options from user interface."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    _LOGGER.info("Async_unload_entry is getting called! unload_ok: %s", unload_ok)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    version = config_entry.version

    _LOGGER.info("Migrating from version %s", version)

    if version == 1:
        # Config allows multiple heatings, buffers, and boilers
        # and differentiates system (vampair, therminator)
        new = {**config_entry.data}

        new[CONF_HEATING_CIRCUIT] = 1 if config_entry.data[CONF_HEATING_CIRCUIT] else 0
        new[CONF_BUFFER] = 1 if config_entry.data[CONF_BUFFER] else 0
        new[CONF_BOILER] = 1 if config_entry.data[CONF_BOILER] else 0

        new[CONF_SOLARFOCUS_SYSTEM] = (
            config_entry.data[CONF_SOLARFOCUS_SYSTEM]
            if CONF_SOLARFOCUS_SYSTEM in config_entry.data
            else Systems.VAMPAIR
        )

        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, data=new)

    if version == 2:
        # Add option to configure solar
        new = {**config_entry.data}

        new[CONF_SOLAR] = False

        config_entry.version = 3
        hass.config_entries.async_update_entry(config_entry, data=new)

    if version == 3:
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
        new_options[CONF_BIOMASS_BOILER] = new_data[CONF_BIOMASS_BOILER]

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
        del new_data[CONF_BIOMASS_BOILER]

        config_entry.version = 4
        hass.config_entries.async_update_entry(
            config_entry, data=new_data, options=new_options
        )

    if version == 4:
        new_data = {**config_entry.data}
        new_options = {**config_entry.options}

        # Rename pelletsboiler to biomassboiler
        new_options[CONF_BIOMASS_BOILER] = new_options["pelletsboiler"]
        del new_options["pelletsboiler"]

        config_entry.version = 5
        hass.config_entries.async_update_entry(
            config_entry, data=new_data, options=new_options
        )

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    _LOGGER.debug(
        "Config Entries data: %s, options: %s", config_entry.data, config_entry.options
    )

    return True
