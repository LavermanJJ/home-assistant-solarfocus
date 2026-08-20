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

The same goes for the registers under a component. An entity reads its value by
`getattr`-ing its key off the pysolarfocus component, so a description whose key
the library does not carry for that system raises an `AttributeError` on the
first read - which is why register 2410 could not simply be renamed here and
needed the library to name it first (issue #223).
"""

from packaging import version
from pysolarfocus import ApiVersions, SolarfocusAPI, Systems
import pytest

from custom_components.solarfocus.binary_sensor import (
    BIOMASS_BOILER_BINARY_SENSOR_TYPES,
)
from custom_components.solarfocus.config_flow import SOLARFOCUS_SYSTEMS
from custom_components.solarfocus.const import CONF_BIOMASS_BOILER, CONF_HEATPUMP
from custom_components.solarfocus.coordinator import COMPONENT_UPDATES
from custom_components.solarfocus.sensor import BIOMASS_BOILER_SENSOR_TYPES

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


# Every description of the biomass boiler, whichever platform reports it.
BIOMASS_BOILER_DESCRIPTIONS = [
    *BIOMASS_BOILER_SENSOR_TYPES,
    *BIOMASS_BOILER_BINARY_SENSOR_TYPES,
]


def _reaches(system: Systems, description) -> bool:
    """Return whether a description survives the system and version filter."""
    return system not in (
        description.unsupported_systems or []
    ) and version.parse(description.min_required_version) <= version.parse(
        LATEST_API_VERSION.value
    )


@pytest.mark.parametrize("system", OFFERED_SYSTEMS, ids=lambda s: s.name)
def test_every_biomass_boiler_entity_has_a_register_behind_it(
    system: Systems,
) -> None:
    """A description the library has no attribute for cannot be read at all.

    `_get_native_value` does `getattr(component, key).scaled_value`, so the
    entity is built, added, and raises on the first refresh. Nothing else in
    this suite notices: the platform tests build their components from mocks,
    which answer to any name.
    """
    if _heat_source_of(system) != CONF_BIOMASS_BOILER:
        pytest.skip(f"{system.name} has no biomass boiler")

    boiler = SolarfocusAPI(
        ip="127.0.0.1", system=system, api_version=LATEST_API_VERSION
    ).biomassboiler

    missing = [
        description.key
        for description in BIOMASS_BOILER_DESCRIPTIONS
        if _reaches(system, description) and not hasattr(boiler, description.key)
    ]

    assert not missing, (
        f"{system.name} would build {sorted(missing)} on its biomass boiler, "
        f"but pysolarfocus carries no such register for that system."
    )


# The two names register 2410 is read under, and the systems the register
# document grants each to. The octoplus reads the bottom of its buffer there,
# the EcoTop and the Pellet Elegance read the return flow of the boiler, and on
# a therminator the address is nicht belegt.
REGISTER_2410 = {
    "octoplus_buffer_temperature_bottom": [Systems.OCTOPLUS],
    "return_temperature": [Systems.ECOTOP, Systems.PELLETELEGANCE],
}


@pytest.mark.parametrize("system", OFFERED_SYSTEMS, ids=lambda s: s.name)
def test_register_2410_is_reported_under_one_name_per_system(
    system: Systems,
) -> None:
    """Regression test for #223.

    Two measurements share address 2410, so exactly one of the two names may
    reach a system - and it has to be the one the library reads there. Reading
    it as the buffer bottom everywhere gave an EcoTop and a Pellet Elegance
    their return flow temperature under a name that says "buffer"; gating that
    to the octoplus without adding this one took the reading away instead of
    correcting it.
    """
    described = {
        description.key: description
        for description in BIOMASS_BOILER_SENSOR_TYPES
        if description.key in REGISTER_2410
    }
    assert sorted(described) == sorted(REGISTER_2410), (
        f"the biomass boiler describes {sorted(described)} for register 2410, "
        f"and both of {sorted(REGISTER_2410)} have to be there."
    )

    reached = [key for key in REGISTER_2410 if _reaches(system, described[key])]
    expected = [
        key for key, systems in REGISTER_2410.items() if system in systems
    ]

    assert reached == expected

    if _heat_source_of(system) == CONF_BIOMASS_BOILER:
        boiler = SolarfocusAPI(
            ip="127.0.0.1", system=system, api_version=LATEST_API_VERSION
        ).biomassboiler
        assert [key for key in REGISTER_2410 if hasattr(boiler, key)] == expected
