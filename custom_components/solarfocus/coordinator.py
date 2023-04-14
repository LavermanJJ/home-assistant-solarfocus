"""Coordinator for Solarfocus integration"""

from datetime import timedelta
import logging
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


from .const import (
    CONF_BOILER,
    CONF_BUFFER,
    CONF_FRESH_WATER_MODULE,
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
    CONF_PELLETSBOILER,
    CONF_PHOTOVOLTAIC,
    CONF_SOLAR,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class SolarfocusDataUpdateCoordinator(DataUpdateCoordinator):
    """Get the latest data and update the states."""

    def __init__(self, hass, entry, api) -> None:
        """Init the Solarfocus data object."""

        self.api = api
        self.api.connect()

        self.name = entry.title
        self._entry = entry
        self.hass = hass

        _LOGGER.info(
            "SolarfocusDataUpdateCoordinator.__init__(), SCAN Interval: %s",
            self._entry.options[CONF_SCAN_INTERVAL],
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=self._entry.options[CONF_SCAN_INTERVAL]),
        )

    async def _async_update_data(self):
        """Update data via library."""

        if not self.api.is_connected:
            self.api.connect()

        success = True

        if self._entry.options[CONF_HEATING_CIRCUIT]:
            success &= True and await self.hass.async_add_executor_job(
                self.api.update_heating
            )

        if self._entry.options[CONF_BUFFER]:
            success &= True and await self.hass.async_add_executor_job(
                self.api.update_buffer
            )

        if self._entry.options[CONF_BOILER]:
            success &= True and await self.hass.async_add_executor_job(
                self.api.update_boiler
            )

        if self._entry.options[CONF_HEATPUMP]:
            success &= True and await self.hass.async_add_executor_job(
                self.api.update_heatpump
            )

        if self._entry.options[CONF_PHOTOVOLTAIC]:
            success &= True and await self.hass.async_add_executor_job(
                self.api.update_photovoltaic
            )

        if self._entry.options[CONF_PELLETSBOILER]:
            success &= True and await self.hass.async_add_executor_job(
                self.api.update_pelletsboiler
            )

        if self._entry.options[CONF_SOLAR]:
            success &= True and await self.hass.async_add_executor_job(
                self.api.update_solar
            )

        if self._entry.options[CONF_FRESH_WATER_MODULE]:
            success &= True and await self.hass.async_add_executor_job(
                self.api.update_fresh_water_modules
            )

        if not success:
            _LOGGER.debug("Data updated failed")
        else:
            _LOGGER.debug("Data updated successfully")
