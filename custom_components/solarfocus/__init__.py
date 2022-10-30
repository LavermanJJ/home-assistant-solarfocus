"""The Solarfocus integration."""
from __future__ import annotations
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from pysolarfocus import SolarfocusAPI, Systems

from .coordinator import SolarfocusDataUpdateCoordinator, SolarfocusServiceCoordinator
from .const import (
    CONF_BOILER,
    CONF_BUFFER,
    CONF_HEATING_CIRCUIT,
    CONF_SOLARFOCUS_SYSTEM,
    DATA_COORDINATOR,
    DOMAIN,
)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    # Platform.SELECT,
    # Platform.NUMBER,
    # Platform.BUTTON,
    # Platform.BINARY_SENSOR,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Solarfocus from a config entry."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})

    api = SolarfocusAPI(
        ip=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        heating_circuit_count=entry.data[CONF_HEATING_CIRCUIT],
        buffer_count=entry.data[CONF_BUFFER],
        boiler_count=entry.data[CONF_BOILER],
        system=Systems(entry.data[CONF_SOLARFOCUS_SYSTEM]).name,
    )
    coordinator = SolarfocusDataUpdateCoordinator(hass, entry, api)
    service_coordinator = SolarfocusServiceCoordinator(coordinator)

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

    hass.services.async_register(
        DOMAIN, "set_operation_mode", service_coordinator.set_operation_mode
    )

    hass.services.async_register(
        DOMAIN, "set_heating_mode", service_coordinator.set_heating_mode
    )

    hass.services.async_register(
        DOMAIN, "set_boiler_mode", service_coordinator.set_boiler_mode
    )

    hass.services.async_register(
        DOMAIN, "set_smart_grid", service_coordinator.set_smart_grid
    )

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options from user interface."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    _LOGGER.info("async_unload_entry is getting called! unload_ok: %s", unload_ok)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
