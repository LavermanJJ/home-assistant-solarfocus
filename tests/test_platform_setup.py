"""Test which entities each platform creates for a given configuration.

`async_setup_entry` of every platform turns the configured component counts into
entities. Creating one entity too many means a broken entity in the UI, creating
one too few means a silently missing entity, and both only show up once an entry
is actually set up.
"""

from pysolarfocus import ApiVersions, Systems
import pytest

from custom_components.solarfocus import (
    binary_sensor,
    button,
    climate,
    number,
    select,
    sensor,
    switch,
    water_heater,
)
from custom_components.solarfocus.const import (
    BOILER_COMPONENT_PREFIX,
    BUFFER_COMPONENT_PREFIX,
    HEATING_CIRCUIT_COMPONENT_PREFIX,
    SOLAR_COMPONENT_PREFIX,
)
from homeassistant.core import HomeAssistant

from .conftest import build_config_entry, build_coordinator

PLATFORMS = [
    binary_sensor,
    button,
    climate,
    number,
    select,
    sensor,
    switch,
    water_heater,
]


async def _setup(hass: HomeAssistant, platform, entry) -> list:
    """Run a platform's async_setup_entry and return the created entities."""
    entry.add_to_hass(hass)
    entry.runtime_data = build_coordinator(entry)

    added = []
    await platform.async_setup_entry(hass, entry, lambda entities: added.extend(entities))
    return added


def _keys(entities) -> list[str]:
    return [entity.entity_description.key for entity in entities]


@pytest.mark.parametrize("platform", PLATFORMS, ids=lambda p: p.__name__.split(".")[-1])
async def test_no_components_creates_no_entities(
    hass: HomeAssistant, platform
) -> None:
    """An entry without any component must not create entities."""
    entities = await _setup(hass, platform, build_config_entry())

    assert entities == []


@pytest.mark.parametrize("platform", PLATFORMS, ids=lambda p: p.__name__.split(".")[-1])
def test_platform_declares_parallel_updates(platform) -> None:
    """Home Assistant only limits parallelism if the platform declares it.

    Read-only platforms are unlimited, platforms that write hold their service
    calls to one at a time so two writes cannot interleave on the registers of
    the same component.
    """
    read_only = platform in (binary_sensor, sensor)

    assert platform.PARALLEL_UPDATES == (0 if read_only else 1)


@pytest.mark.parametrize("platform", PLATFORMS, ids=lambda p: p.__name__.split(".")[-1])
async def test_entity_keys_are_unique(hass: HomeAssistant, platform) -> None:
    """Duplicate keys would collide on the same unique id."""
    entry = build_config_entry(
        Systems.THERMINATOR,
        api_version=ApiVersions.V_26_020.value,
        heating_circuit=3,
        buffer=2,
        boiler=2,
        fresh_water_module=2,
        solar=2,
        biomassboiler=True,
        photovoltaic=True,
    )

    keys = _keys(await _setup(hass, platform, entry))

    assert len(keys) == len(set(keys))


@pytest.mark.parametrize("count", [1, 2, 8])
async def test_one_climate_entity_per_heating_circuit(
    hass: HomeAssistant, count: int
) -> None:
    """Every configured heating circuit gets its own thermostat."""
    entry = build_config_entry(heating_circuit=count)

    entities = await _setup(hass, climate, entry)

    assert _keys(entities) == [
        f"{HEATING_CIRCUIT_COMPONENT_PREFIX}{i + 1}_thermostat" for i in range(count)
    ]


@pytest.mark.parametrize("count", [1, 4])
async def test_one_water_heater_per_boiler(hass: HomeAssistant, count: int) -> None:
    """Every configured boiler gets a water heater."""
    entry = build_config_entry(boiler=count)

    entities = await _setup(hass, water_heater, entry)

    assert _keys(entities) == [
        f"{BOILER_COMPONENT_PREFIX}{i + 1}_domestic_hot_water" for i in range(count)
    ]


async def test_buttons_are_created_per_boiler(hass: HomeAssistant) -> None:
    """Each boiler gets the single charge and circulation buttons."""
    entry = build_config_entry(boiler=2)

    entities = await _setup(hass, button, entry)

    assert _keys(entities) == [
        f"{BOILER_COMPONENT_PREFIX}1_single_charge",
        f"{BOILER_COMPONENT_PREFIX}1_circulation",
        f"{BOILER_COMPONENT_PREFIX}2_single_charge",
        f"{BOILER_COMPONENT_PREFIX}2_circulation",
    ]


async def test_switches_need_a_heatpump(hass: HomeAssistant) -> None:
    """The only switch belongs to the heat pump."""
    assert await _setup(hass, switch, build_config_entry(heatpump=False)) == []

    entities = await _setup(hass, switch, build_config_entry(heatpump=True))

    assert _keys(entities) == ["hp_evu_lock"]


async def test_sensors_are_created_per_component_instance(
    hass: HomeAssistant,
) -> None:
    """The number of sensors scales with the configured instances."""
    single = await _setup(hass, sensor, build_config_entry(buffer=1))
    double = await _setup(hass, sensor, build_config_entry(buffer=2))

    assert single
    assert len(double) == 2 * len(single)
    assert all(key.startswith(BUFFER_COMPONENT_PREFIX) for key in _keys(double))
    assert {key.split("_", 1)[0] for key in _keys(double)} == {
        f"{BUFFER_COMPONENT_PREFIX}1",
        f"{BUFFER_COMPONENT_PREFIX}2",
    }


async def test_sensors_of_a_disabled_component_are_not_created(
    hass: HomeAssistant,
) -> None:
    """A therminator has no heat pump sensors."""
    entry = build_config_entry(Systems.THERMINATOR, biomassboiler=True, heatpump=False)

    keys = _keys(await _setup(hass, sensor, entry))

    assert keys
    assert not any(key.startswith("hp_") for key in keys)


async def test_version_specific_entities_are_filtered(hass: HomeAssistant) -> None:
    """An entity newer than the configured api version is not created."""
    old = _keys(
        await _setup(
            hass,
            number,
            build_config_entry(photovoltaic=True, api_version="25.030"),
        )
    )
    new = _keys(
        await _setup(
            hass,
            number,
            build_config_entry(photovoltaic=True, api_version="26.020"),
        )
    )

    assert "pv_hems_target_electrical_power" not in old
    assert "pv_hems_target_electrical_power" in new


async def test_system_specific_entities_are_filtered(hass: HomeAssistant) -> None:
    """Entities excluded for a system are not created for it (issue #163)."""
    unsupported = {
        description.key
        for description in sensor.BUFFER_SENSOR_TYPES
        if description.unsupported_systems
        and Systems.THERMINATOR in description.unsupported_systems
    }
    assert unsupported, "expected at least one system specific buffer sensor"

    vampair = _keys(await _setup(hass, sensor, build_config_entry(buffer=1)))
    therminator = _keys(
        await _setup(hass, sensor, build_config_entry(Systems.THERMINATOR, buffer=1))
    )

    for item in unsupported:
        assert f"{BUFFER_COMPONENT_PREFIX}1_{item}" in vampair
        assert f"{BUFFER_COMPONENT_PREFIX}1_{item}" not in therminator


async def test_single_solar_instance_keeps_the_unnumbered_key(
    hass: HomeAssistant,
) -> None:
    """A single solar keeps its pre-multi-instance entity id."""
    entry = build_config_entry(solar=1, api_version="25.030")

    entities = await _setup(hass, sensor, entry)

    assert entities
    for entity in entities:
        assert entity.entity_description.key.startswith(f"{SOLAR_COMPONENT_PREFIX}_")
        # An empty index is what keeps the number out of the translated name
        assert entity.entity_description.translation_placeholders == {"idx": ""}
        # The index is still needed to address the component in the library
        assert entity.entity_description.component_idx == "1"


async def test_multiple_solar_instances_are_numbered(hass: HomeAssistant) -> None:
    """From api version 25.030 on, several solar circuits can be configured."""
    entry = build_config_entry(solar=3, api_version="25.030")

    entities = await _setup(hass, sensor, entry)

    assert len(entities) == 3 * len(sensor.SOLAR_SENSOR_TYPES)
    assert {entity.entity_description.component_idx for entity in entities} == {
        "1",
        "2",
        "3",
    }


async def test_older_api_versions_are_limited_to_one_solar(
    hass: HomeAssistant,
) -> None:
    """Before 25.030 the device only exposes a single solar circuit."""
    entry = build_config_entry(solar=3, api_version="23.020")

    entities = await _setup(hass, sensor, entry)

    assert len(entities) == len(sensor.SOLAR_SENSOR_TYPES)
    assert all(
        entity.entity_description.key.startswith(f"{SOLAR_COMPONENT_PREFIX}_")
        for entity in entities
    )


async def test_legacy_boolean_solar_option_creates_one_instance(
    hass: HomeAssistant,
) -> None:
    """An entry that still stores solar as a boolean must not break setup."""
    entry = build_config_entry(solar=True, api_version="25.030")

    entities = await _setup(hass, sensor, entry)

    assert len(entities) == len(sensor.SOLAR_SENSOR_TYPES)


async def test_selects_cover_all_configured_components(hass: HomeAssistant) -> None:
    """Selects exist for heating circuits, boilers and the heat pump."""
    entry = build_config_entry(heating_circuit=1, boiler=1, heatpump=True)

    keys = _keys(await _setup(hass, select, entry))

    assert any(key.startswith(HEATING_CIRCUIT_COMPONENT_PREFIX) for key in keys)
    assert any(key.startswith(BOILER_COMPONENT_PREFIX) for key in keys)
    assert "hp_smart_grid" in keys


async def test_binary_sensors_cover_all_configured_components(
    hass: HomeAssistant,
) -> None:
    """Binary sensors exist for every component that has one."""
    entry = build_config_entry(
        Systems.THERMINATOR,
        # The fresh water module binary sensors need at least 23.040
        api_version=ApiVersions.V_26_020.value,
        heating_circuit=1,
        buffer=1,
        fresh_water_module=1,
        biomassboiler=True,
        photovoltaic=True,
    )

    keys = _keys(await _setup(hass, binary_sensor, entry))

    for prefix in ("hc1_", "bu1_", "bb_", "pv_", "fm1_"):
        assert any(key.startswith(prefix) for key in keys), prefix


async def test_entities_read_the_coordinator(hass: HomeAssistant) -> None:
    """Created entities are wired to the coordinator of their entry."""
    entry = build_config_entry(boiler=1)
    entry.add_to_hass(hass)
    coordinator = build_coordinator(entry)
    entry.runtime_data = coordinator

    added: list = []
    await water_heater.async_setup_entry(hass, entry, added.extend)

    assert added
    assert all(entity.coordinator is coordinator for entity in added)
