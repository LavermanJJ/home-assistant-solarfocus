"""Diagnostics for the Solarfocus integration.

What a report about this integration needs is the two things a log line does not
carry: how the entry is configured, and what the heating system last answered
with. Almost every issue so far has been a register reading something other than
what the specification says, on a firmware and a component layout that have to be
asked for one message at a time.
"""

from __future__ import annotations

from typing import Any

from pysolarfocus.components.base.part import Part

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import (
    BIOMASS_BOILER_COMPONENT,
    BOILER_COMPONENT,
    BUFFER_COMPONENT,
    FRESH_WATER_MODULE_COMPONENT,
    HEAT_PUMP_COMPONENT,
    HEATING_CIRCUIT_COMPONENT,
    PHOTOVOLTAIC_COMPONENT,
    SOLAR_COMPONENT,
)
from .coordinator import SolarfocusConfigEntry

# The components pysolarfocus builds, in the order the coordinator reads them.
COMPONENTS: tuple[str, ...] = (
    HEATING_CIRCUIT_COMPONENT,
    BUFFER_COMPONENT,
    BOILER_COMPONENT,
    HEAT_PUMP_COMPONENT,
    PHOTOVOLTAIC_COMPONENT,
    BIOMASS_BOILER_COMPONENT,
    SOLAR_COMPONENT,
    FRESH_WATER_MODULE_COMPONENT,
)

# The address of the controller is on the user's own network and says little on
# its own, but a diagnostics download is something people paste into an issue.
TO_REDACT = {CONF_HOST}


def _registers(component: Any) -> dict[str, Any]:
    """Return every register of one component, the way the entities read it.

    `Part` is what pysolarfocus gives a component for each of its registers, and
    for the two values it calculates rather than reads, so this is exactly the
    set of values an entity of that component can show.
    """
    return {
        name: part.scaled_value
        for name, part in vars(component).items()
        if isinstance(part, Part)
    }


def _component_registers(component: Any) -> Any:
    """Return the registers of a component, or of each of them if it is a list.

    A heating circuit, buffer, boiler, solar circuit and fresh water module can
    exist several times over; the heat pump, photovoltaic and biomass boiler are
    either there once or not at all.
    """
    if isinstance(component, list):
        return [_registers(one) for one in component]

    return None if component is None else _registers(component)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SolarfocusConfigEntry
) -> dict[str, Any]:
    """Return what the entry is configured as and what it last read."""
    coordinator = entry.runtime_data

    return {
        "entry": {
            "version": entry.version,
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            # Empty unless a component fails on its own while the others read
            # fine, which is what an unsupported register range looks like.
            "failed_components": sorted(coordinator.failed_components),
        },
        "components": {
            name: _component_registers(getattr(coordinator.api, name, None))
            for name in COMPONENTS
        },
    }
