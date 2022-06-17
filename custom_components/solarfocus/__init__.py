"""The Solarfocus integration."""
from __future__ import annotations
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pysolarfocus import SolarfocusAPI
from pymodbus.client.sync import ModbusTcpClient as ModbusClient

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.SENSOR]


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
        if entry.options.get(platform, True):
            hass.async_add_job(
                hass.config_entries.async_forward_entry_setup(entry, platform)
            )

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

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


class SolarfocusDataUpdateCoordinator(DataUpdateCoordinator):
    """Get the latest data and update the states."""

    def __init__(self, hass, modbus_client, entry):
        """Init the Solarfocus data object."""

        self.api = SolarfocusAPI(modbus_client, 1)
        self.name = entry.title
        self._entry = entry
        self.hass = hass

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=self._entry.data[CONF_SCAN_INTERVAL]),
        )

    async def _async_update_data(self):
        """Update data via library."""
        if not await self.hass.async_add_executor_job(self.api.update):
            _LOGGER.debug("Data updated failed")
        else:
            _LOGGER.debug("Data updated successfully")


class SolarfocusEntity(Entity):
    """Defines a base Solarfocus entity."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: SolarfocusDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the Atag entity."""
        self.coordinator = coordinator
        self._name = coordinator._entry.title
        self._state = None

        self.entity_description = description

    @property
    def device_info(self) -> dict:
        """Return info for device registry."""
        device = self._name
        return {
            "identifiers": {(DOMAIN, device)},
            "name": "Solarfocus eco manager-touch",
            "model": "eco manager-touch",
            "sw_version": "21.040",
            "manufacturer": "Solarfocus",
        }

    @property
    def state(self):
        """Return the current state."""
        sensor = self.entity_description.key
        value = getattr(self.coordinator.api, sensor)
        if isinstance(value, float):
            try:
                rounded_value = round(float(value), 2)
                return rounded_value
            except ValueError:
                return value
        return value

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        sensor = self.entity_description.key
        return f"{self._name}_{sensor}"

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update entity."""
        await self.coordinator.async_request_refresh()
