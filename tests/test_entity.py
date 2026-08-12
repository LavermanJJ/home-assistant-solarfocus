"""Test the Solarfocus base entity."""

from unittest.mock import MagicMock

from pysolarfocus import ApiVersions
from pysolarfocus.components.photovoltaic import Photovoltaic

from custom_components.solarfocus.const import PHOTOVOLTAIC_COMPONENT
from custom_components.solarfocus.entity import (
    SolarfocusEntity,
    SolarfocusEntityDescription,
)


def _entity(photovoltaic: Photovoltaic) -> SolarfocusEntity:
    """Create an entity writing to the photovoltaic component."""
    coordinator = MagicMock()
    coordinator.api.photovoltaic = photovoltaic

    entity = SolarfocusEntity(
        coordinator,
        SolarfocusEntityDescription(
            key="grid_im_export",
            item="grid_im_export",
            component=PHOTOVOLTAIC_COMPONENT,
        ),
    )
    entity.async_write_ha_state = MagicMock()
    return entity


def test_set_native_value_writes_negative_value_as_twos_complement():
    """Negative values have to be written as unsigned words."""
    modbus = MagicMock()
    modbus.write_register.return_value = True
    photovoltaic = Photovoltaic(api_version=ApiVersions.V_26_020).initialize(modbus)
    # Don't let the read-back of the component overwrite the written value
    photovoltaic.update = MagicMock()

    _entity(photovoltaic)._set_native_value("grid_im_export", -500)

    modbus.write_register.assert_called_once_with(65036, 33409)
    # The entity keeps reporting the signed value
    assert photovoltaic.grid_im_export.scaled_value == -500


def test_set_native_value_writes_positive_value_unchanged():
    """Positive values are written as they are."""
    modbus = MagicMock()
    modbus.write_register.return_value = True
    photovoltaic = Photovoltaic(api_version=ApiVersions.V_26_020).initialize(modbus)
    # Don't let the read-back of the component overwrite the written value
    photovoltaic.update = MagicMock()

    _entity(photovoltaic)._set_native_value("grid_im_export", 500)

    modbus.write_register.assert_called_once_with(500, 33409)
    assert photovoltaic.grid_im_export.scaled_value == 500
