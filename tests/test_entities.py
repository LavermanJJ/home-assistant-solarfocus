"""Test what the entity classes read from and write to the device.

Every entity reads its value through `_get_native_value` and writes it through
`_set_native_value`, which address a pysolarfocus component by name and index.
These tests pin the mapping down for one entity of every platform.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.solarfocus.binary_sensor import (
    SolarfocusBinarySensorEntity,
    SolarfocusBinarySensorEntityDescription,
)
from custom_components.solarfocus.button import (
    BOILER_BUTTON_TYPES,
    SolarfocusButtonEntity,
)
from custom_components.solarfocus.const import (
    BOILER_COMPONENT,
    BOILER_COMPONENT_PREFIX,
    BOILER_PREFIX,
    CONF_BOILER,
    DOMAIN,
    HEAT_PUMP_COMPONENT,
    HEAT_PUMP_COMPONENT_PREFIX,
    HEATING_CIRCUIT_COMPONENT,
    HEATING_CIRCUIT_COMPONENT_PREFIX,
    MANUFACTURER,
)
from custom_components.solarfocus.entity import create_description
from custom_components.solarfocus.number import (
    BOILER_NUMBER_TYPES,
    SolarfocusNumberEntity,
)
from custom_components.solarfocus.select import (
    HEATPUMP_SELECT_TYPES,
    SolarfocusSelectEntity,
)
from custom_components.solarfocus.sensor import BOILER_SENSOR_TYPES, SolarfocusSensor
from custom_components.solarfocus.switch import (
    HEATPUMP_SWITCH_TYPES,
    OFF,
    ON,
    SolarfocusSwitchEntity,
)
from custom_components.solarfocus.water_heater import (
    HA_DISPLAY_MODE_ALWAYS_ON,
    HA_DISPLAY_MODE_BLOCKWISE,
    SOLARFOCUS_MODE_ALWAYS_OFF,
    SOLARFOCUS_MODE_ALWAYS_ON,
    SOLARFOCUS_MODE_BLOCKWISE,
    SOLARFOCUS_TEMP_WATER_MAX,
    SOLARFOCUS_TEMP_WATER_MIN,
    WATER_HEATER_TYPES,
    SolarfocusWaterHeaterEntity,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, UnitOfTemperature

from .conftest import build_config_entry, build_coordinator


def _make(entity_class, description, component, component_prefix, idx="1"):
    """Create an entity of the given class on a mocked coordinator."""
    coordinator = build_coordinator(build_config_entry())
    entity = entity_class(
        coordinator,
        create_description(component, component_prefix, idx, description),
    )
    entity.async_write_ha_state = MagicMock()
    return entity


@pytest.fixture(name="boiler_water_heater")
def boiler_water_heater_fixture() -> SolarfocusWaterHeaterEntity:
    """Return the water heater of the second boiler."""
    return _make(
        SolarfocusWaterHeaterEntity,
        WATER_HEATER_TYPES[0],
        BOILER_COMPONENT,
        BOILER_COMPONENT_PREFIX,
        idx="2",
    )


# --- base entity ------------------------------------------------------------


def test_unique_id_combines_the_entry_id_and_the_key() -> None:
    """The unique id has to stay stable, it identifies the entity in the registry.

    The entry id, not the title: the title is renamed from the UI, and an entity
    that changes its unique id is a new entity to Home Assistant.
    """
    entity = _make(
        SolarfocusSensor,
        BOILER_SENSOR_TYPES[0],
        BOILER_COMPONENT,
        BOILER_COMPONENT_PREFIX,
    )
    entry_id = entity.coordinator._entry.entry_id

    assert entity.unique_id == f"{entry_id}_bo1_{BOILER_SENSOR_TYPES[0].key}"
    assert entity.translation_key == f"bo_{BOILER_SENSOR_TYPES[0].key}"


def test_device_info_puts_the_entity_on_its_own_component() -> None:
    """A boiler entity belongs to a boiler, not to the whole heating system.

    The identifier is always indexed, `..._bo1`, even where the name of the
    device drops the index - so raising the count of a component renames its
    first device rather than orphaning it.
    """
    entry = build_config_entry()
    coordinator = build_coordinator(entry)
    coordinator.hub_device_id = "hub"
    entity = SolarfocusSensor(
        coordinator,
        create_description(
                        BOILER_COMPONENT,
            BOILER_COMPONENT_PREFIX,
            "2",
            BOILER_SENSOR_TYPES[0],
        ),
    )

    device_info = entity.device_info

    assert device_info["identifiers"] == {(DOMAIN, f"{entry.entry_id}_bo2")}
    assert device_info["translation_key"] == CONF_BOILER
    assert device_info["translation_placeholders"] == {"idx": " 2"}
    assert device_info["model"] == BOILER_PREFIX
    assert device_info["manufacturer"] == MANUFACTURER
    # Every component hangs off the controller
    assert device_info["via_device_id"] == "hub"


def test_a_component_that_exists_once_is_not_numbered() -> None:
    """There is one heat pump, so its device is `Heat pump`, not `Heat pump 1`."""
    coordinator = build_coordinator(build_config_entry())
    coordinator.hub_device_id = "hub"
    entity = SolarfocusSwitchEntity(
        coordinator,
        create_description(
                        HEAT_PUMP_COMPONENT,
            HEAT_PUMP_COMPONENT_PREFIX,
            "",
            HEATPUMP_SWITCH_TYPES[0],
        ),
    )

    assert entity.device_info["translation_placeholders"] == {"idx": ""}


def test_device_info_values_are_strings() -> None:
    """The device registry rejects anything else from 2026.12 on.

    `model` and `sw_version` used to be built as set literals, `{model}`, which
    Home Assistant reported as "passes a non-string value of type set as model to
    the device registry".
    """
    entity = _make(
        SolarfocusSensor,
        BOILER_SENSOR_TYPES[0],
        BOILER_COMPONENT,
        BOILER_COMPONENT_PREFIX,
    )

    device_info = entity.device_info

    for field in ("model", "manufacturer"):
        assert isinstance(device_info[field], str), (
            f"{field} is {type(device_info[field]).__name__}, not str"
        )


def test_entity_is_unavailable_after_a_failed_update() -> None:
    """A device that stopped answering must not keep reporting stale values."""
    entity = _make(
        SolarfocusSensor,
        BOILER_SENSOR_TYPES[0],
        BOILER_COMPONENT,
        BOILER_COMPONENT_PREFIX,
    )

    assert entity.available is True

    entity.coordinator.last_update_success = False

    assert entity.available is False


def test_indexed_components_are_addressed_by_position() -> None:
    """Boiler 2 is the second entry of the component list, not the second boiler id."""
    entity = _make(
        SolarfocusSensor,
        BOILER_SENSOR_TYPES[0],
        BOILER_COMPONENT,
        BOILER_COMPONENT_PREFIX,
        idx="3",
    )
    boilers = [MagicMock() for _ in range(3)]
    boilers[2].temperature.scaled_value = 55
    entity.coordinator.api.boilers = boilers

    assert entity._get_native_value("temperature") == 55


def test_components_without_an_index_are_read_directly() -> None:
    """The heat pump exists once, so it is not a list."""
    entity = _make(
        SolarfocusSwitchEntity,
        HEATPUMP_SWITCH_TYPES[0],
        HEAT_PUMP_COMPONENT,
        HEAT_PUMP_COMPONENT_PREFIX,
        idx="",
    )
    entity.coordinator.api.heatpump.evu_lock.scaled_value = 1

    assert entity._get_native_value("evu_lock") == 1


async def test_async_update_requests_a_coordinator_refresh() -> None:
    """Polling an entity refreshes the whole device."""
    entity = _make(
        SolarfocusSensor,
        BOILER_SENSOR_TYPES[0],
        BOILER_COMPONENT,
        BOILER_COMPONENT_PREFIX,
    )
    entity.coordinator.async_request_refresh = AsyncMock()

    await entity.async_update()

    entity.coordinator.async_request_refresh.assert_awaited_once()


async def test_entity_follows_the_coordinator_while_added() -> None:
    """The entity writes its state whenever the coordinator has new data."""
    entity = _make(
        SolarfocusSensor,
        BOILER_SENSOR_TYPES[0],
        BOILER_COMPONENT,
        BOILER_COMPONENT_PREFIX,
    )
    remove_listener = MagicMock()
    entity.coordinator.async_add_listener.return_value = remove_listener
    entity.async_on_remove = MagicMock()

    await entity.async_added_to_hass()

    entity.coordinator.async_add_listener.assert_called_once_with(
        entity.async_write_ha_state
    )
    # The listener is removed again when the entity goes away
    entity.async_on_remove.assert_called_once_with(remove_listener)


# --- sensor -----------------------------------------------------------------


def test_sensor_reports_the_component_value() -> None:
    """A sensor reads the item its description names."""
    description = BOILER_SENSOR_TYPES[0]
    entity = _make(
        SolarfocusSensor,
        description,
        BOILER_COMPONENT,
        BOILER_COMPONENT_PREFIX,
    )
    getattr(entity.coordinator.api.boilers[0], description.key).scaled_value = 42

    assert entity.native_value == 42


# --- binary sensor ----------------------------------------------------------


@pytest.mark.parametrize(
    ("on_state", "value", "expected"),
    [("1", 1, True), ("1", 0, False), ("0", 0, True), ("0", 1, False)],
)
def test_binary_sensor_compares_against_its_on_state(
    on_state: str, value: int, expected: bool
) -> None:
    """Some binary sensors are active on 0 (a problem) and some on 1 (running)."""
    entity = _make(
        SolarfocusBinarySensorEntity,
        SolarfocusBinarySensorEntityDescription(key="pump", on_state=on_state),
        HEATING_CIRCUIT_COMPONENT,
        HEATING_CIRCUIT_COMPONENT_PREFIX,
    )
    entity.coordinator.api.heating_circuits[0].pump.scaled_value = value

    assert entity.is_on is expected


# --- number -----------------------------------------------------------------


async def test_number_writes_the_value() -> None:
    """Setting a number writes to the component it belongs to."""
    entity = _make(
        SolarfocusNumberEntity,
        BOILER_NUMBER_TYPES[0],
        BOILER_COMPONENT,
        BOILER_COMPONENT_PREFIX,
    )

    with patch.object(entity, "_set_native_value") as set_value:
        await entity.async_set_native_value(60)

    assert set_value.call_args_list == [(("target_temperature", 60),)]


def test_number_reads_the_value() -> None:
    """A number reports the current value of its item."""
    entity = _make(
        SolarfocusNumberEntity,
        BOILER_NUMBER_TYPES[0],
        BOILER_COMPONENT,
        BOILER_COMPONENT_PREFIX,
    )
    entity.coordinator.api.boilers[0].target_temperature.scaled_value = 55

    assert entity.native_value == 55


# --- select -----------------------------------------------------------------


async def test_select_writes_and_reports_the_option() -> None:
    """Selecting an option writes the raw value the device expects."""
    entity = _make(
        SolarfocusSelectEntity,
        HEATPUMP_SELECT_TYPES[0],
        HEAT_PUMP_COMPONENT,
        HEAT_PUMP_COMPONENT_PREFIX,
        idx="",
    )

    assert entity.options == HEATPUMP_SELECT_TYPES[0].solarfocus_options

    with patch.object(entity, "_set_native_value") as set_value:
        await entity.async_select_option("3")

    assert set_value.call_args_list == [(("smart_grid", "3"),)]

    entity.coordinator.api.heatpump.smart_grid.scaled_value = 3
    assert entity.current_option == "3"


# --- switch -----------------------------------------------------------------


async def test_switch_turns_the_lock_on_and_off() -> None:
    """The switch writes 1 and 0."""
    entity = _make(
        SolarfocusSwitchEntity,
        HEATPUMP_SWITCH_TYPES[0],
        HEAT_PUMP_COMPONENT,
        HEAT_PUMP_COMPONENT_PREFIX,
        idx="",
    )

    with patch.object(entity, "_set_native_value") as set_value:
        await entity.async_turn_on()
        await entity.async_turn_off()

    assert set_value.call_args_list == [
        (("evu_lock", ON),),
        (("evu_lock", OFF),),
    ]


def test_switch_reports_its_state() -> None:
    """The switch reads the same item it writes."""
    entity = _make(
        SolarfocusSwitchEntity,
        HEATPUMP_SWITCH_TYPES[0],
        HEAT_PUMP_COMPONENT,
        HEAT_PUMP_COMPONENT_PREFIX,
        idx="",
    )
    entity.coordinator.api.heatpump.evu_lock.scaled_value = 1

    assert entity.is_on == 1


# --- button -----------------------------------------------------------------


@pytest.mark.parametrize("description", BOILER_BUTTON_TYPES, ids=lambda d: d.key)
async def test_button_triggers_its_item(description) -> None:
    """Pressing a button writes 1 to the register it names.

    A number, not a bool: the sensor of the same name reads the register back and
    turns it into a state, and "True" is not one of the states it accepts. Since
    `True == 1`, the type is what the assertion is about.
    """
    entity = _make(
        SolarfocusButtonEntity,
        description,
        BOILER_COMPONENT,
        BOILER_COMPONENT_PREFIX,
    )

    with patch.object(entity, "_set_native_value") as set_value:
        await entity.async_press()

    assert set_value.call_args_list == [((description.key, 1),)]
    assert not isinstance(set_value.call_args.args[1], bool)


# --- water heater -----------------------------------------------------------


def test_water_heater_reports_temperatures(boiler_water_heater) -> None:
    """The water heater reads the boiler it belongs to."""
    boiler = boiler_water_heater.coordinator.api.boilers[1]
    boiler.temperature.scaled_value = 48.5
    boiler.target_temperature.scaled_value = 55.0

    assert boiler_water_heater.current_temperature == 48.5
    assert boiler_water_heater.target_temperature == 55.0
    assert boiler_water_heater.temperature_unit == UnitOfTemperature.CELSIUS
    assert boiler_water_heater.min_temp == SOLARFOCUS_TEMP_WATER_MIN
    assert boiler_water_heater.max_temp == SOLARFOCUS_TEMP_WATER_MAX


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (SOLARFOCUS_MODE_ALWAYS_OFF, STATE_OFF),
        (SOLARFOCUS_MODE_ALWAYS_ON, HA_DISPLAY_MODE_ALWAYS_ON),
        (SOLARFOCUS_MODE_BLOCKWISE, HA_DISPLAY_MODE_BLOCKWISE),
    ],
)
def test_water_heater_maps_the_device_mode(
    boiler_water_heater, mode: int, expected: str
) -> None:
    """The numeric device mode is translated into the displayed operation."""
    boiler_water_heater.coordinator.api.boilers[1].mode.scaled_value = mode

    assert boiler_water_heater.current_operation == expected


def test_water_heater_operation_list_covers_every_device_mode(
    boiler_water_heater,
) -> None:
    """Every mode the device can report can also be selected."""
    assert set(boiler_water_heater.operation_list) == {
        STATE_OFF,
        HA_DISPLAY_MODE_ALWAYS_ON,
        HA_DISPLAY_MODE_BLOCKWISE,
        "Montag - Sonntag",
        "Tageweise",
    }


async def test_water_heater_sets_the_target_temperature(boiler_water_heater) -> None:
    """Setting the temperature writes the boiler target temperature."""
    with patch.object(boiler_water_heater, "_set_native_value") as set_value:
        await boiler_water_heater.async_set_temperature(**{ATTR_TEMPERATURE: 52})

    assert set_value.call_args_list == [(("target_temperature", 52),)]


async def test_water_heater_ignores_a_call_without_a_temperature(
    boiler_water_heater,
) -> None:
    """A service call without a temperature must not write anything."""
    with patch.object(boiler_water_heater, "_set_native_value") as set_value:
        await boiler_water_heater.async_set_temperature(operation_mode="auto")

    assert not set_value.called


async def test_water_heater_sets_the_operation_mode(boiler_water_heater) -> None:
    """The displayed operation is written back as the numeric device mode."""
    with patch.object(boiler_water_heater, "_set_native_value") as set_value:
        await boiler_water_heater.async_set_operation_mode(HA_DISPLAY_MODE_BLOCKWISE)

    assert set_value.call_args_list == [
        (("holding_mode", SOLARFOCUS_MODE_BLOCKWISE),)
    ]


async def test_water_heater_turns_on_and_off(boiler_water_heater) -> None:
    """On and off map to the always on and always off modes."""
    with patch.object(boiler_water_heater, "_set_native_value") as set_value:
        await boiler_water_heater.async_turn_on()
        await boiler_water_heater.async_turn_off()

    assert set_value.call_args_list == [
        (("holding_mode", SOLARFOCUS_MODE_ALWAYS_ON),),
        (("holding_mode", SOLARFOCUS_MODE_ALWAYS_OFF),),
    ]


# --- writing ----------------------------------------------------------------


def test_set_native_value_writes_and_refreshes_the_component() -> None:
    """Writing commits the register and reads the component back."""
    entity = _make(
        SolarfocusNumberEntity,
        BOILER_NUMBER_TYPES[0],
        BOILER_COMPONENT,
        BOILER_COMPONENT_PREFIX,
    )
    boiler = entity.coordinator.api.boilers[0]
    boiler.target_temperature.value = 55
    boiler.target_temperature.count = 1

    entity._set_native_value("target_temperature", 55)

    boiler.target_temperature.set_unscaled_value.assert_called_once_with(55)
    boiler.target_temperature.commit.assert_called_once()
    boiler.update.assert_called_once()
    entity.async_write_ha_state.assert_called_once()
