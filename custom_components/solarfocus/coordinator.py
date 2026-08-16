"""Coordinator for Solarfocus integration."""

from datetime import timedelta
import logging

from pysolarfocus import SolarfocusAPI

from homeassistant.config_entries import ConfigEntry
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
        self._failed_components: set[str] = set()

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=entry.options[CONF_SCAN_INTERVAL]),
        )

    @property
    def failed_components(self) -> set[str]:
        """Return the components that could not be read on the last refresh."""
        return set(self._failed_components)

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

        configured = 0
        failed = []
        for option, update in COMPONENT_UPDATES:
            if not self._entry.options[option]:
                continue
            configured += 1
            if not await self.hass.async_add_executor_job(getattr(self.api, update)):
                failed.append(option)

        if failed and len(failed) == configured:
            # Nothing could be read: the system is gone rather than one of its
            # components being unhappy. Reporting that as a success would leave
            # every entity available and showing its last value.
            raise UpdateFailed(
                f"Failed to read {', '.join(failed)} from {self._address}"
            )

        self._report_partial_failure(failed)

        _LOGGER.debug("Data updated successfully")

    def _report_partial_failure(self, failed: list[str]) -> None:
        """Log components that could not be read while others could.

        Taking the whole entry down for this would be worse than it sounds: a
        register range that a particular firmware does not answer fails on every
        poll, and the components that do work - including the ones that can be
        written - would go with it. So the rest keeps updating and the failure
        is logged instead, once, until the set of failing components changes.
        """
        if set(failed) == self._failed_components:
            return

        self._failed_components = set(failed)
        if failed:
            _LOGGER.warning(
                "Could not read %s from %s, its entities keep their last value."
                " The other components were read successfully",
                ", ".join(failed),
                self._address,
            )
        else:
            _LOGGER.info("Reading all components of %s works again", self._address)


# The coordinator of an entry lives on the entry itself, this spells that out
# for the platforms reading it back.
SolarfocusConfigEntry = ConfigEntry[SolarfocusDataUpdateCoordinator]
