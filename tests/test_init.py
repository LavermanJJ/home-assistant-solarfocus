"""Test setting up, unloading and migrating a Solarfocus config entry."""

from unittest.mock import patch

from pysolarfocus import ApiVersions, Systems
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solarfocus import (
    async_migrate_entry,
    async_reload_entry,
    async_remove_config_entry_device,
)
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
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import CURRENT_VERSION, build_config_entry, build_options


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


async def test_a_refused_connection_says_so(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api, config_entry
) -> None:
    """Nothing to talk to at the address is the common half of a failed setup.

    Telling that user their controller answered and then went quiet sends them
    looking at the heating system for a problem that is in the network.
    """
    api.connect.return_value = False
    api.is_connected = False
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert config_entry.error_reason_translation_key == "cannot_connect"


async def test_a_controller_that_answers_nothing_says_that_instead(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api, config_entry
) -> None:
    """A connection that is accepted and read from anyway is the other half."""
    api.is_connected = True
    for component in ("heating", "buffer", "boiler", "heatpump"):
        getattr(api, f"update_{component}").return_value = False
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert config_entry.error_reason_translation_key == "cannot_set_up"


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

    assert entry.version == CURRENT_VERSION
    # Booleans became counts
    assert entry.options[CONF_HEATING_CIRCUIT] == 1
    assert entry.options[CONF_BUFFER] == 1
    assert entry.options[CONF_BOILER] == 0
    # Systems default to the heat pump the integration started out with
    assert entry.data[CONF_SOLARFOCUS_SYSTEM] == Systems.VAMPAIR
    # Connection details moved from data to options
    assert entry.data[CONF_HOST] == "solarfocus.local"
    assert entry.data[CONF_PORT] == 502
    assert entry.options[CONF_SCAN_INTERVAL] == 10
    assert CONF_HOST not in entry.options
    # New options got a default
    assert entry.data[CONF_API_VERSION] == "21.140"
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

    assert entry.version == CURRENT_VERSION
    assert entry.data == {
        CONF_NAME: DEFAULT_NAME,
        CONF_SOLARFOCUS_SYSTEM: Systems.THERMINATOR,
        CONF_HOST: "10.0.0.2",
        CONF_PORT: 502,
        CONF_API_VERSION: "21.140",
    }
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

    assert entry.version == CURRENT_VERSION
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

    assert entry.version == CURRENT_VERSION
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

    assert entry.version == CURRENT_VERSION
    assert entry.state is ConfigEntryState.LOADED


def _version_6_entry(**option_overrides) -> MockConfigEntry:
    """Return an entry as version 6 stored one: no unique id, and the
    connection still among the options."""
    options = {
        CONF_HOST: "solarfocus.local",
        CONF_PORT: 502,
        CONF_API_VERSION: ApiVersions.V_23_020.value,
        **build_options(**option_overrides),
    }
    return MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        version=6,
        unique_id=None,
        data={CONF_NAME: DEFAULT_NAME, CONF_SOLARFOCUS_SYSTEM: Systems.VAMPAIR},
        options=options,
    )


async def test_setup_moves_the_unique_id_to_the_configured_address(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """The address can change, and the unique id follows it on the next load."""
    entry = build_config_entry(heating_circuit=1)
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, unique_id="stale.local:502")

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.unique_id == "solarfocus.local:502"


async def test_setup_leaves_a_unique_id_less_entry_alone(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """A duplicate the migration left without a unique id keeps it that way."""
    first = build_config_entry()
    first.add_to_hass(hass)
    duplicate = build_config_entry(heating_circuit=1)
    duplicate.add_to_hass(hass)
    hass.config_entries.async_update_entry(duplicate, unique_id=None, title="Second")

    assert await hass.config_entries.async_setup(duplicate.entry_id)
    await hass.async_block_till_done()

    assert duplicate.unique_id is None
    assert first.unique_id == "solarfocus.local:502"


async def test_setup_does_not_move_a_unique_id_onto_another_entry(
    hass: HomeAssistant,
    enable_custom_integrations,
    mock_api,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The options flow refuses this, a hand-edited entry can still get here."""
    first = build_config_entry()
    first.add_to_hass(hass)
    other = build_config_entry(heating_circuit=1)
    other.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        other, unique_id="10.0.0.7:502", title="Second"
    )

    assert await hass.config_entries.async_setup(other.entry_id)
    await hass.async_block_till_done()

    assert other.unique_id == "10.0.0.7:502"
    assert "another entry already has it" in caplog.text


async def test_migration_moves_the_connection_into_the_entry_data(
    hass: HomeAssistant,
) -> None:
    """Version 8 keeps what it takes to read the system in `data`.

    Everything used to be an option, including the address. What a user
    changes about a system that already answers - how often to ask it, and
    which of its components to ask about - stays in `options`.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        version=7,
        unique_id="10.0.0.2:503",
        data={CONF_NAME: DEFAULT_NAME, CONF_SOLARFOCUS_SYSTEM: Systems.THERMINATOR},
        options={
            CONF_HOST: "10.0.0.2",
            CONF_PORT: 503,
            CONF_API_VERSION: "25.030",
            **build_options(heating_circuit=2, biomassboiler=True),
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == CURRENT_VERSION
    assert entry.data == {
        CONF_NAME: DEFAULT_NAME,
        CONF_SOLARFOCUS_SYSTEM: Systems.THERMINATOR,
        CONF_HOST: "10.0.0.2",
        CONF_PORT: 503,
        CONF_API_VERSION: "25.030",
    }
    for moved in (CONF_HOST, CONF_PORT, CONF_API_VERSION):
        assert moved not in entry.options

    # What the user chose about the system is left where it was
    assert entry.options[CONF_SCAN_INTERVAL] == 10
    assert entry.options[CONF_HEATING_CIRCUIT] == 2
    assert entry.options[CONF_BIOMASS_BOILER] is True
    assert entry.unique_id == "10.0.0.2:503"


async def test_migration_backfills_the_unique_id(hass: HomeAssistant) -> None:
    """Entries from before version 7 have no unique id.

    Without one the duplicate check of the config flow cannot see them, so an
    existing installation could still be added a second time.
    """
    entry = _version_6_entry(host="10.0.0.2", port=503)
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == CURRENT_VERSION
    assert entry.unique_id == "10.0.0.2:503"


async def test_migration_leaves_a_duplicate_entry_without_a_unique_id(
    hass: HomeAssistant,
) -> None:
    """Nothing stopped two entries for one system, so both can exist.

    Giving the second one the same unique id would be a collision, so it keeps
    working without one instead.
    """
    first = build_config_entry()
    first.add_to_hass(hass)
    duplicate = _version_6_entry()
    duplicate.add_to_hass(hass)

    assert await async_migrate_entry(hass, duplicate) is True

    assert duplicate.version == CURRENT_VERSION
    assert duplicate.unique_id is None
    assert first.unique_id == "solarfocus.local:502"


async def test_migration_of_a_current_entry_changes_nothing(
    hass: HomeAssistant,
) -> None:
    """An entry already on the current version is left alone."""
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1)
    entry.add_to_hass(hass)
    data, options = dict(entry.data), dict(entry.options)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == CURRENT_VERSION
    assert entry.data == data
    assert entry.options == options


def _version_8_entry(hass: HomeAssistant, title: str = DEFAULT_NAME) -> MockConfigEntry:
    """Return an entry as version 8 stored one, added to hass."""
    entry = build_config_entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, title=title, version=8)
    return entry


async def test_migration_identifies_the_device_by_the_entry_id(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Version 9 takes the device identity off the title of the entry.

    The device is re-identified rather than replaced, so it keeps its id and
    everything the user hung on it: the area, the name they gave it, and every
    automation that points at it by device.
    """
    entry = _version_8_entry(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.title)},
        name="Solarfocus",
    )
    device_registry.async_update_device(device.id, name_by_user="Heizung Keller")

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == CURRENT_VERSION

    migrated = device_registry.async_get(device.id)
    assert migrated is not None
    assert migrated.identifiers == {(DOMAIN, entry.entry_id)}
    # The same device, so what the user put on it is still there
    assert migrated.id == device.id
    assert migrated.name_by_user == "Heizung Keller"
    assert device_registry.async_get_device({(DOMAIN, entry.title)}) is None


async def test_migration_without_a_device_is_still_a_migration(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """An entry that has never been set up has no device to re-identify."""
    entry = _version_8_entry(hass)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == CURRENT_VERSION
    assert not dr.async_entries_for_config_entry(device_registry, entry.entry_id)


async def test_migration_finds_the_device_of_an_entry_renamed_since_setup(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """The registry holds the title of the last setup, not the current one.

    Renaming a version 8 entry while the controller was unreachable left the
    device under the old title and the entry under the new one. Looking the old
    identifier up by the current title found nothing and the migration did
    nothing, so the next setup built a fresh device and orphaned the original -
    exactly what this migration exists to prevent.
    """
    entry = _version_8_entry(hass, title="Haus")
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "Haus")}
    )
    hass.config_entries.async_update_entry(entry, title="Werkstatt")

    assert await async_migrate_entry(hass, entry) is True

    assert device_registry.async_get(device.id).identifiers == {
        (DOMAIN, entry.entry_id)
    }


async def test_migration_keeps_the_device_the_entities_are_on(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, entity_registry
) -> None:
    """A rename under version 8 built a second device, so there can be two.

    The one the entities sit on is the live one. The other holds nothing and
    would never leave the registry on its own, because it still names a config
    entry that exists.
    """
    entry = _version_8_entry(hass, title="Werkstatt")
    abandoned = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "Haus")}
    )
    live = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "Werkstatt")}
    )
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "Werkstatt_bo1_temperature",
        config_entry=entry,
        device_id=live.id,
    )

    assert await async_migrate_entry(hass, entry) is True

    assert device_registry.async_get(live.id).identifiers == {(DOMAIN, entry.entry_id)}
    assert device_registry.async_get(abandoned.id) is None
    assert len(dr.async_entries_for_config_entry(device_registry, entry.entry_id)) == 1


async def test_migration_leaves_the_device_of_another_entry_alone(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Two entries under different names each keep their own device.

    The old identifier was the title, which is global to the domain rather than
    to the entry, so the lookup has to be scoped to the entry being migrated.
    """
    entry = _version_8_entry(hass, title="Haus")
    other = _version_8_entry(hass, title="Werkstatt")
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "Haus")}
    )
    untouched = device_registry.async_get_or_create(
        config_entry_id=other.entry_id, identifiers={(DOMAIN, "Werkstatt")}
    )

    assert await async_migrate_entry(hass, entry) is True

    assert device_registry.async_get(untouched.id).identifiers == {
        (DOMAIN, "Werkstatt")
    }


async def test_a_renamed_entry_keeps_its_device(
    hass: HomeAssistant, enable_custom_integrations, mock_api, device_registry
) -> None:
    """What the whole migration is for.

    Renaming an entry used to leave its device behind and build a second one
    under the new title, taking every entity with it.
    """
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hub = device_registry.async_get_device({(DOMAIN, entry.entry_id)})
    before = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert hub is not None

    hass.config_entries.async_update_entry(entry, title="Heizung Keller")
    await hass.async_block_till_done()
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    after = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    # The same hub, and the same components under it - a rename adds nothing
    assert device_registry.async_get_device({(DOMAIN, entry.entry_id)}).id == hub.id
    assert {device.id for device in after} == {device.id for device in before}


async def test_a_renamed_entry_still_duplicates_its_entities(
    hass: HomeAssistant, enable_custom_integrations, mock_api, entity_registry
) -> None:
    """The device half of the rename is fixed, the entity half is not.

    Entity unique ids are `f"{entry.title}_{key}"`, so a rename gives every
    entity of the entry a new one and the registry keeps the old: two sets, the
    dead one and a `_2` suffixed one, both now on the single device the
    migration keeps rather than split across two.

    This is here to record it rather than leave it to be discovered. It is the
    other half of #208, and this test is what will fail when that half is done -
    which is the point of writing it down.
    """
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    before = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    hass.config_entries.async_update_entry(entry, title="Heizung Keller")
    await hass.async_block_till_done()
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    after = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    assert len(after) == 2 * len(before)
    assert any(registered.entity_id.endswith("_2") for registered in after)


async def test_every_component_is_its_own_device_under_the_hub(
    hass: HomeAssistant, enable_custom_integrations, mock_api, device_registry
) -> None:
    """The layout a user sees: a controller, and the components of it.

    Two heating circuits, one buffer and a heat pump is five devices - not one
    page holding every entity of a heating system.
    """
    entry = build_config_entry(
        Systems.VAMPAIR, heating_circuit=2, buffer=1, heatpump=True
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    identifiers = {next(iter(device.identifiers))[1] for device in devices}

    assert identifiers == {
        entry.entry_id,
        f"{entry.entry_id}_hc1",
        f"{entry.entry_id}_hc2",
        f"{entry.entry_id}_bu1",
        f"{entry.entry_id}_hp",
    }

    hub = device_registry.async_get_device({(DOMAIN, entry.entry_id)})
    components = [device for device in devices if device.id != hub.id]

    assert components
    assert all(device.via_device_id == hub.id for device in components)
    assert hub.via_device_id is None


async def test_every_entity_sits_on_the_component_it_reads(
    hass: HomeAssistant, enable_custom_integrations, mock_api, device_registry,
    entity_registry,
) -> None:
    """An entity of heating circuit 2 belongs to the device of heating circuit 2."""
    entry = build_config_entry(
        Systems.VAMPAIR, heating_circuit=2, boiler=1, heatpump=True
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    misplaced = []
    for registered in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        device = device_registry.async_get(registered.device_id)
        identifier = next(iter(device.identifiers))[1]
        component = registered.unique_id.split("_")[1]
        if not identifier.endswith(f"_{component}"):
            misplaced.append((registered.entity_id, identifier))

    assert not misplaced


async def test_the_entity_id_is_the_device_and_the_english_key(
    hass: HomeAssistant, enable_custom_integrations, mock_api, entity_registry
) -> None:
    """Home Assistant composes the id; the integration only supplies half of it.

    The device half follows the language of the installation, because a device
    name is translated like any other. The entity half is the words of the key,
    which `create_description` keeps English on purpose - so a German
    installation reads `sensor.heizkreis_1_supply_temperature`, not
    `sensor.heizkreis_1_vorlauftemperatur`.

    Entities already in the registry keep the ids they were given, so an
    installation upgrading from 5.1.0 keeps its `sensor.solarfocus_*` ids and
    only newly added components get these.
    """
    await hass.config.async_update(language="de")

    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, solar=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ids = {
        registered.entity_id
        for registered in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        )
    }

    assert "sensor.heizkreis_1_supply_temperature" in ids
    # One solar circuit is not numbered, in the device name and so in the id
    assert "sensor.solar_collector_temperature_1" in ids
    # The words of a key are never translated
    assert not [entity_id for entity_id in ids if "vorlauf" in entity_id]


async def test_lowering_a_count_removes_the_device_and_its_entities(
    hass: HomeAssistant, enable_custom_integrations, mock_api, device_registry,
    entity_registry,
) -> None:
    """A component a user takes away must not leave anything behind.

    The device of a component that is gone still names a config entry that
    exists, so nothing removes it on its own - and its entities sit there
    holding the value they had when the component was last polled.
    """
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=3)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    third = device_registry.async_get_device({(DOMAIN, f"{entry.entry_id}_hc3")})
    assert third is not None
    assert er.async_entries_for_device(entity_registry, third.id)

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_HEATING_CIRCUIT: 2}
    )
    await hass.async_block_till_done()

    assert device_registry.async_get_device({(DOMAIN, f"{entry.entry_id}_hc3")}) is None
    assert not er.async_entries_for_device(
        entity_registry, third.id, include_disabled_entities=True
    )
    # The ones that are left are untouched
    assert device_registry.async_get_device({(DOMAIN, f"{entry.entry_id}_hc2")})


async def test_switching_a_component_off_removes_its_device(
    hass: HomeAssistant, enable_custom_integrations, mock_api, device_registry
) -> None:
    """The same for the components that are a switch rather than a count."""
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, photovoltaic=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get_device({(DOMAIN, f"{entry.entry_id}_pv")})

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_PHOTOVOLTAIC: False}
    )
    await hass.async_block_till_done()

    assert device_registry.async_get_device({(DOMAIN, f"{entry.entry_id}_pv")}) is None


async def test_raising_a_count_adds_a_device(
    hass: HomeAssistant, enable_custom_integrations, mock_api, device_registry
) -> None:
    """The other direction, and the hub keeps every one of them."""
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_HEATING_CIRCUIT: 2}
    )
    await hass.async_block_till_done()

    hub = device_registry.async_get_device({(DOMAIN, entry.entry_id)})
    second = device_registry.async_get_device({(DOMAIN, f"{entry.entry_id}_hc2")})

    assert second is not None
    assert second.via_device_id == hub.id


async def test_removing_the_entry_removes_every_device(
    hass: HomeAssistant, enable_custom_integrations, mock_api, device_registry
) -> None:
    """The components go with the controller they hang off."""
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=2, heatpump=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert not dr.async_entries_for_config_entry(device_registry, entry.entry_id)


async def test_a_device_can_only_be_deleted_once_its_component_is_gone(
    hass: HomeAssistant, enable_custom_integrations, mock_api, device_registry
) -> None:
    """Deleting a configured device by hand would only have it built again.

    A stale one is the user's to remove, which is what the delete button on a
    device page asks this.
    """
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    live = device_registry.async_get_device({(DOMAIN, f"{entry.entry_id}_hc1")})
    hub = device_registry.async_get_device({(DOMAIN, entry.entry_id)})
    stale = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_bu4")},
    )

    assert await async_remove_config_entry_device(hass, entry, live) is False
    assert await async_remove_config_entry_device(hass, entry, hub) is False
    assert await async_remove_config_entry_device(hass, entry, stale) is True


async def test_a_new_component_device_lands_in_the_area_of_its_controller(
    hass: HomeAssistant, enable_custom_integrations, mock_api, device_registry,
    area_registry,
) -> None:
    """Splitting the components off must not take them out of their room.

    Everything of an entry used to sit on one device, so a user who put that
    device in a room put every entity of their heating system in it. A new
    device is in no area, and an automation or a voice command scoped to a room
    stops matching what is in none.
    """
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    heizraum = area_registry.async_get_or_create("Heizraum")
    hub = device_registry.async_get_device({(DOMAIN, entry.entry_id)})
    device_registry.async_update_device(hub.id, area_id=heizraum.id)

    # A component that appears afterwards, as all of them did on the upgrade
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_HEATING_CIRCUIT: 2}
    )
    await hass.async_block_till_done()

    second = device_registry.async_get_device({(DOMAIN, f"{entry.entry_id}_hc2")})

    assert second.area_id == heizraum.id


async def test_a_component_the_user_moved_stays_where_they_put_it(
    hass: HomeAssistant, enable_custom_integrations, mock_api, device_registry,
    area_registry,
) -> None:
    """Inheriting the area is for devices that are new, and only then."""
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    heizraum = area_registry.async_get_or_create("Heizraum")
    wohnzimmer = area_registry.async_get_or_create("Wohnzimmer")
    hub = device_registry.async_get_device({(DOMAIN, entry.entry_id)})
    circuit = device_registry.async_get_device({(DOMAIN, f"{entry.entry_id}_hc1")})
    device_registry.async_update_device(hub.id, area_id=heizraum.id)
    device_registry.async_update_device(circuit.id, area_id=wohnzimmer.id)

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device({(DOMAIN, f"{entry.entry_id}_hc1")}).area_id
        == wohnzimmer.id
    )


async def test_the_solar_entities_follow_the_key_the_count_uses(
    hass: HomeAssistant, enable_custom_integrations, mock_api, entity_registry
) -> None:
    """One solar circuit is keyed without its index, several are keyed with it.

    Crossing that line renames every entity of the first circuit. Left alone,
    the set under the other key stays in the registry for good - on a device
    that is still configured, so it is never removed with it - reading the
    value it had when the count changed.
    """
    entry = build_config_entry(
        Systems.VAMPAIR, api_version=ApiVersions.V_25_030.value, solar=1
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    def _solar_keys() -> set[str]:
        return {
            registered.unique_id.removeprefix(f"{DEFAULT_NAME}_")
            for registered in er.async_entries_for_config_entry(
                entity_registry, entry.entry_id
            )
            if "_so" in registered.unique_id
        }

    unnumbered = _solar_keys()
    assert unnumbered
    assert all(key.startswith("so_") for key in unnumbered)

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_SOLAR: 2}
    )
    await hass.async_block_till_done()

    # The first circuit was renamed rather than left behind and built again
    numbered = _solar_keys()
    assert all(key.startswith(("so1_", "so2_")) for key in numbered)
    assert {key.replace("so1_", "so_") for key in numbered if key.startswith("so1_")} == (
        unnumbered
    )

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_SOLAR: 1}
    )
    await hass.async_block_till_done()

    assert _solar_keys() == unnumbered
