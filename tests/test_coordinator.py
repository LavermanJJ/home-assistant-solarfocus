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


async def test_initial_connection_failure_is_logged(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Constructing the coordinator against an unreachable device does not raise."""
    api = build_api()
    api.connect.return_value = False

    _coordinator(hass, api, heating_circuit=1)

    assert "Failed to connect to modbus" in caplog.text


async def test_failing_component_update_is_logged(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A component that fails to update is reported."""
    api = build_api()
    api.update_heating.return_value = False
    coordinator = _coordinator(hass, api, heating_circuit=1)

    with caplog.at_level(logging.DEBUG):
        await coordinator._async_update_data()

    assert "Data updated failed" in caplog.text


async def test_successful_update_is_logged(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A successful refresh is reported."""
    api = build_api()
    coordinator = _coordinator(hass, api, heating_circuit=1)

    with caplog.at_level(logging.DEBUG):
        await coordinator._async_update_data()

    assert "Data updated successfully" in caplog.text
