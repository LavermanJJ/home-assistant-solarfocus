"""Invariants that sensor entity descriptions have to satisfy.

Home Assistant validates some device_class/state_class combinations when an entity
is added and logs a warning for the invalid ones (see issue #136). Asserting the
invariant here catches it at build time instead of in a user's log.
"""

import pytest
from homeassistant.components.sensor import SensorDeviceClass

from custom_components.solarfocus import sensor

ALL_SENSOR_TYPES = [
    *sensor.HEATING_CIRCUIT_SENSOR_TYPES,
    *sensor.BUFFER_SENSOR_TYPES,
    *sensor.BOILER_SENSOR_TYPES,
    *sensor.HEATPUMP_SENSOR_TYPES,
    *sensor.PHOTOVOLTAIC_SENSOR_TYPES,
    *sensor.BIOMASS_BOILER_SENSOR_TYPES,
    *sensor.SOLAR_SENSOR_TYPES,
    *sensor.FRESH_WATER_MODULE_SENSOR_TYPES,
]

ENUM_SENSOR_TYPES = [
    d for d in ALL_SENSOR_TYPES if d.device_class is SensorDeviceClass.ENUM
]


def test_enum_sensors_exist() -> None:
    """Guard the fixtures above against silently matching nothing."""
    assert ENUM_SENSOR_TYPES


@pytest.mark.parametrize(
    "description", ENUM_SENSOR_TYPES, ids=lambda d: d.key
)
def test_enum_sensor_has_no_state_class(description) -> None:
    """An enum is not a measurement, so it must not declare a state class.

    Core rejects the combination with:
        "is using state class 'measurement' which is impossible considering
         device class ('enum') it is using; expected None"
    """
    assert description.state_class is None, (
        f"sensor '{description.key}' declares device_class=ENUM together with "
        f"state_class={description.state_class!r}; enum sensors must not set one."
    )


@pytest.mark.parametrize(
    "description", ENUM_SENSOR_TYPES, ids=lambda d: d.key
)
def test_enum_sensor_declares_options(description) -> None:
    """An enum sensor without options renders every state as a raw value."""
    assert description.options, f"sensor '{description.key}' declares no options"


@pytest.mark.parametrize(
    "description", ALL_SENSOR_TYPES, ids=lambda d: d.key
)
def test_non_enum_sensor_declares_no_options(description) -> None:
    """Core raises if options are provided without the enum device class."""
    if description.device_class is not SensorDeviceClass.ENUM:
        assert not description.options, (
            f"sensor '{description.key}' provides options but its device class is "
            f"{description.device_class!r} instead of 'enum'"
        )
