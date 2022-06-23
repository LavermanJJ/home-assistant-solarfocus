"""The Solarfocus integration."""
from __future__ import annotations
from datetime import timedelta
import logging


import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv

from pymodbus.client.sync import ModbusTcpClient as ModbusClient

from .coordinator import SolarfocusDataUpdateCoordinator
from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SELECT]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Solarfocus from a config entry."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})

    modbus_client = ModbusClient(entry.data[CONF_HOST], entry.data[CONF_PORT])
    coordinator = SolarfocusDataUpdateCoordinator(hass, modbus_client, entry)

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = coordinator

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    # hass.data[DOMAIN][entry.entry_id] = coordinator
    #
    # for platform in PLATFORMS:
    #    if entry.options.get(platform, True):
    #        hass.async_add_job(
    #            hass.config_entries.async_forward_entry_setup(entry, platform)
    #        )
    #
    # entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    # hass.data.setdefault(DOMAIN, {})
    # hass.data[DOMAIN][entry.entry_id] = coordinator

    # hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    # hass.services.async_register(
    #    DOMAIN, "enable_cooling", coordinator.update_hc1_cooling
    # )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
