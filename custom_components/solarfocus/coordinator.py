"""Coordinator for Solarfocus integration."""

from datetime import timedelta
import logging
from typing import override

from pysolarfocus import SolarfocusAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_BIOMASS_BOILER,
    CONF_BOILER,
    CONF_BUFFER,
    CONF_CIRCULATION,
    CONF_DIFFERENTIAL_MODULE,
    CONF_FRESH_WATER_MODULE,
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
    CONF_PHOTOVOLTAIC,
    CONF_SOLAR,
    DOMAIN,
)
from .service_menu import DisplayedNumber

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
    (CONF_CIRCULATION, "update_circulation"),
    (CONF_DIFFERENTIAL_MODULE, "update_differential_modules"),
)


# Nothing is handed to the entities through the coordinator: an entity reads
# the component objects of the library directly, so a refresh has no data of
# its own to carry.
class SolarfocusDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Get the latest data and update the states."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: "SolarfocusConfigEntry",
        api: SolarfocusAPI,
    ) -> None:
        """Init the Solarfocus data object."""

        self.api = api
        self._entry = entry
        self.hass = hass
        self._failed_components: frozenset[str] = frozenset()
        # The controller every component device of this entry hangs off, set by
        # `async_setup_entry` once the device is registered. A component device
        # points at it by id rather than by identifier, which Home Assistant
        # deprecates.
        self.hub_device_id: str | None = None
        # The number the installer menu of the controller shows: typed in on
        # one entity of it and multiplied by another. Not a register, so it
        # lives here, where both platforms can reach it.
        self.displayed_number = DisplayedNumber()

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=entry.options[CONF_SCAN_INTERVAL]),
        )

    @property
    def failed_components(self) -> frozenset[str]:
        """Return the components that could not be read on the last refresh.

        Every entity of the entry reads this on every state write, so it is
        handed out as it is rather than copied: a frozenset cannot be added to
        by the caller, which is what the copy was there for.
        """
        return self._failed_components

    @property
    def _address(self) -> str:
        """Return the address of the heating system, for log messages."""
        return f"{self._entry.data[CONF_HOST]}:{self._entry.data[CONF_PORT]}"

    @override
    async def _async_update_data(self) -> None:
        """Update data via library."""

        if not self.api.is_connected and not await self.hass.async_add_executor_job(
            self.api.connect
        ):
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"address": self._address},
            )

        configured = 0
        failed = []
        for option, update in COMPONENT_UPDATES:
            if not self._entry.options[option]:
                continue
            configured += 1
            if not await self.hass.async_add_executor_job(getattr(self.api, update)):
                failed.append(option)

        # A connection that drops part way through the poll fails every
        # component read after it, whatever those components would have
        # answered - the library returns False without asking the socket
        # anything. Calling that a component that does not answer would grey
        # out an arbitrary tail of the system and raise an issue per component
        # telling the user to switch it off, for what is one dropped
        # connection, re-established on the next refresh.
        connection_lost = bool(failed) and not self.api.is_connected

        if connection_lost or (failed and len(failed) == configured):
            # Nothing could be read: the system is gone rather than one of its
            # components being unhappy. Reporting that as a success would leave
            # every entity available and showing its last value.
            #
            # No component is failing on its own any more, so whatever was doing
            # that is forgotten here rather than left behind to be reported as
            # still true: named in the diagnostics download, and raised as an
            # issue saying that every other component reads fine. The outage
            # itself is what the failed refresh says, and the issue comes back
            # on the first refresh that reads anything at all.
            self._failed_components = frozenset()
            self._report_failed_components([])
            if connection_lost:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="cannot_connect",
                    translation_placeholders={"address": self._address},
                )
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_read",
                translation_placeholders={
                    "address": self._address,
                    "components": ", ".join(failed),
                },
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

        What the failing component itself does is read off `failed_components`
        by the entities on it, which go unavailable while the rest of the entry
        carries on.
        """
        self._report_failed_components(failed)

        if frozenset(failed) == self._failed_components:
            return

        self._failed_components = frozenset(failed)

        if failed:
            _LOGGER.warning(
                "Could not read %s from %s, its entities are unavailable."
                " The other components were read successfully",
                ", ".join(failed),
                self._address,
            )
        else:
            _LOGGER.info("Reading all components of %s works again", self._address)

    def _report_failed_components(self, failed: list[str]) -> None:
        """Raise a repair issue per component that cannot be read, one per entry.

        A register range a particular firmware does not answer fails on every
        poll and never recovers on its own. The entities of that component are
        unavailable for as long as it lasts, which says nothing about why - and
        the log line that does is written once, so it has usually scrolled away
        by the time anybody looks.

        Nothing here can fix it: either the component is not installed and the
        user should switch it off in the options, or the api version is set
        higher than the controller runs.

        Every component is answered for, not only the ones that changed or are
        configured: switching a component off is what the issue asks the user to
        do, and that reloads the entry into a coordinator that knows nothing
        about the issues the one before it raised.
        """
        for option, _ in COMPONENT_UPDATES:
            issue_id = component_issue_id(self._entry.entry_id, option)
            if option not in failed:
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)
                continue

            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="component_unavailable",
                translation_placeholders={
                    "component": option,
                    "address": self._address,
                    "title": self._entry.title,
                },
            )


def component_issue_id(entry_id: str, option: str) -> str:
    """Return the issue id of one component of one entry.

    Per component rather than one for all of them, so that a component coming
    back clears its own issue and leaves the others standing.
    """
    return f"component_unavailable_{entry_id}_{option}"


@callback
def async_delete_component_issues(
    hass: HomeAssistant, entry: "SolarfocusConfigEntry"
) -> None:
    """Delete every component issue an entry raised.

    An entry that is unloaded is not reading anything, and one that is removed
    is not there to be configured, so an issue naming it has nothing left to
    say. Neither is noticed by the issue registry on its own.
    """
    for option, _ in COMPONENT_UPDATES:
        ir.async_delete_issue(hass, DOMAIN, component_issue_id(entry.entry_id, option))


# The coordinator of an entry lives on the entry itself, this spells that out
# for the platforms reading it back.
SolarfocusConfigEntry = ConfigEntry[SolarfocusDataUpdateCoordinator]
