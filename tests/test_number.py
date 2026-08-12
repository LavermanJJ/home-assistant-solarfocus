"""Test the Solarfocus number entities."""

from types import SimpleNamespace

from pysolarfocus import ApiVersions, Systems
from pysolarfocus.components.photovoltaic import Photovoltaic

from custom_components.solarfocus.const import (
    PHOTOVOLTAIC_COMPONENT,
    PHOTOVOLTAIC_COMPONENT_PREFIX,
    PHOTOVOLTAIC_PREFIX,
)
from custom_components.solarfocus.entity import (
    create_description,
    filterVersionAndSystem,
)
from custom_components.solarfocus.number import PHOTOVOLTAIC_NUMBER_TYPES
from homeassistant.const import CONF_API_VERSION


def _config_entry(api_version: str):
    """Create a minimal config entry stub for entity filtering."""
    return SimpleNamespace(
        options={CONF_API_VERSION: api_version},
        data={"system": Systems.VAMPAIR},
    )


def _entities(api_version: str):
    """Create the photovoltaic number entities for the given api version."""
    entities = [
        SimpleNamespace(
            entity_description=create_description(
                PHOTOVOLTAIC_PREFIX,
                PHOTOVOLTAIC_COMPONENT,
                PHOTOVOLTAIC_COMPONENT_PREFIX,
                "",
                description,
            )
        )
        for description in PHOTOVOLTAIC_NUMBER_TYPES
    ]
    return [
        entity.entity_description.item
        for entity in filterVersionAndSystem(_config_entry(api_version), entities)
    ]


def test_photovoltaic_numbers_match_library_holding_registers():
    """Every number entity has to map to a writable value of the library."""
    photovoltaic = Photovoltaic(api_version=ApiVersions.V_26_020)

    for description in PHOTOVOLTAIC_NUMBER_TYPES:
        assert hasattr(photovoltaic, description.key)


def test_photovoltaic_number_keys_and_names():
    """Entity keys and translation keys are prefixed with the component."""
    description = create_description(
        PHOTOVOLTAIC_PREFIX,
        PHOTOVOLTAIC_COMPONENT,
        PHOTOVOLTAIC_COMPONENT_PREFIX,
        "",
        PHOTOVOLTAIC_NUMBER_TYPES[0],
    )

    assert description.item == "smart_meter"
    assert description.key == "pv_smart_meter"
    assert description.translation_key == "pv_smart_meter"
    assert description.name == "Photovoltaic smart meter"
    assert description.component == PHOTOVOLTAIC_COMPONENT


def test_photovoltaic_numbers_available_since_21_140():
    """Registers 33407-33409 are available for all supported api versions."""
    assert _entities("21.140") == ["smart_meter", "photovoltaic", "grid_im_export"]


def test_hems_target_electrical_power_requires_26_020():
    """Register 33415 has been introduced with api version 26.020."""
    assert "hems_target_electrical_power" not in _entities("25.030")
    assert "hems_target_electrical_power" in _entities("26.020")
