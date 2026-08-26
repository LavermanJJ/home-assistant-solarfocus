"""Test the Solarfocus number entities."""

from aiosolarfocus import ApiVersion, ComponentId

from custom_components.solarfocus.const import (
    PHOTOVOLTAIC_COMPONENT,
    PHOTOVOLTAIC_COMPONENT_PREFIX,
)
from custom_components.solarfocus.entity import create_description, supported_entities
from custom_components.solarfocus.number import (
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
