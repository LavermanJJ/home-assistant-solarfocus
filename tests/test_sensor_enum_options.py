"""Keep enum sensor `options` in sync with the translated states.

For a sensor with `device_class=ENUM`, core raises

    ValueError: Sensor <entity_id> provides state value '<x>',
                which is not in the list of options provided

whenever the device reports a value outside `options`, and the entity then stops
updating entirely (issue #165).

A translated state is the integration asserting "the device can report this", so
every translated state must appear in `options`. The reverse is not required: an
option without a translation merely renders as a raw number.
"""

import json
import pathlib

import pytest

from custom_components.solarfocus import sensor
from custom_components.solarfocus.const import (
    BIOMASS_BOILER_COMPONENT_PREFIX,
    BOILER_COMPONENT_PREFIX,
    BUFFER_COMPONENT_PREFIX,
    FRESH_WATER_MODULE_COMPONENT_PREFIX,
    HEAT_PUMP_COMPONENT_PREFIX,
    HEATING_CIRCUIT_COMPONENT_PREFIX,
    PHOTOVOLTAIC_COMPONENT_PREFIX,
    SOLAR_COMPONENT_PREFIX,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import HomeAssistant

from .conftest import build_config_entry

COMPONENT_DIR = pathlib.Path(sensor.__file__).parent

# Entity list -> the translation-key prefix create_description() builds keys with.
SENSOR_TYPES_BY_PREFIX = [
    (sensor.HEATING_CIRCUIT_SENSOR_TYPES, HEATING_CIRCUIT_COMPONENT_PREFIX),
    (sensor.BUFFER_SENSOR_TYPES, BUFFER_COMPONENT_PREFIX),
    (sensor.BOILER_SENSOR_TYPES, BOILER_COMPONENT_PREFIX),
    (sensor.HEATPUMP_SENSOR_TYPES, HEAT_PUMP_COMPONENT_PREFIX),
    (sensor.PHOTOVOLTAIC_SENSOR_TYPES, PHOTOVOLTAIC_COMPONENT_PREFIX),
    (sensor.BIOMASS_BOILER_SENSOR_TYPES, BIOMASS_BOILER_COMPONENT_PREFIX),
    (sensor.SOLAR_SENSOR_TYPES, SOLAR_COMPONENT_PREFIX),
    (sensor.FRESH_WATER_MODULE_SENSOR_TYPES, FRESH_WATER_MODULE_COMPONENT_PREFIX),
]


def _translations(filename: str) -> dict:
    with (COMPONENT_DIR / filename).open(encoding="utf-8") as fh:
        return json.load(fh)["entity"]["sensor"]


def _cases():
    """Yield (translation_key, options) for every enum sensor."""
    for descriptions, prefix in SENSOR_TYPES_BY_PREFIX:
        for description in descriptions:
            if description.device_class is not SensorDeviceClass.ENUM:
                continue
            yield pytest.param(
                f"{prefix}_{description.key}",
                description.options,
                id=f"{prefix}_{description.key}",
            )


CASES = list(_cases())


@pytest.mark.parametrize(
    "filename", ["strings.json", "translations/en.json", "translations/de.json"]
)
@pytest.mark.parametrize(("translation_key", "options"), CASES)
def test_translated_states_are_valid_options(
    filename: str, translation_key: str, options: list[str]
) -> None:
    """Every translated state must be an accepted option.

    Both are the state as Home Assistant holds it, a string, so they compare
    directly: the keys of the translation are the options of the sensor.
    """
    entity = _translations(filename).get(translation_key)
    if entity is None or "state" not in entity:
        pytest.skip(f"{translation_key} has no states in {filename}")

    missing = sorted(set(entity["state"]) - set(options), key=int)

    assert not missing, (
        f"{filename}: '{translation_key}' translates state(s) {missing} that are not "
        f"in its options list. A device reporting one of these raises ValueError and "
        f"the entity stops updating."
    )


@pytest.mark.parametrize(("translation_key", "options"), CASES)
def test_options_are_strings(translation_key: str, options: list[str]) -> None:
    """The options of an enum sensor are states, and a state is a string.

    Listing the raw numbers instead leaves the state of the sensor outside of its
    own options, see `test_the_state_of_an_enum_sensor_is_one_of_its_options`.
    """
    assert options
    assert [option for option in options if not isinstance(option, str)] == []


async def test_the_state_of_an_enum_sensor_is_one_of_its_options(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """Regression test for #193.

    The automation editor offers the options of the sensor to compare its state
    against, and inserts the option that was picked into the condition. While the
    options were numbers and the state was the string of one, no condition built
    that way could ever match.
    """
    api.heatpump.vampair_state.scaled_value = 3
    entry = build_config_entry(heatpump=True)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.solarfocus_heat_pump_vampair_state")

    assert state.state == "3"
    assert state.state in state.attributes["options"]


def test_cases_cover_the_known_enum_sensors() -> None:
    """Guard the parametrization against silently matching nothing."""
    keys = {case.values[0] for case in CASES}
    assert {"bb_message_number", "bo_single_charge", "bo_circulation"} <= keys


def test_biomass_message_number_covers_acknowledged_range() -> None:
    """Regression test for #165: the 200-range and 2010 must be selectable."""
    description = next(
        d for d in sensor.BIOMASS_BOILER_SENSOR_TYPES if d.key == "message_number"
    )
    for value in ("201", "287", "2010"):
        assert value in description.options


def test_single_charge_allows_locked_state() -> None:
    """`-1` (Locked) is translated for single_charge, so it must be an option."""
    description = next(
        d for d in sensor.BOILER_SENSOR_TYPES if d.key == "single_charge"
    )
    assert "-1" in description.options
