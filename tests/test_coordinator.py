"""Test the Solarfocus data update coordinator.

The library reports a failed refresh in two different ways, and the whole point
of this file is that the coordinator keeps them apart: a connection that is not
there raises, because that says nothing about any component, and everything
else - a range this firmware refuses, an exception response - is attributed to
the components whose registers were in that read.
"""

from datetime import timedelta
import logging

from aiosolarfocus import ApiVersion, ComponentId, SolarfocusConnectionError, Systems
import pytest

from custom_components.solarfocus.const import (
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
from custom_components.solarfocus.coordinator import SolarfocusDataUpdateCoordinator
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import build_client, build_config_entry, controller_of, revive, silence

# The api version that has every component of the table below - the circulation
# and the differential module arrived in it, and the entries the tests build
# are older than that by default.
EVERY_COMPONENT_VERSION = ApiVersion.V_25_030.label

# Config option -> what it is configured as, what the library calls it, and the
# system that has it. The heat source is the one part of the layout the system
# decides rather than the user, and the library refuses the combination the
# config flow has never offered: a Vampair has the heat pump, everything else
# has the biomass boiler.
COMPONENTS = [
    (CONF_HEATING_CIRCUIT, 1, ComponentId.HEATING_CIRCUITS, Systems.VAMPAIR),
    (CONF_BUFFER, 1, ComponentId.BUFFERS, Systems.VAMPAIR),
    (CONF_BOILER, 1, ComponentId.BOILERS, Systems.VAMPAIR),
    (CONF_HEATPUMP, True, ComponentId.HEAT_PUMP, Systems.VAMPAIR),
    (CONF_PHOTOVOLTAIC, True, ComponentId.PHOTOVOLTAIC, Systems.VAMPAIR),
    (CONF_BIOMASS_BOILER, True, ComponentId.BIOMASS_BOILER, Systems.THERMINATOR),
    (CONF_SOLAR, 1, ComponentId.SOLAR, Systems.VAMPAIR),
    (CONF_FRESH_WATER_MODULE, 1, ComponentId.FRESH_WATER_MODULES, Systems.VAMPAIR),
    (CONF_CIRCULATION, 1, ComponentId.CIRCULATIONS, Systems.VAMPAIR),
    (CONF_DIFFERENTIAL_MODULE, 1, ComponentId.DIFFERENTIAL_MODULES, Systems.VAMPAIR),
]

# Everything a vampair can have at once, which is everything but the heat
# source it does not have.
EVERY_VAMPAIR_COMPONENT = {
    option: value
    for option, value, _, _ in COMPONENTS
    if option != CONF_BIOMASS_BOILER
}


def _coordinator(
    hass: HomeAssistant, system: Systems = Systems.VAMPAIR, **options
) -> SolarfocusDataUpdateCoordinator:
    """Create a coordinator over a controller that is not real."""
    entry = build_config_entry(system, **options)
    entry.add_to_hass(hass)

    return SolarfocusDataUpdateCoordinator(hass, entry, build_client(entry))


@pytest.mark.parametrize(("option", "value", "component", "system"), COMPONENTS)
async def test_only_configured_components_are_polled(
    hass: HomeAssistant, option: str, value, component: ComponentId, system: Systems
) -> None:
    """A component that is not configured must not be read from the device."""
    coordinator = _coordinator(
        hass, system, api_version=EVERY_COMPONENT_VERSION, **{option: value}
    )

    await coordinator._async_update_data()

    assert set(coordinator.client.components) == {
        key for key in coordinator.client.components if key.id is component
    }
    assert coordinator.client.of(component)


async def test_no_configured_components_polls_nothing(hass: HomeAssistant) -> None:
    """An entry without components does not talk to the device at all."""
    coordinator = _coordinator(hass)

    await coordinator._async_update_data()

    assert not controller_of(coordinator.client).reads


async def test_all_components_are_polled(hass: HomeAssistant) -> None:
    """Every configured component is refreshed on a single update."""
    coordinator = _coordinator(
        hass, api_version=EVERY_COMPONENT_VERSION, **EVERY_VAMPAIR_COMPONENT
    )

    await coordinator._async_update_data()

    assert all(
        component.available for component in coordinator.client.components.values()
    )
    assert {key.id for key in coordinator.client.components} == {
        component
        for option, _, component, _ in COMPONENTS
        if option != CONF_BIOMASS_BOILER
    }


async def test_scan_interval_is_taken_from_the_options(hass: HomeAssistant) -> None:
    """The configured scan interval becomes the update interval."""
    coordinator = _coordinator(hass, scan_interval=42)

    assert coordinator.update_interval == timedelta(seconds=42)


async def test_coordinator_keeps_the_entry(hass: HomeAssistant) -> None:
    """Entities read the options and the device name off the entry."""
    entry = build_config_entry()
    entry.add_to_hass(hass)

    coordinator = SolarfocusDataUpdateCoordinator(hass, entry, build_client(entry))

    assert coordinator._entry is entry
    # The coordinator is named after the integration, the device name entities
    # use comes from `_entry.title`.
    assert coordinator.name == DOMAIN
    assert entry.title == "Solarfocus"


async def test_the_refresh_connects_on_its_own(hass: HomeAssistant) -> None:
    """A dropped connection is re-established on the next refresh.

    `update` opens the socket if it is not open, so there is no connection flag
    for the coordinator to check first - which is what it used to do, and what
    it then had to consult again afterwards to work out what a `False` meant.
    """
    coordinator = _coordinator(hass, heating_circuit=1)
    assert not coordinator.client.connected

    await coordinator._async_update_data()

    assert coordinator.client.connected


async def test_constructing_the_coordinator_does_not_talk_to_the_device(
    hass: HomeAssistant,
) -> None:
    """Connecting is I/O and belongs in the refresh, not in __init__."""
    coordinator = _coordinator(hass, heating_circuit=1)

    assert not coordinator.client.connected
    assert not controller_of(coordinator.client).reads


async def test_unreachable_device_fails_the_update(hass: HomeAssistant) -> None:
    """A refresh that cannot connect must not look like a successful one."""
    coordinator = _coordinator(hass, heating_circuit=1)
    controller_of(coordinator.client).fail_with = SolarfocusConnectionError("gone")

    with pytest.raises(UpdateFailed) as failure:
        await coordinator._async_update_data()

    assert failure.value.translation_key == "cannot_connect"
    assert failure.value.translation_placeholders == {"address": "solarfocus.local:502"}


async def test_all_reads_failing_fails_the_refresh(hass: HomeAssistant) -> None:
    """Nothing could be read, so the system is gone.

    Swallowing that left every entity of the entry available and showing its
    last value, with nothing telling the user the values had stopped moving.
    """
    coordinator = _coordinator(hass, heating_circuit=1, buffer=1)
    silence(coordinator.client, ComponentId.HEATING_CIRCUITS)
    silence(coordinator.client, ComponentId.BUFFERS)

    with pytest.raises(UpdateFailed) as failure:
        await coordinator._async_update_data()

    assert failure.value.translation_key == "cannot_read"
    assert failure.value.translation_placeholders == {
        "address": "solarfocus.local:502",
        # What the device page calls them, index and all, rather than the
        # config keys - this text is shown to the user.
        "components": "Buffer 1, Heating circuit 1",
    }


@pytest.mark.parametrize("option", [CONF_CIRCULATION, CONF_DIFFERENTIAL_MODULE])
async def test_a_component_the_api_version_lacks_is_not_built(
    hass: HomeAssistant, option: str
) -> None:
    """A component that arrived in a later api version is not there below it.

    It used to be built and polled by a library call that returned success
    without asking the controller anything, so it was a read that could not
    fail - which is why the coordinator had to count configured components
    rather than trusting the answer.
    """
    coordinator = _coordinator(hass, **{option: 2})

    await coordinator._async_update_data()

    assert not coordinator.client.components


@pytest.mark.parametrize("option", [CONF_CIRCULATION, CONF_DIFFERENTIAL_MODULE])
async def test_a_component_the_api_version_lacks_does_not_hide_an_outage(
    hass: HomeAssistant, option: str
) -> None:
    """Nothing is read, so the refresh fails - whatever else is configured."""
    coordinator = _coordinator(hass, heating_circuit=1, **{option: 2})
    silence(coordinator.client, ComponentId.HEATING_CIRCUITS)

    with pytest.raises(UpdateFailed) as failure:
        await coordinator._async_update_data()

    assert failure.value.translation_key == "cannot_read"
    assert (
        failure.value.translation_placeholders["components"] == "Heating circuit 1"
    )


async def test_one_failing_component_keeps_the_others_working(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A single component that cannot be read must not take the entry down.

    A register range a particular firmware does not answer fails on every poll.
    Failing the refresh for it would make every entity of the entry unavailable
    for good, including the ones that can be written - and Home Assistant drops
    unavailable entities from service calls, so the user could not control the
    parts that do work.
    """
    coordinator = _coordinator(hass, heating_circuit=1, buffer=1)
    silence(coordinator.client, ComponentId.HEATING_CIRCUITS)

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.client.buffers[0].available
    assert "Could not read Heating circuit 1" in caplog.text


async def test_one_failing_instance_leaves_the_others_alone(
    hass: HomeAssistant,
) -> None:
    """Two buffers, one of which answers nothing.

    The predecessor read all four buffers in one call and stopped at the first
    that failed, so a buffer that answered nothing was every buffer as far as
    anything here could tell. The library reads them as slices of the whole
    system and attributes a refusal to the instances it was actually for.
    """
    coordinator = _coordinator(hass, buffer=2)
    silence(coordinator.client, ComponentId.BUFFERS, index=2)

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.failed_components == frozenset({(CONF_BUFFER, "2")})
    assert coordinator.client.buffers[0].available
    assert not coordinator.client.buffers[1].available


async def test_a_connection_dropping_mid_poll_is_an_outage(
    hass: HomeAssistant,
) -> None:
    """A socket that goes away is not a component to be configured away.

    Calling it one would grey out whatever the drop happened to land on and
    raise an issue telling the user to switch that component off, for a
    connection that is re-established on the next refresh.
    """
    coordinator = _coordinator(hass, heating_circuit=1, boiler=1, heatpump=True)
    controller_of(coordinator.client).fail_with = SolarfocusConnectionError("dropped")

    with pytest.raises(UpdateFailed) as failure:
        await coordinator._async_update_data()

    assert failure.value.translation_key == "cannot_connect"
    assert coordinator.failed_components == frozenset()


async def test_a_connection_dropping_mid_poll_raises_no_component_issue(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """End to end: an outage is not a component to be configured away."""
    entry = build_config_entry(heating_circuit=1, boiler=1)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_client.controller.fail_with = SolarfocusConnectionError("dropped")
    await entry.runtime_data.async_refresh()

    assert not entry.runtime_data.last_update_success
    assert not ir.async_get(hass).issues


async def test_a_failing_component_on_a_live_connection_is_still_partial(
    hass: HomeAssistant,
) -> None:
    """The guard is about the connection, not about a read that was refused."""
    coordinator = _coordinator(hass, heating_circuit=1, boiler=1)
    silence(coordinator.client, ComponentId.BOILERS)

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.failed_components == frozenset({(CONF_BOILER, "1")})


async def test_failed_components_is_handed_out_rather_than_copied(
    hass: HomeAssistant,
) -> None:
    """Every entity of the entry reads this on every state write.

    A copy per read is hundreds of throwaway sets per poll for a set of at most
    eight names. A frozenset cannot be added to by whoever reads it, which is
    what the copy was there for.
    """
    coordinator = _coordinator(hass, heating_circuit=1, boiler=1)
    silence(coordinator.client, ComponentId.BOILERS)

    await coordinator.async_refresh()

    assert isinstance(coordinator.failed_components, frozenset)
    assert coordinator.failed_components is coordinator.failed_components


async def test_only_the_failing_component_is_greyed_out(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """End to end: the heating circuit answers nothing, the boiler answers.

    The refresh succeeds, so the entry keeps polling and every entity of the
    boiler carries its value as usual. The entities of the heating circuit go
    unavailable rather than keeping the last value they read, which they used to
    do for as long as the entry was loaded.
    """
    entry = build_config_entry(heating_circuit=1, boiler=1)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_client.silence(ComponentId.HEATING_CIRCUITS)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    def states(device: str) -> list[str]:
        return [
            hass.states.get(entity_id).state
            for entity_id in hass.states.async_entity_ids()
            if entity_id.split(".", 1)[1].startswith(device)
        ]

    heating_circuit = states("heating_circuit_1_")
    boiler = states("boiler_1_")

    assert heating_circuit and boiler, "the entities of both components are there"
    assert set(heating_circuit) == {STATE_UNAVAILABLE}
    assert STATE_UNAVAILABLE not in boiler


async def test_a_partial_failure_is_logged_once_and_the_recovery_too(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Once per outage, not once per poll."""
    coordinator = _coordinator(hass, heating_circuit=1, buffer=1)
    silence(coordinator.client, ComponentId.HEATING_CIRCUITS)

    await coordinator.async_refresh()
    await coordinator.async_refresh()
    await coordinator.async_refresh()

    assert caplog.text.count("Could not read Heating circuit 1") == 1

    caplog.clear()
    revive(coordinator.client, ComponentId.HEATING_CIRCUITS)
    await coordinator.async_refresh()
    await coordinator.async_refresh()

    assert caplog.text.count("works again") == 1


async def test_entities_become_unavailable_and_recover(hass: HomeAssistant) -> None:
    """`last_update_success` is what the entities report as availability."""
    coordinator = _coordinator(hass, heating_circuit=1)

    await coordinator.async_refresh()
    assert coordinator.last_update_success

    silence(coordinator.client, ComponentId.HEATING_CIRCUITS)
    await coordinator.async_refresh()
    assert not coordinator.last_update_success

    revive(coordinator.client, ComponentId.HEATING_CIRCUITS)
    await coordinator.async_refresh()
    assert coordinator.last_update_success


async def test_a_failure_is_logged_once_and_the_recovery_too(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """An unreachable system must not fill the log on every poll.

    Raising `UpdateFailed` hands that to the coordinator, which logs the first
    failure and the recovery and keeps quiet in between.
    """
    coordinator = _coordinator(hass, heating_circuit=1)
    await coordinator.async_refresh()

    caplog.clear()
    silence(coordinator.client, ComponentId.HEATING_CIRCUITS)
    await coordinator.async_refresh()
    await coordinator.async_refresh()
    await coordinator.async_refresh()

    assert caplog.text.count(f"Error fetching {DOMAIN} data") == 1

    caplog.clear()
    revive(coordinator.client, ComponentId.HEATING_CIRCUITS)
    await coordinator.async_refresh()

    assert caplog.text.count(f"Fetching {DOMAIN} data recovered") == 1


async def test_successful_update_is_logged(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A successful refresh is reported, with what it took to make it."""
    coordinator = _coordinator(hass, heating_circuit=1)

    with caplog.at_level(logging.DEBUG):
        await coordinator._async_update_data()

    assert "Data updated successfully" in caplog.text
