"""Coordinator for Solarfocus integration."""

from collections.abc import Iterable, Mapping
from datetime import timedelta
import logging
from typing import override

from aiosolarfocus import (
    ComponentId,
    ComponentKey,
    SolarfocusClient,
    SolarfocusConnectionError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COMPONENT_DEVICES,
    COMPONENT_PREFIXES,
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
    SINGLE_COMPONENTS,
    component_instances,
)
from .service_menu import DisplayedNumber

_LOGGER = logging.getLogger(__name__)

# The entry option a component is configured under -> what the library calls
# that component. The option keys are what an entry has stored since long
# before this library, so they stay as they are and are translated here.
COMPONENT_IDS: Mapping[str, ComponentId] = {
    CONF_HEATING_CIRCUIT: ComponentId.HEATING_CIRCUITS,
    CONF_BUFFER: ComponentId.BUFFERS,
    CONF_BOILER: ComponentId.BOILERS,
    CONF_HEATPUMP: ComponentId.HEAT_PUMP,
    CONF_PHOTOVOLTAIC: ComponentId.PHOTOVOLTAIC,
    CONF_BIOMASS_BOILER: ComponentId.BIOMASS_BOILER,
    CONF_SOLAR: ComponentId.SOLAR,
    CONF_FRESH_WATER_MODULE: ComponentId.FRESH_WATER_MODULES,
    CONF_CIRCULATION: ComponentId.CIRCULATIONS,
    CONF_DIFFERENTIAL_MODULE: ComponentId.DIFFERENTIAL_MODULES,
}

# The other way round, for reading a failure back off an `UpdateResult`.
COMPONENT_OPTIONS: Mapping[ComponentId, str] = {
    component_id: option for option, component_id in COMPONENT_IDS.items()
}


def failed_instance(key: ComponentKey) -> tuple[str, str]:
    """Return the option and index an entity of this component instance carries.

    The library names a component instance by its id and a 1-based number; an
    entity description carries the entry option and `component_idx`, which is
    blank for the components a controller only has one of. Availability is
    matched on the pair, so this is where the two namings meet.
    """
    option = COMPONENT_OPTIONS[key.id]
    return (option, "" if option in SINGLE_COMPONENTS else str(key.number))


# Nothing is handed to the entities through the coordinator: an entity reads
# the component objects of the library directly, so a refresh has no data of
# its own to carry.
class SolarfocusDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Get the latest data and update the states."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: "SolarfocusConfigEntry",
        client: SolarfocusClient,
    ) -> None:
        """Init the Solarfocus data object."""

        self.client = client
        self._entry = entry
        self.hass = hass
        self._failed_components: frozenset[tuple[str, str]] = frozenset()
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
    def failed_components(self) -> frozenset[tuple[str, str]]:
        """Return the component instances that could not be read last refresh.

        A pair of the entry option and the index, because the library reports a
        failure per instance: one buffer that answers nothing is one buffer, and
        the other three carry on. See `failed_instance`.

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

        try:
            result = await self.client.update()
        except SolarfocusConnectionError as error:
            # The one failure that says nothing about any component: there is
            # no socket, so no component was asked anything. Whatever was
            # failing on its own before is forgotten rather than left behind to
            # be reported as still true - named in the diagnostics download, and
            # raised as an issue saying that every other component reads fine.
            # The outage itself is what the failed refresh says, and the issue
            # comes back on the first refresh that reads anything at all.
            self._failed_components = frozenset()
            self._report_failed_components([])
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"address": self._address},
            ) from error

        failed = sorted(failed_instance(key) for key in result.failed)

        if failed and len(failed) == len(self.client.components):
            # Nothing could be read: the system is gone rather than one of its
            # components being unhappy. Reporting that as a success would leave
            # every entity available and showing its last value.
            self._failed_components = frozenset()
            self._report_failed_components([])
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_read",
                translation_placeholders={
                    "address": self._address,
                    "components": ", ".join(_names(failed)),
                },
            )

        self._report_partial_failure(failed)

        _LOGGER.debug("Data updated successfully: %s", result)

    def _report_partial_failure(self, failed: list[tuple[str, str]]) -> None:
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
                ", ".join(_names(failed)),
                self._address,
            )
        else:
            _LOGGER.info("Reading all components of %s works again", self._address)

    def _report_failed_components(self, failed: list[tuple[str, str]]) -> None:
        """Raise a repair issue per component instance that cannot be read.

        A register range a particular firmware does not answer fails on every
        poll and never recovers on its own. The entities of that component are
        unavailable for as long as it lasts, which says nothing about why - and
        the log line that does is written once, so it has usually scrolled away
        by the time anybody looks.

        Nothing here can fix it: either the component is not installed and the
        user should switch it off in the options, or the api version is set
        higher than the controller runs.

        One issue per *instance* rather than per component: the library plans
        its reads across the whole system and attributes a refused range to the
        components whose registers were in it, so one buffer that answers
        nothing is one buffer, and the other three carry on with their entities
        available and their pages alive.

        Every instance is answered for, not only the ones that changed or are
        configured: switching a component off is what the issue asks the user to
        do, and that reloads the entry into a coordinator that knows nothing
        about the issues the one before it raised.
        """
        for option in COMPONENT_IDS:
            for instance in component_instances(option):
                issue_id = component_issue_id(self._entry.entry_id, *instance)
                if instance not in failed:
                    ir.async_delete_issue(self.hass, DOMAIN, issue_id)
                    continue

                device = self._component_device(*instance)
                # What the device page calls this component's model, for when
                # there is no device yet to ask - either it is not registered
                # yet, which is what the report at the end of
                # `async_setup_entry` catches up with, or the configured api
                # version does not have it at all. Either way this is never the
                # bare option: that is a config key, not a word, and leaks into
                # every language's text.
                fallback = _fallback_name(*instance)
                # What the device page calls this component, which is translated
                # and is whatever the user renamed it to, and the same name as a
                # link to that page.
                if device is None:
                    name, link = fallback, fallback
                else:
                    name = device.name_by_user or device.name or fallback
                    link = (
                        f"[{_escape_markdown_link_text(name)}]"
                        f"(/config/devices/device/{device.id})"
                    )

                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    issue_id,
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="component_unavailable",
                    translation_placeholders={
                        "component": name,
                        "devices": link,
                        "address": self._address,
                        "title": self._entry.title,
                    },
                )

    def _component_device(self, option: str, idx: str) -> dr.DeviceEntry | None:
        """Return the registered device of one component instance.

        A device is registered by the entities on it, which are built after the
        refresh `async_setup_entry` awaits - so on the first refresh of a new
        entry there is none yet, and the issue names what it can.
        """
        prefix = COMPONENT_PREFIXES[option]
        identifier = (DOMAIN, f"{self._entry.entry_id}_{prefix}{idx}")

        return dr.async_get(self.hass).async_get_device({identifier})

    @callback
    def async_report_failed_components(self) -> None:
        """Raise the issues of the components that are failing again.

        For `async_setup_entry` to call once the platforms are set up: an issue
        raised by the refresh before that names its devices by the option they
        are configured under, because nothing has registered them yet. Raising
        it again over the top is what puts the device names and their links in.
        """
        self._report_failed_components(sorted(self._failed_components))


def _fallback_name(option: str, idx: str) -> str:
    """Return what to call a component instance with no device to ask.

    The model the device page shows, with the index the device name would carry
    - `Buffer 2` rather than the bare `buffer`, which is a config key rather
    than a word and would leak English into every language's text.
    """
    model = COMPONENT_DEVICES[COMPONENT_PREFIXES[option]].model
    return f"{model} {idx}" if idx else model


def _names(failed: Iterable[tuple[str, str]]) -> list[str]:
    """Return what to call each failing instance in a log line or a message."""
    return [_fallback_name(*instance) for instance in failed]


def _escape_markdown_link_text(text: str) -> str:
    """Escape a device name for use as the text span of a markdown link.

    The name is whatever the user renamed the device to, so it can contain a
    `]` that would otherwise close the link's text span early and leave the
    rest of it as literal, unlinked text in the repair dialog.
    """
    return text.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def component_issue_id(entry_id: str, option: str, idx: str) -> str:
    """Return the issue id of one component instance of one entry.

    Per instance rather than one for all of them, so that a buffer coming back
    clears its own issue and leaves the others standing.
    """
    return f"component_unavailable_{entry_id}_{option}{idx}"


@callback
def async_delete_component_issues(
    hass: HomeAssistant, entry: "SolarfocusConfigEntry"
) -> None:
    """Delete every component issue an entry raised.

    An entry that is unloaded is not reading anything, and one that is removed
    is not there to be configured, so an issue naming it has nothing left to
    say. Neither is noticed by the issue registry on its own.
    """
    for option in COMPONENT_IDS:
        for instance in component_instances(option):
            ir.async_delete_issue(
                hass, DOMAIN, component_issue_id(entry.entry_id, *instance)
            )


# The coordinator of an entry lives on the entry itself, this spells that out
# for the platforms reading it back.
SolarfocusConfigEntry = ConfigEntry[SolarfocusDataUpdateCoordinator]
