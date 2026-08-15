"""Coordinator for Solarfocus integration."""

from datetime import timedelta
import logging

from pysolarfocus import SolarfocusAPI

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_BIOMASS_BOILER,
    CONF_BOILER,
    CONF_BUFFER,
    CONF_FRESH_WATER_MODULE,
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
    CONF_PHOTOVOLTAIC,
    CONF_SOLAR,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Config option -> the library call that reads the registers of that component.
COMPONENT_UPDATES: tuple[tuple[str, str], ...] = (
    (CONF_HEATING_CIRCUIT, "update_heating"),
    (CONF_BUFFER, "update_buffer"),
    (CONF_BOILER, "update_boiler"),
    (CONF_HEATPUMP, "update_heatpump"),
    (CONF_PHOTOVOLTAIC, "update_photovoltaic"),
    (CONF_BIOMASS_BOILER, "update_biomassboiler"),
    (CONF_SOLAR, "update_solar"),
    (CONF_FRESH_WATER_MODULE, "update_fresh_water_modules"),
)


class SolarfocusDataUpdateCoordinator(DataUpdateCoordinator):
    """Get the latest data and update the states."""

    def __init__(self, hass, entry, api: SolarfocusAPI) -> None:
        """Init the Solarfocus data object."""

        self.api = api
        self._entry = entry
        self.hass = hass

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=entry.options[CONF_SCAN_INTERVAL]),
        )

    @property
    def _address(self) -> str:
        """Return the address of the heating system, for log messages."""
        return f"{self._entry.options[CONF_HOST]}:{self._entry.options[CONF_PORT]}"

    async def _async_update_data(self):
        """Update data via library."""

        if not self.api.is_connected and not await self.hass.async_add_executor_job(
            self.api.connect
        ):
            raise UpdateFailed(f"Cannot connect to {self._address}")

        failed = []
        for option, update in COMPONENT_UPDATES:
            if not self._entry.options[option]:
                continue
            if not await self.hass.async_add_executor_job(getattr(self.api, update)):
                failed.append(option)

        if failed:
            # Reporting a partial read as a success would leave the entities of the
            # component that failed on their last value without anything saying so.
            raise UpdateFailed(
                f"Failed to read {', '.join(failed)} from {self._address}"
            )

        _LOGGER.debug("Data updated successfully")
