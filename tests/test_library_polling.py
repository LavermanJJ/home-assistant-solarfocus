"""Check what the integration offers against what pysolarfocus actually reads.

An entity is only as good as the poll behind it, and the library's `update_*`
methods return True both when they read a component and when they decided the
system has none to read. A component the library quietly skips therefore
produces entities that sit at their default value forever and a refresh that
reports success: no exception, no unavailable entity, no repair issue, and
nothing in the rest of this suite notices.

That is what happened when Pellet Elegance and Octoplus were first added to the
dropdown - `update_biomassboiler` named THERMINATOR and ECOTOP, so both new
systems showed a boiler at 0.0 degrees and called it fine. These tests tie the
dropdown to the library, so offering a system the library does not poll fails
here instead of in somebody's dashboard.
"""

import pytest
from pysolarfocus import ApiVersions, SolarfocusAPI, Systems

from custom_components.solarfocus.config_flow import SOLARFOCUS_SYSTEMS
from custom_components.solarfocus.const import CONF_BIOMASS_BOILER, CONF_HEATPUMP
from custom_components.solarfocus.coordinator import COMPONENT_UPDATES

# The systems a user can actually pick, read off the dropdown itself so that
# adding one to the form brings it under these tests with it.
OFFERED_SYSTEMS = [Systems(option["value"]) for option in SOLARFOCUS_SYSTEMS]

# The heat source the config flow switches on for a system, and the attribute on
# the API that the matching `update_*` call is supposed to read.
HEAT_SOURCE_COMPONENTS = {
    CONF_HEATPUMP: "heatpump",
    CONF_BIOMASS_BOILER: "biomassboiler",
}

LATEST_API_VERSION = list(ApiVersions)[-1]


def _heat_source_of(system: Systems) -> str:
    """Return the component flag `async_step_component` enables for a system."""
    return CONF_HEATPUMP if system == Systems.VAMPAIR else CONF_BIOMASS_BOILER


def _update_method(flag: str) -> str:
    """Return the API method the coordinator calls for a component flag."""
    return next(method for conf, method in COMPONENT_UPDATES if conf == flag)


@pytest.mark.parametrize("system", OFFERED_SYSTEMS, ids=lambda s: s.name)
def test_the_heat_source_of_every_offered_system_is_read(
    system: Systems, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Whichever heat source a system is set up with has to actually be polled."""
    api = SolarfocusAPI(
        ip="127.0.0.1", system=system, api_version=LATEST_API_VERSION
    )
    flag = _heat_source_of(system)
    component = getattr(api, HEAT_SOURCE_COMPONENTS[flag])

    reads: list[str] = []
    monkeypatch.setattr(
        type(component), "update", lambda self: reads.append(system.name) or True
    )

    assert getattr(api, _update_method(flag))() is True
    assert reads, (
        f"{system.name} is offered in the dropdown and set up with "
        f"{flag}, but pysolarfocus never reads its {HEAT_SOURCE_COMPONENTS[flag]}. "
        f"Every entity on it would sit at its default value and the refresh "
        f"would still report success."
    )


@pytest.mark.parametrize("system", OFFERED_SYSTEMS, ids=lambda s: s.name)
def test_the_heat_source_a_system_does_not_have_is_skipped(
    system: Systems, monkeypatch: pytest.MonkeyPatch
) -> None:
    """And the other one is left alone, rather than read and reported as real."""
    api = SolarfocusAPI(
        ip="127.0.0.1", system=system, api_version=LATEST_API_VERSION
    )
    absent = (
        CONF_BIOMASS_BOILER
        if _heat_source_of(system) == CONF_HEATPUMP
        else CONF_HEATPUMP
    )
    component = getattr(api, HEAT_SOURCE_COMPONENTS[absent])

    reads: list[str] = []
    monkeypatch.setattr(
        type(component), "update", lambda self: reads.append(system.name) or True
    )

    assert getattr(api, _update_method(absent))() is True
    assert not reads, (
        f"{system.name} has no {HEAT_SOURCE_COMPONENTS[absent]}, but pysolarfocus "
        f"reads one for it."
    )
