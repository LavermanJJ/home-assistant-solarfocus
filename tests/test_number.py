"""Test the Solarfocus number entities."""

from aiosolarfocus import ApiVersion, ComponentId, Systems
import pytest

from custom_components.solarfocus.const import (
    BIOMASS_BOILER_COMPONENT,
    BIOMASS_BOILER_COMPONENT_PREFIX,
    HEAT_PUMP_COMPONENT,
    HEAT_PUMP_COMPONENT_PREFIX,
    PHOTOVOLTAIC_COMPONENT,
    PHOTOVOLTAIC_COMPONENT_PREFIX,
)
from custom_components.solarfocus.entity import create_description, supported_entities
from custom_components.solarfocus.number import (
    BIOMASS_BOILER_NUMBER_TYPES,
    HEATPUMP_NUMBER_TYPES,
    PHOTOVOLTAIC_NUMBER_TYPES,
    SolarfocusNumberEntity,
)

from .conftest import build_client, build_config_entry, build_coordinator


def _entities(api_version: str) -> list[str]:
    """Return the photovoltaic numbers an entry on this firmware would build."""
    entry = build_config_entry(api_version=api_version, photovoltaic=True)
    coordinator = build_coordinator(entry, build_client(entry))

    entities = [
        SolarfocusNumberEntity(
            coordinator,
            create_description(
                PHOTOVOLTAIC_COMPONENT,
                PHOTOVOLTAIC_COMPONENT_PREFIX,
                "",
                description,
            ),
        )
        for description in PHOTOVOLTAIC_NUMBER_TYPES
    ]

    return [
        entity.entity_description.item
        for entity in supported_entities(entry, entities)
    ]


def test_photovoltaic_numbers_match_library_holding_registers():
    """Every number entity has to map to a writable value of the library."""
    entry = build_config_entry(
        api_version=ApiVersion.V_26_020.label, photovoltaic=True
    )
    photovoltaic = build_client(entry).of(ComponentId.PHOTOVOLTAIC)[0]

    for description in PHOTOVOLTAIC_NUMBER_TYPES:
        item = description.item or description.key
        assert photovoltaic.supports(item)
        # A number entity writes, so the register has to take a write - which
        # the library says outright rather than leaving to be inferred from
        # which block the register is in.
        assert photovoltaic.info(item).writable


def test_photovoltaic_number_keys_and_names():
    """Entity keys and translation keys are prefixed with the component."""
    description = create_description(
        PHOTOVOLTAIC_COMPONENT,
        PHOTOVOLTAIC_COMPONENT_PREFIX,
        "",
        PHOTOVOLTAIC_NUMBER_TYPES[0],
    )

    assert description.item == "smart_meter"
    assert description.key == "pv_smart_meter"
    assert description.translation_key == "pv_smart_meter"
    # The name comes from the translation of the key now, and the photovoltaic
    # component exists once, so there is no index to substitute into it
    assert description.device_idx == ""
    assert description.component == PHOTOVOLTAIC_COMPONENT


def test_photovoltaic_numbers_available_since_21_140():
    """Registers 33407-33409 are available for all supported api versions."""
    assert _entities("21.140") == ["smart_meter", "photovoltaic", "grid_im_export"]


def test_hems_target_electrical_power_requires_26_020():
    """Register 33415 has been introduced with api version 26.020."""
    assert "hems_target_electrical_power" not in _entities("25.030")
    assert "hems_target_electrical_power" in _entities("26.020")


def _heatpump_entities(api_version: str) -> list[str]:
    """Return the heat pump numbers an entry on this firmware would build."""
    entry = build_config_entry(api_version=api_version, heatpump=True)
    coordinator = build_coordinator(entry, build_client(entry))

    entities = [
        SolarfocusNumberEntity(
            coordinator,
            create_description(
                HEAT_PUMP_COMPONENT,
                HEAT_PUMP_COMPONENT_PREFIX,
                "",
                description,
            ),
        )
        for description in HEATPUMP_NUMBER_TYPES
    ]

    return [
        entity.entity_description.item
        for entity in supported_entities(entry, entities)
    ]


def test_heatpump_numbers_match_library_holding_registers():
    """Every number entity has to map to a writable value of the library."""
    entry = build_config_entry(api_version=ApiVersion.V_26_020.label, heatpump=True)
    heat_pump = build_client(entry).of(ComponentId.HEAT_PUMP)[0]

    for description in HEATPUMP_NUMBER_TYPES:
        item = description.item or description.key
        assert heat_pump.supports(item)
        assert heat_pump.info(item).writable


def test_heatpump_number_keys_and_names():
    """Entity keys and translation keys are prefixed with the component."""
    description = create_description(
        HEAT_PUMP_COMPONENT,
        HEAT_PUMP_COMPONENT_PREFIX,
        "",
        HEATPUMP_NUMBER_TYPES[0],
    )

    assert description.item == "outdoor_temperature_external"
    assert description.key == "hp_outdoor_temperature_external"
    assert description.translation_key == "hp_outdoor_temperature_external"
    assert description.device_idx == ""
    assert description.component == HEAT_PUMP_COMPONENT


def test_outdoor_temperature_external_available_since_20_110():
    """Register 33406 is available for all supported api versions.

    20.110 is both the version that introduced it and the oldest the library
    knows, so there is no firmware here that has to do without it.
    """
    assert _heatpump_entities("20.110") == ["outdoor_temperature_external"]
    assert _heatpump_entities("26.020") == ["outdoor_temperature_external"]


def _biomass_boiler_entities(api_version: str, system: Systems) -> list[str]:
    """Return the biomass boiler numbers an entry on this system would build."""
    entry = build_config_entry(
        system, api_version=api_version, biomassboiler=True
    )
    coordinator = build_coordinator(entry, build_client(entry))

    entities = [
        SolarfocusNumberEntity(
            coordinator,
            create_description(
                BIOMASS_BOILER_COMPONENT,
                BIOMASS_BOILER_COMPONENT_PREFIX,
                "",
                description,
            ),
        )
        for description in BIOMASS_BOILER_NUMBER_TYPES
    ]

    return [
        entity.entity_description.item
        for entity in supported_entities(entry, entities)
    ]


def test_biomass_boiler_numbers_match_library_holding_registers():
    """Every number entity has to map to a writable value of the library."""
    entry = build_config_entry(
        Systems.PELLETELEGANCE,
        api_version=ApiVersion.V_26_020.label,
        biomassboiler=True,
    )
    biomass_boiler = build_client(entry).of(ComponentId.BIOMASS_BOILER)[0]

    for description in BIOMASS_BOILER_NUMBER_TYPES:
        item = description.item or description.key
        assert biomass_boiler.supports(item)
        assert biomass_boiler.info(item).writable


def test_biomass_boiler_number_keys_and_names():
    """Entity keys and translation keys are prefixed with the component."""
    description = create_description(
        BIOMASS_BOILER_COMPONENT,
        BIOMASS_BOILER_COMPONENT_PREFIX,
        "",
        BIOMASS_BOILER_NUMBER_TYPES[0],
    )

    assert description.item == "outdoor_temperature_external"
    assert description.key == "bb_outdoor_temperature_external"
    assert description.translation_key == "bb_outdoor_temperature_external"
    assert description.device_idx == ""
    assert description.component == BIOMASS_BOILER_COMPONENT


@pytest.mark.parametrize(
    "system",
    [
        Systems.THERMINATOR,
        Systems.ECOTOP,
        Systems.PELLETELEGANCE,
        Systems.OCTOPLUS,
    ],
)
def test_outdoor_temperature_external_reaches_biomass_systems(system: Systems):
    """Holding 33406 belongs to both components, so both have to offer it.

    The heat pump maps it at offset 2 from 33404 and the biomass boiler at
    offset 6 from 33400, and the config flow makes the heat pump a vampair and
    the biomass boiler everything else - so wiring the number to the heat pump
    alone would leave every biomass owner with the raw modbus write this is
    meant to replace.
    """
    assert _biomass_boiler_entities("23.010", system) == [
        "outdoor_temperature_external"
    ]


def test_outdoor_temperature_external_requires_23_010_on_biomass():
    """The boiler's half of 33406 arrived later than the heat pump's."""
    assert "outdoor_temperature_external" not in _biomass_boiler_entities(
        "22.090", Systems.PELLETELEGANCE
    )
