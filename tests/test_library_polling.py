"""Check what the integration offers against what the library actually reads.

An entity is only as good as the poll behind it. The predecessor's `update_*`
methods returned True both when they read a component and when they decided the
system had none to read, so a component the library quietly skipped produced
entities that sat at their default value forever and a refresh that reported
success: no exception, no unavailable entity, no repair issue, and nothing in
the rest of this suite noticed.

That is what happened when Pellet Elegance and Octoplus were first added to the
dropdown - `update_biomassboiler` named THERMINATOR and ECOTOP, so both new
systems showed a boiler at 0.0 degrees and called it fine.

`aiosolarfocus` closes that hole by construction: a component the system does
not have is not built, and a read that fails is attributed rather than
swallowed. These tests hold the dropdown to it anyway, because the failure they
guard against is silent and the cost of asking is one client per system.
"""

from aiosolarfocus import ApiVersion, ComponentId, Systems
import pytest

from custom_components.solarfocus.binary_sensor import (
    BIOMASS_BOILER_BINARY_SENSOR_TYPES,
)
from custom_components.solarfocus.config_flow import SOLARFOCUS_SYSTEMS
from custom_components.solarfocus.const import CONF_BIOMASS_BOILER, CONF_HEATPUMP
from custom_components.solarfocus.coordinator import COMPONENT_IDS
from custom_components.solarfocus.sensor import BIOMASS_BOILER_SENSOR_TYPES

from .conftest import build_client, build_config_entry, controller_of

# The systems a user can actually pick, read off the dropdown itself so that
# adding one to the form brings it under these tests with it.
OFFERED_SYSTEMS = [Systems(option["value"]) for option in SOLARFOCUS_SYSTEMS]

LATEST_API_VERSION = list(ApiVersion)[-1]


def _heat_source_of(system: Systems) -> str:
    """Return the component flag `async_step_component` enables for a system."""
    return CONF_HEATPUMP if system == Systems.VAMPAIR else CONF_BIOMASS_BOILER


def _client(system: Systems, **options):
    """Return a client for a system, on the newest firmware the library knows."""
    entry = build_config_entry(
        system, api_version=LATEST_API_VERSION.label, **options
    )

    return build_client(entry)


@pytest.mark.parametrize("system", OFFERED_SYSTEMS, ids=lambda s: s.name)
async def test_the_heat_source_of_every_offered_system_is_read(
    system: Systems,
) -> None:
    """Whichever heat source a system is set up with has to actually be polled."""
    flag = _heat_source_of(system)
    component_id = COMPONENT_IDS[flag]
    client = _client(system, **{flag: True})

    result = await client.update()

    assert client.of(component_id), (
        f"{system.name} is offered in the dropdown and set up with {flag}, "
        f"but the library builds no {component_id.value} for it. Every entity "
        f"on it would sit at its default value."
    )
    assert controller_of(client).reads, f"{system.name} read nothing at all"
    assert result.ok


@pytest.mark.parametrize("system", OFFERED_SYSTEMS, ids=lambda s: s.name)
def test_the_heat_source_a_system_does_not_have_is_refused(
    system: Systems,
) -> None:
    """And the other one is refused outright rather than built and read.

    The predecessor built it and read nothing into it. The library will not
    take the configuration at all, which is the difference between a boiler
    reporting 0.0 degrees and an entry that says why it cannot be set up.
    """
    absent = (
        CONF_BIOMASS_BOILER
        if _heat_source_of(system) == CONF_HEATPUMP
        else CONF_HEATPUMP
    )

    with pytest.raises(Exception, match="has no"):
        _client(system, **{absent: True})


# Every description of the biomass boiler, whichever platform reports it.
BIOMASS_BOILER_DESCRIPTIONS = [
    *BIOMASS_BOILER_SENSOR_TYPES,
    *BIOMASS_BOILER_BINARY_SENSOR_TYPES,
]


@pytest.mark.parametrize("system", OFFERED_SYSTEMS, ids=lambda s: s.name)
def test_every_biomass_boiler_entity_has_a_register_behind_it(
    system: Systems,
) -> None:
    """A description the library has no value for cannot be read at all.

    The entities are built from `supports` now, so this is less a guard against
    a broken entity than a check that every description this integration
    carries still names something - a description the library has never heard
    of would simply never be built, and would sit here unnoticed instead.
    """
    if _heat_source_of(system) != CONF_BIOMASS_BOILER:
        pytest.skip(f"{system.name} has no biomass boiler")

    boiler = _client(system, biomassboiler=True).of(ComponentId.BIOMASS_BOILER)[0]
    available = set(boiler.available_values())

    unknown = [
        description.key
        for description in BIOMASS_BOILER_DESCRIPTIONS
        if (description.item or description.key) not in available
    ]

    # Only what no system has: a register the document grants to one system is
    # legitimately absent on the others, and the entity is not built there.
    everything = set()
    for other in OFFERED_SYSTEMS:
        if _heat_source_of(other) != CONF_BIOMASS_BOILER:
            continue
        everything |= set(
            _client(other, biomassboiler=True)
            .of(ComponentId.BIOMASS_BOILER)[0]
            .available_values()
        )

    orphaned = [key for key in unknown if key not in everything]

    assert not orphaned, (
        f"the biomass boiler describes {sorted(orphaned)}, which the library "
        f"carries no value of that name for on any system."
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

    if _heat_source_of(system) != CONF_BIOMASS_BOILER:
        pytest.skip(f"{system.name} has no biomass boiler")

    boiler = _client(system, biomassboiler=True).of(ComponentId.BIOMASS_BOILER)[0]
    expected = [key for key, systems in REGISTER_2410.items() if system in systems]

    assert [key for key in REGISTER_2410 if boiler.supports(key)] == expected
