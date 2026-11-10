"""Diagnostics for the Solarfocus integration.

What a report about this integration needs is the two things a log line does not
carry: how the entry is configured, and what the heating system last answered
with. Almost every issue so far has been a register reading something other than
what the specification says, on a firmware and a component layout that have to be
asked for one message at a time.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from aiosolarfocus import (
    SolarfocusClient,
    SolarfocusError,
    __version__ as aiosolarfocus_version,
)

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import SolarfocusConfigEntry

# The address of the controller is on the user's own network and says little on
# its own, but a diagnostics download is something people paste into an issue.
TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SolarfocusConfigEntry
) -> dict[str, Any]:
    """Return what the entry is configured as and what it last read."""
    coordinator = entry.runtime_data

    return {
        # The manifest pins one version, but a report is written from what is
        # installed rather than from what is pinned - fklein1980 ran a stale
        # aiosolarfocus against a controller and could not tell from its output
        # (#237), which is the same trap a diagnostics download falls into.
        "aiosolarfocus": aiosolarfocus_version,
        "entry": {
            "version": entry.version,
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            # Empty unless a component instance fails on its own while the
            # others read fine, which is what an unsupported register range
            # looks like. Rendered as the library names the instance, so a
            # report here and a `python -m aiosolarfocus dump` line up.
            "failed_components": [
                f"{option}.{idx}" if idx else option
                for option, idx in sorted(coordinator.failed_components)
            ],
        },
        # Keyed "heating_circuits.1", and richer than what this used to reach
        # into the library for: the address each value came from, the raw words
        # before scaling, and the unit. A sentinel reading has a raw value and
        # no decoded one, which is how a reader tells "no sensor fitted" from
        # "never read".
        "components": coordinator.client.snapshot(),
        # What the controller says it is, asked now, next to what the entry
        # says it is above. Most reports so far have come down to the two
        # disagreeing - a system or a version chosen wrong, a component counted
        # that is not there - and were settled by asking for exactly this, one
        # message at a time.
        "detection": await _async_detect(coordinator.client),
    }


async def _async_detect(client: SolarfocusClient) -> dict[str, Any]:
    """Return what the controller reads as, or why it could not be asked.

    Ninety-odd reads over the connection the coordinator already has, which is
    a few seconds: fine for a download somebody asked for, and a controller
    that will not answer them is no reason to withhold the rest of it.
    """
    try:
        detection = await client.detect()
    except SolarfocusError as error:
        return {"error": str(error)}

    return {
        "system": detection.system.value,
        "api_version": detection.api_version.label,
        "confident": detection.confident,
        "counts": asdict(detection.counts),
        "heat_pump": detection.has_heat_pump,
        "biomass_boiler": detection.has_biomass_boiler,
        "photovoltaic": detection.has_photovoltaic,
        "fresh_water_module_cascade": detection.has_fresh_water_module_cascade,
        "circulation_module": detection.has_circulation_module,
        # Counted, and not something this system is supposed to have.
        "unsupported": {
            component.value: count
            for component, count in detection.unsupported().items()
        },
        # The readings each of those was decided on.
        "evidence": dict(detection.evidence),
        "reads": detection.reads,
    }
