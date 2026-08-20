"""Fixtures for the Solarfocus tests."""

from unittest.mock import MagicMock, patch

from pysolarfocus import ApiVersions, Systems
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

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
    CONF_SOLARFOCUS_SYSTEM,
    DEFAULT_NAME,
    DOMAIN,
    build_unique_id,
)
from custom_components.solarfocus.service_menu import DisplayedNumber
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
)

# The config entry version the integration currently migrates to.
CURRENT_VERSION = 11


def build_data(system: Systems = Systems.VAMPAIR) -> dict:
    """Return the entry data: what it takes to read the heating system at all."""
    return {
        CONF_NAME: DEFAULT_NAME,
        CONF_SOLARFOCUS_SYSTEM: system,
        CONF_HOST: "solarfocus.local",
        CONF_PORT: 502,
        CONF_API_VERSION: ApiVersions.V_23_020.value,
    }


def build_options(**overrides) -> dict:
    """Return config entry options with all components off unless overridden."""
    options = {
        CONF_SCAN_INTERVAL: 10,
        CONF_HEATING_CIRCUIT: 0,
        CONF_BUFFER: 0,
        CONF_BOILER: 0,
        CONF_FRESH_WATER_MODULE: 0,
        CONF_CIRCULATION: 0,
        CONF_DIFFERENTIAL_MODULE: 0,
        CONF_SOLAR: 0,
        CONF_HEATPUMP: False,
        CONF_BIOMASS_BOILER: False,
        CONF_PHOTOVOLTAIC: False,
    }
    options.update(overrides)
    return options


def build_config_entry(
    system: Systems = Systems.VAMPAIR, **overrides
) -> MockConfigEntry:
    """Return a config entry in the layout the current version stores.

    An override goes to whichever half of the entry holds that setting, so a
    test says what its entry is rather than where the integration keeps it.
    """
    data = build_data(system)
    options = build_options()

    for setting, value in overrides.items():
        if setting in data:
            data[setting] = value
        elif setting in options:
            options[setting] = value
        else:
            raise KeyError(f"{setting} is in neither the data nor the options")

    return MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        version=CURRENT_VERSION,
        unique_id=build_unique_id(data[CONF_HOST], data[CONF_PORT]),
        data=data,
        options=options,
    )


@pytest.fixture(name="config_entry")
def config_entry_fixture() -> MockConfigEntry:
    """Return a vampair config entry with one of every multi-instance component."""
    return build_config_entry(
        heating_circuit=1,
        buffer=1,
        boiler=1,
        heatpump=True,
    )


def build_api(system: Systems = Systems.VAMPAIR) -> MagicMock:
    """Return a mocked SolarfocusAPI that connects and updates successfully."""
    api = MagicMock()
    api.system = system
    api.api_version = ApiVersions.V_23_020
    api.connect.return_value = True
    api.is_connected = True
    for update in (
        "update_heating",
        "update_buffer",
        "update_boiler",
        "update_heatpump",
        "update_photovoltaic",
        "update_biomassboiler",
        "update_solar",
        "update_fresh_water_modules",
        "update_circulation",
        "update_differential_modules",
    ):
        getattr(api, update).return_value = True
    return api


@pytest.fixture(name="api")
def api_fixture() -> MagicMock:
    """Return a mocked SolarfocusAPI."""
    return build_api()


@pytest.fixture(name="mock_api")
def mock_api_fixture(api: MagicMock):
    """Patch SolarfocusAPI everywhere the integration constructs one."""
    with (
        patch(
            "custom_components.solarfocus.SolarfocusAPI", return_value=api
        ) as constructor,
        patch("custom_components.solarfocus.config_flow.SolarfocusAPI", return_value=api),
    ):
        constructor.instance = api
        yield constructor


def build_coordinator(entry, api: MagicMock | None = None) -> MagicMock:
    """Return a coordinator stub that entities can read from."""
    coordinator = MagicMock()
    coordinator._entry = entry
    coordinator.api = api if api is not None else build_api()
    coordinator.last_update_success = True
    # Every component reads, so the entities on them are available. A stub of it
    # rather than whatever a MagicMock makes of `in`, which is what availability
    # asks of this.
    coordinator.failed_components = set()
    # The real one, not a mock: the number the installer menu shows is shared
    # between two entities, and what a test of either is about is that sharing.
    coordinator.displayed_number = DisplayedNumber()
    return coordinator
