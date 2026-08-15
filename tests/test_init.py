"""Test setting up, unloading and migrating a Solarfocus config entry."""

from unittest.mock import patch

from pysolarfocus import ApiVersions, Systems
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solarfocus import async_migrate_entry, async_reload_entry
from custom_components.solarfocus.const import (
    CONF_BIOMASS_BOILER,
    CONF_BOILER,
    CONF_BUFFER,
    CONF_FRESH_WATER_MODULE,
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
    CONF_PHOTOVOLTAIC,
    CONF_SOLAR,
    CONF_SOLARFOCUS_SYSTEM,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant

from .conftest import build_config_entry


async def test_setup_and_unload_entry(
    hass: HomeAssistant, enable_custom_integrations, mock_api, config_entry
) -> None:
    """A reachable device sets up the entry and unloading cleans up again."""
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not None

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_passes_component_counts_to_the_library(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """The configured component counts are handed to pysolarfocus."""
    entry = build_config_entry(
        Systems.THERMINATOR,
        api_version=ApiVersions.V_25_030.value,
        heating_circuit=3,
        buffer=2,
        boiler=1,
        fresh_water_module=2,
        solar=2,
        biomassboiler=True,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    kwargs = mock_api.call_args.kwargs
    assert kwargs["heating_circuit_count"] == 3
    assert kwargs["buffer_count"] == 2
    assert kwargs["boiler_count"] == 1
    # Was never passed, so the library built its default of one module and
    # every entity of a second one raised IndexError on read.
    assert kwargs["fresh_water_module_count"] == 2
    assert kwargs["solar_count"] == 2
    assert kwargs["system"] is Systems.THERMINATOR
    assert kwargs["api_version"] is ApiVersions.V_25_030


@pytest.mark.parametrize(
    ("stored_solar", "expected_count"), [(True, 1), (False, 0), (0, 0), (4, 4)]
)
async def test_setup_accepts_legacy_boolean_solar_option(
    hass: HomeAssistant,
    enable_custom_integrations,
    mock_api,
    stored_solar,
    expected_count: int,
) -> None:
    """Entries written before solar became a count still set up."""
    entry = build_config_entry(
        Systems.VAMPAIR,
        api_version=ApiVersions.V_25_030.value,
        heating_circuit=1,
        solar=stored_solar,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert mock_api.call_args.kwargs["solar_count"] == expected_count


@pytest.mark.parametrize("stored_solar", [2, 4])
async def test_setup_caps_solar_below_the_version_that_supports_several(
    hass: HomeAssistant, enable_custom_integrations, mock_api, stored_solar: int
) -> None:
    """The options allow a count the selected api version cannot have.

    pysolarfocus rejects more than one solar circuit below 25.030 by raising
    InvalidConfigurationError, which failed the whole entry rather than just
    the extra circuits.
    """
    entry = build_config_entry(
        Systems.VAMPAIR,
        api_version=ApiVersions.V_23_020.value,
        heating_circuit=1,
        solar=stored_solar,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert mock_api.call_args.kwargs["solar_count"] == 1


async def test_setup_retries_when_the_device_is_unreachable(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api, config_entry
) -> None:
    """A failing first refresh raises ConfigEntryNotReady."""
    api.connect.return_value = False
    api.is_connected = False
    api.update_heating.side_effect = OSError("no route to host")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_updating_options_reloads_the_entry(
    hass: HomeAssistant, enable_custom_integrations, mock_api, config_entry
) -> None:
    """The update listener reloads the entry so entities follow the new options."""
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as async_reload:
        hass.config_entries.async_update_entry(
            config_entry, options={**config_entry.options, CONF_SCAN_INTERVAL: 60}
        )
        await hass.async_block_till_done()

    assert async_reload.call_args_list == [((config_entry.entry_id,),)]


async def test_unload_without_setup_is_a_noop(hass: HomeAssistant) -> None:
    """Unloading an entry that never got set up must not raise."""
    from custom_components.solarfocus import async_unload_entry

    entry = build_config_entry()
    entry.add_to_hass(hass)

    assert await async_unload_entry(hass, entry) is True


async def test_reload_entry(
    hass: HomeAssistant, enable_custom_integrations, mock_api, config_entry
) -> None:
    """Reloading tears the entry down and sets it up again."""
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await async_reload_entry(hass, config_entry)
    await hass.async_block_till_done()

    assert config_entry.runtime_data is not None


async def test_migration_from_version_1(hass: HomeAssistant) -> None:
    """Version 1 stored booleans for the components and no system."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        version=1,
        data={
            CONF_NAME: DEFAULT_NAME,
            CONF_HOST: "solarfocus.local",
            CONF_PORT: 502,
            CONF_SCAN_INTERVAL: 10,
            CONF_HEATING_CIRCUIT: True,
            CONF_BUFFER: True,
            CONF_BOILER: False,
            CONF_HEATPUMP: True,
            CONF_PHOTOVOLTAIC: False,
            "pelletsboiler": False,
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == 6
    # Booleans became counts
    assert entry.options[CONF_HEATING_CIRCUIT] == 1
    assert entry.options[CONF_BUFFER] == 1
    assert entry.options[CONF_BOILER] == 0
    # Systems default to the heat pump the integration started out with
    assert entry.data[CONF_SOLARFOCUS_SYSTEM] == Systems.VAMPAIR
    # Connection details moved from data to options
    assert entry.options[CONF_HOST] == "solarfocus.local"
    assert entry.options[CONF_PORT] == 502
    assert entry.options[CONF_SCAN_INTERVAL] == 10
    assert CONF_HOST not in entry.data
    # New options got a default
    assert entry.options[CONF_API_VERSION] == "21.140"
    assert entry.options[CONF_FRESH_WATER_MODULE] == 0
    assert entry.options[CONF_SOLAR] == 0
    # pelletsboiler was renamed
    assert "pelletsboiler" not in entry.options
    assert entry.options[CONF_BIOMASS_BOILER] is False
    assert entry.data[CONF_NAME] == DEFAULT_NAME


async def test_migration_from_version_3_moves_options(hass: HomeAssistant) -> None:
    """Version 3 kept everything in data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        version=3,
        data={
            CONF_NAME: DEFAULT_NAME,
            CONF_SOLARFOCUS_SYSTEM: Systems.THERMINATOR,
            CONF_HOST: "10.0.0.2",
            CONF_PORT: 502,
            CONF_SCAN_INTERVAL: 15,
            CONF_HEATING_CIRCUIT: 2,
            CONF_BUFFER: 1,
            CONF_BOILER: 1,
            CONF_HEATPUMP: False,
            CONF_PHOTOVOLTAIC: True,
            CONF_SOLAR: True,
            "pelletsboiler": True,
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == 6
    assert entry.data == {
        CONF_NAME: DEFAULT_NAME,
        CONF_SOLARFOCUS_SYSTEM: Systems.THERMINATOR,
    }
    assert entry.options[CONF_HOST] == "10.0.0.2"
    assert entry.options[CONF_SCAN_INTERVAL] == 15
    assert entry.options[CONF_HEATING_CIRCUIT] == 2
    assert entry.options[CONF_BIOMASS_BOILER] is True
    # Solar became a count on version 6
    assert entry.options[CONF_SOLAR] == 1


async def test_migration_from_version_5_converts_solar_to_a_count(
    hass: HomeAssistant,
) -> None:
    """Version 5 stored solar as a boolean."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        version=5,
        data={CONF_NAME: DEFAULT_NAME, CONF_SOLARFOCUS_SYSTEM: Systems.VAMPAIR},
        options={
            CONF_HOST: "10.0.0.2",
            CONF_PORT: 502,
            CONF_SCAN_INTERVAL: 10,
            CONF_API_VERSION: "23.020",
            CONF_HEATING_CIRCUIT: 1,
            CONF_BUFFER: 1,
            CONF_BOILER: 1,
            CONF_FRESH_WATER_MODULE: 0,
            CONF_PHOTOVOLTAIC: False,
            CONF_SOLAR: True,
            CONF_HEATPUMP: True,
            CONF_BIOMASS_BOILER: False,
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == 6
    assert entry.options[CONF_SOLAR] == 1


async def test_migration_keeps_an_existing_solar_count(hass: HomeAssistant) -> None:
    """A count written by a newer version survives the version 5 migration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        version=5,
        data={CONF_NAME: DEFAULT_NAME, CONF_SOLARFOCUS_SYSTEM: Systems.VAMPAIR},
        options={
            CONF_HOST: "10.0.0.2",
            CONF_PORT: 502,
            CONF_SCAN_INTERVAL: 10,
            CONF_API_VERSION: "25.030",
            CONF_HEATING_CIRCUIT: 1,
            CONF_BUFFER: 1,
            CONF_BOILER: 1,
            CONF_FRESH_WATER_MODULE: 0,
            CONF_PHOTOVOLTAIC: False,
            CONF_SOLAR: 3,
            CONF_HEATPUMP: True,
            CONF_BIOMASS_BOILER: False,
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.options[CONF_SOLAR] == 3


async def test_migration_from_version_4_renames_the_pellets_boiler(
    hass: HomeAssistant,
) -> None:
    """Version 4 still called the biomass boiler "pelletsboiler"."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        version=4,
        data={CONF_NAME: DEFAULT_NAME, CONF_SOLARFOCUS_SYSTEM: Systems.ECOTOP},
        options={
            CONF_HOST: "10.0.0.2",
            CONF_PORT: 502,
            CONF_SCAN_INTERVAL: 10,
            CONF_API_VERSION: "21.140",
            CONF_HEATING_CIRCUIT: 1,
            CONF_BUFFER: 1,
            CONF_BOILER: 1,
            CONF_FRESH_WATER_MODULE: 0,
            CONF_PHOTOVOLTAIC: False,
            CONF_SOLAR: False,
            CONF_HEATPUMP: False,
            "pelletsboiler": True,
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == 6
    assert "pelletsboiler" not in entry.options
    assert entry.options[CONF_BIOMASS_BOILER] is True


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5])
async def test_migrated_entries_can_be_set_up(
    hass: HomeAssistant, enable_custom_integrations, mock_api, version: int
) -> None:
    """Every supported old entry ends up in the layout async_setup_entry reads.

    Migrating without reaching the current version leaves the entry half converted
    and setup then fails on a missing option.
    """
    data = {
        CONF_NAME: DEFAULT_NAME,
        CONF_SOLARFOCUS_SYSTEM: Systems.THERMINATOR,
        CONF_HOST: "10.0.0.2",
        CONF_PORT: 502,
        CONF_SCAN_INTERVAL: 10,
        CONF_HEATING_CIRCUIT: 1,
        CONF_BUFFER: 1,
        CONF_BOILER: 1,
        CONF_PHOTOVOLTAIC: False,
        CONF_HEATPUMP: False,
        "pelletsboiler": True,
    }
    options = {}

    if version >= 2:
        data[CONF_SOLAR] = False
    if version >= 4:
        options = {
            CONF_API_VERSION: "21.140",
            CONF_FRESH_WATER_MODULE: 0,
            **{key: data.pop(key) for key in list(data) if key not in (CONF_NAME, CONF_SOLARFOCUS_SYSTEM)},
        }
    if version >= 5:
        options[CONF_BIOMASS_BOILER] = options.pop("pelletsboiler")

    entry = MockConfigEntry(
        domain=DOMAIN, title=DEFAULT_NAME, version=version, data=data, options=options
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 6
    assert entry.state is ConfigEntryState.LOADED


async def test_migration_of_a_current_entry_changes_nothing(
    hass: HomeAssistant,
) -> None:
    """An entry already on the current version is left alone."""
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1)
    entry.add_to_hass(hass)
    data, options = dict(entry.data), dict(entry.options)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == 6
    assert entry.data == data
    assert entry.options == options
