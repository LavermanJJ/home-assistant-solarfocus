"""Verify entity descriptions against the components pysolarfocus actually exposes.

Every entity description names a `key` that is read off a pysolarfocus component at
runtime via `getattr`. If the component for a given Solarfocus system does not carry
that attribute, the entity is still created and every coordinator refresh raises
`AttributeError` -- see issue #163, where the buffer `external_*` sensors were declared
for all systems although `TherminatorBuffer` does not have them.

These tests walk every description in every platform and assert the attribute exists
for each system the description is not explicitly excluded from.
"""

import pytest
from pysolarfocus import ApiVersions, SolarfocusAPI, Systems

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
    BIOMASS_BOILER_COMPONENT,
    BOILER_COMPONENT,
    BUFFER_COMPONENT,
    FRESH_WATER_MODULE_COMPONENT,
    HEAT_PUMP_COMPONENT,
    HEATING_CIRCUIT_COMPONENT,
    PHOTOVOLTAIC_COMPONENT,
    SOLAR_COMPONENT,
)

# Entity description list -> the SolarfocusAPI attribute it is read from.
# Mirrors the wiring in each platform's async_setup_entry.
DESCRIPTION_LISTS = [
    (sensor.HEATING_CIRCUIT_SENSOR_TYPES, HEATING_CIRCUIT_COMPONENT),
    (sensor.BUFFER_SENSOR_TYPES, BUFFER_COMPONENT),
    (sensor.BOILER_SENSOR_TYPES, BOILER_COMPONENT),
    (sensor.HEATPUMP_SENSOR_TYPES, HEAT_PUMP_COMPONENT),
    (sensor.PHOTOVOLTAIC_SENSOR_TYPES, PHOTOVOLTAIC_COMPONENT),
    (sensor.BIOMASS_BOILER_SENSOR_TYPES, BIOMASS_BOILER_COMPONENT),
    (sensor.SOLAR_SENSOR_TYPES, SOLAR_COMPONENT),
    (sensor.FRESH_WATER_MODULE_SENSOR_TYPES, FRESH_WATER_MODULE_COMPONENT),
    (number.HEATING_CIRCUIT_NUMBER_TYPES, HEATING_CIRCUIT_COMPONENT),
    (number.BOILER_NUMBER_TYPES, BOILER_COMPONENT),
    (select.HEATPUMP_SELECT_TYPES, HEAT_PUMP_COMPONENT),
    (select.HEATING_CIRCUIT_SELECT_TYPES, HEATING_CIRCUIT_COMPONENT),
    (select.BOILER_SELECT_TYPES, BOILER_COMPONENT),
    (switch.HEATPUMP_SWITCH_TYPES, HEAT_PUMP_COMPONENT),
    (button.BOILER_BUTTON_TYPES, BOILER_COMPONENT),
    (binary_sensor.HEATING_CIRCUIT_BINARY_SENSOR_TYPES, HEATING_CIRCUIT_COMPONENT),
    (binary_sensor.BUFFER_BINARY_SENSOR_TYPES, BUFFER_COMPONENT),
    (binary_sensor.HEATPUMP_BINARY_SENSOR_TYPES, HEAT_PUMP_COMPONENT),
    (binary_sensor.BIOMASS_BOILER_BINARY_SENSOR_TYPES, BIOMASS_BOILER_COMPONENT),
    (binary_sensor.PHOTOVOLTAIC_BINARY_SENSOR_TYPES, PHOTOVOLTAIC_COMPONENT),
    (binary_sensor.FRESH_WATER_MODULE_BINARY_SENSOR_TYPES, FRESH_WATER_MODULE_COMPONENT),
]

# water_heater and climate are composite entities: their description key is only a
# label ("domestic_hot_water", "thermostat") and the registers they touch are named
# inline in the property implementations. Those names are listed here so they get the
# same coverage as the key-based platforms.
COMPOSITE_ITEMS = [
    (
        BOILER_COMPONENT,
        water_heater.WATER_HEATER_TYPES,
        ["temperature", "target_temperature", "mode", "holding_mode"],
    ),
    (
        HEATING_CIRCUIT_COMPONENT,
        climate.CLIMATE_TYPES,
        ["cooling", "target_supply_temperature", "supply_temperature", "state", "mode"],
    ),
]

# Highest version the installed pysolarfocus knows about, so that no register is
# hidden behind a version gate while checking.
LATEST_API_VERSION = list(ApiVersions)[-1]


def _component(system: Systems, component: str):
    """Return the pysolarfocus component instance for a system."""
    api = SolarfocusAPI(
        ip="127.0.0.1", system=system, api_version=LATEST_API_VERSION
    )
    comp = getattr(api, component)
    return comp[0] if isinstance(comp, list) else comp


def _cases():
    """Yield (system, component, key) for every description/system combination."""
    for descriptions, component in DESCRIPTION_LISTS:
        for description in descriptions:
            unsupported = description.unsupported_systems or []
            for system in Systems:
                if system in unsupported:
                    continue
                yield pytest.param(
                    system,
                    component,
                    description.key,
                    id=f"{system.name}-{component}-{description.key}",
                )


@pytest.mark.parametrize(("system", "component", "key"), list(_cases()))
def test_description_key_exists_on_component(
    system: Systems, component: str, key: str
) -> None:
    """Every entity key must exist on the component for every supported system."""
    obj = _component(system, component)
    assert hasattr(obj, key), (
        f"{type(obj).__name__} (system {system.name}) has no attribute '{key}'. "
        f"Either the key is wrong or the description needs "
        f"unsupported_systems=[Systems.{system.name}]."
    )


def _composite_cases():
    """Yield (system, component, item) for the composite entities."""
    for component, descriptions, items in COMPOSITE_ITEMS:
        unsupported = {
            s for d in descriptions for s in (d.unsupported_systems or [])
        }
        for system in Systems:
            if system in unsupported:
                continue
            for item in items:
                yield pytest.param(
                    system, component, item, id=f"{system.name}-{component}-{item}"
                )


@pytest.mark.parametrize(("system", "component", "item"), list(_composite_cases()))
def test_composite_entity_item_exists_on_component(
    system: Systems, component: str, item: str
) -> None:
    """Registers read inline by water_heater/climate must exist too."""
    obj = _component(system, component)
    assert hasattr(obj, item), (
        f"{type(obj).__name__} (system {system.name}) has no attribute '{item}'"
    )


def test_buffer_external_sensors_excluded_for_therminator_buffer() -> None:
    """Regression test for #163.

    THERMINATOR and ECOTOP use TherminatorBuffer, which has no external_* registers.
    """
    external = [
        d
        for d in sensor.BUFFER_SENSOR_TYPES
        if d.key.startswith("external_")
    ]
    assert external, "expected external_* buffer sensors to exist"

    for description in external:
        assert Systems.THERMINATOR in (description.unsupported_systems or [])
        assert Systems.ECOTOP in (description.unsupported_systems or [])


def test_buffer_x35_excluded_where_missing() -> None:
    """x35_temperature only exists on TherminatorBuffer, not on the plain Buffer."""
    description = next(
        d for d in sensor.BUFFER_SENSOR_TYPES if d.key == "x35_temperature"
    )
    unsupported = description.unsupported_systems or []
    for system in (Systems.VAMPAIR, Systems.PELLETELEGANCE, Systems.OCTOPLUS):
        assert system in unsupported


@pytest.mark.parametrize("system", list(Systems), ids=lambda s: s.name)
def test_no_key_is_described_twice_for_one_system(system: Systems) -> None:
    """One system may only ever reach one description per key.

    A description list is allowed to carry the same key more than once - the
    biomass boiler door is described twice because register 2405 is reported
    the other way round on a therminator than on an EcoTop. What the duplicates
    must not do is survive the system filter together: the key is half of the
    `unique_id`, so Home Assistant would create the first entity and drop the
    second, with nothing to say which of the two it kept.
    """
    for descriptions, component in DESCRIPTION_LISTS:
        reached = [
            description.key
            for description in descriptions
            if system not in (description.unsupported_systems or [])
        ]
        duplicates = {key for key in reached if reached.count(key) > 1}
        assert not duplicates, (
            f"{component} describes {sorted(duplicates)} more than once for "
            f"system {system.name}; only one of them can become an entity."
        )


# Register -> the one system the register document grants it to. The document
# names each of these after a single system: "Kesselbetriebsart therminator",
# "Speichertemperatur Oben octoplus", "Stueckholz therminator". Register 2410 is
# the octoplus buffer bottom, and on the other Sigmatek boilers the return flow
# temperature - a different measurement that wants its own entity, not this one.
SINGLE_SYSTEM_BIOMASS_REGISTERS = [
    ("boiler_operating_mode", Systems.THERMINATOR),
    ("log_wood", Systems.THERMINATOR),
    ("octoplus_buffer_temperature_top", Systems.OCTOPLUS),
    ("octoplus_buffer_temperature_bottom", Systems.OCTOPLUS),
]


@pytest.mark.parametrize(("key", "supported"), SINGLE_SYSTEM_BIOMASS_REGISTERS)
def test_single_system_biomass_registers_reach_only_that_system(
    key: str, supported: Systems
) -> None:
    """Regression test for #217.

    These four were excluded from the vampair and the EcoTop and given to
    everything else, which handed a pellet boiler a log wood register and a
    therminator two buffer temperatures its controller does not have.
    """
    description = next(
        d for d in sensor.BIOMASS_BOILER_SENSOR_TYPES if d.key == key
    )
    unsupported = description.unsupported_systems or []

    assert supported not in unsupported
    for system in Systems:
        if system is not supported:
            assert system in unsupported, (
                f"{key} is documented for {supported.name} only, but reaches "
                f"{system.name}."
            )
