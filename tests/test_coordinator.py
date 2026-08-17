"""Test the Solarfocus data update coordinator."""

from datetime import timedelta
import logging

import pytest

from custom_components.solarfocus.const import (
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
from custom_components.solarfocus.coordinator import SolarfocusDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import build_api, build_config_entry

# Config option -> the library call the coordinator has to make for it.
COMPONENT_UPDATES = [
    (CONF_HEATING_CIRCUIT, 1, "update_heating"),
    (CONF_BUFFER, 1, "update_buffer"),
    (CONF_BOILER, 1, "update_boiler"),
    (CONF_HEATPUMP, True, "update_heatpump"),
    (CONF_PHOTOVOLTAIC, True, "update_photovoltaic"),
    (CONF_BIOMASS_BOILER, True, "update_biomassboiler"),
    (CONF_SOLAR, 1, "update_solar"),
    (CONF_FRESH_WATER_MODULE, 1, "update_fresh_water_modules"),
]

ALL_UPDATES = [update for _, _, update in COMPONENT_UPDATES]


def _coordinator(hass: HomeAssistant, api, **options) -> SolarfocusDataUpdateCoordinator:
    """Create a coordinator for an entry with the given options."""
    entry = build_config_entry(**options)
    entry.add_to_hass(hass)
    return SolarfocusDataUpdateCoordinator(hass, entry, api)


@pytest.mark.parametrize(("option", "value", "update"), COMPONENT_UPDATES)
async def test_only_configured_components_are_polled(
    hass: HomeAssistant, option: str, value, update: str
) -> None:
    """A component that is not configured must not be read from the device."""
    api = build_api()
    coordinator = _coordinator(hass, api, **{option: value})

    await coordinator._async_update_data()

    assert getattr(api, update).called
    for other in ALL_UPDATES:
        if other != update:
            assert not getattr(api, other).called, f"{other} was polled unexpectedly"


async def test_no_configured_components_polls_nothing(hass: HomeAssistant) -> None:
    """An entry without components does not talk to the device at all."""
    api = build_api()
    coordinator = _coordinator(hass, api)

    await coordinator._async_update_data()

    for update in ALL_UPDATES:
        assert not getattr(api, update).called


async def test_all_components_are_polled(hass: HomeAssistant) -> None:
    """Every configured component is refreshed on a single update."""
    api = build_api()
    coordinator = _coordinator(
        hass, api, **{option: value for option, value, _ in COMPONENT_UPDATES}
    )

    await coordinator._async_update_data()

    for update in ALL_UPDATES:
        assert getattr(api, update).called


async def test_scan_interval_is_taken_from_the_options(hass: HomeAssistant) -> None:
    """The configured scan interval becomes the update interval."""
    coordinator = _coordinator(hass, build_api(), scan_interval=42)

    assert coordinator.update_interval == timedelta(seconds=42)


async def test_coordinator_keeps_the_entry(hass: HomeAssistant) -> None:
    """Entities read the options and the device name off the entry."""
    entry = build_config_entry()
    entry.add_to_hass(hass)

    coordinator = SolarfocusDataUpdateCoordinator(hass, entry, build_api())

    assert coordinator._entry is entry
    # The coordinator is named after the integration, the device name entities
    # use comes from `_entry.title`.
    assert coordinator.name == DOMAIN
    assert entry.title == "Solarfocus"


async def test_reconnects_before_updating(hass: HomeAssistant) -> None:
    """A dropped connection is re-established on the next refresh."""
    api = build_api()
    coordinator = _coordinator(hass, api, heating_circuit=1)

    api.connect.reset_mock()
    api.is_connected = False

    await coordinator._async_update_data()

    assert api.connect.called
    assert api.update_heating.called


async def test_does_not_reconnect_while_connected(hass: HomeAssistant) -> None:
    """A healthy connection is reused."""
    api = build_api()
    coordinator = _coordinator(hass, api, heating_circuit=1)

    api.connect.reset_mock()

    await coordinator._async_update_data()

    assert not api.connect.called


async def test_constructing_the_coordinator_does_not_talk_to_the_device(
    hass: HomeAssistant,
) -> None:
    """Connecting is blocking I/O and belongs in the refresh, not in __init__."""
    api = build_api()

    _coordinator(hass, api, heating_circuit=1)

    assert not api.connect.called


async def test_unreachable_device_fails_the_update(hass: HomeAssistant) -> None:
    """A refresh that cannot connect must not look like a successful one."""
    api = build_api()
    api.connect.return_value = False
    api.is_connected = False
    coordinator = _coordinator(hass, api, heating_circuit=1)

    with pytest.raises(UpdateFailed) as failure:
        await coordinator._async_update_data()

    assert failure.value.translation_key == "cannot_connect"
    assert failure.value.translation_placeholders == {"address": "solarfocus.local:502"}
    assert not api.update_heating.called


async def test_all_reads_failing_fails_the_refresh(hass: HomeAssistant) -> None:
    """Nothing could be read, so the system is gone.

    The library reports a failed read by returning False. Swallowing that left
    every entity of the entry available and showing its last value, with nothing
    telling the user that the values had stopped being updated.
    """
    api = build_api()
    api.update_heating.return_value = False
    api.update_buffer.return_value = False
    coordinator = _coordinator(hass, api, heating_circuit=1, buffer=1)

    with pytest.raises(UpdateFailed) as failure:
        await coordinator._async_update_data()

    assert failure.value.translation_key == "cannot_read"
    assert failure.value.translation_placeholders == {
        "address": "solarfocus.local:502",
        "components": f"{CONF_HEATING_CIRCUIT}, {CONF_BUFFER}",
    }


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
    api = build_api()
    api.update_heating.return_value = False
    coordinator = _coordinator(hass, api, heating_circuit=1, buffer=1)

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert api.update_buffer.called
    assert "Could not read heating_circuit" in caplog.text


async def test_a_partial_failure_is_logged_once_and_the_recovery_too(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Once per outage, not once per poll."""
    api = build_api()
    api.update_heating.return_value = False
    coordinator = _coordinator(hass, api, heating_circuit=1, buffer=1)

    await coordinator.async_refresh()
    await coordinator.async_refresh()
    await coordinator.async_refresh()

    assert caplog.text.count("Could not read heating_circuit") == 1

    caplog.clear()
    api.update_heating.return_value = True
    await coordinator.async_refresh()
    await coordinator.async_refresh()

    assert caplog.text.count("works again") == 1


async def test_entities_become_unavailable_and_recover(hass: HomeAssistant) -> None:
    """`last_update_success` is what the entities report as availability."""
    api = build_api()
    coordinator = _coordinator(hass, api, heating_circuit=1)

    await coordinator.async_refresh()
    assert coordinator.last_update_success

    api.update_heating.return_value = False
    await coordinator.async_refresh()
    assert not coordinator.last_update_success

    api.update_heating.return_value = True
    await coordinator.async_refresh()
    assert coordinator.last_update_success


async def test_a_failure_is_logged_once_and_the_recovery_too(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """An unreachable system must not fill the log on every poll.

    Raising `UpdateFailed` hands that to the coordinator, which logs the first
    failure and the recovery and keeps quiet in between.
    """
    api = build_api()
    coordinator = _coordinator(hass, api, heating_circuit=1)
    await coordinator.async_refresh()

    caplog.clear()
    api.update_heating.return_value = False
    await coordinator.async_refresh()
    await coordinator.async_refresh()
    await coordinator.async_refresh()

    assert caplog.text.count(f"Error fetching {DOMAIN} data") == 1

    caplog.clear()
    api.update_heating.return_value = True
    await coordinator.async_refresh()

    assert caplog.text.count(f"Fetching {DOMAIN} data recovered") == 1


async def test_successful_update_is_logged(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A successful refresh is reported."""
    api = build_api()
    coordinator = _coordinator(hass, api, heating_circuit=1)

    with caplog.at_level(logging.DEBUG):
        await coordinator._async_update_data()

    assert "Data updated successfully" in caplog.text
