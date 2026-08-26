"""Test the Solarfocus climate entity against the Modbus specification.

Section 6.2 of the specification ("Vorlaufsolltemperatur wird an ecomanager-touch
geschickt") defines three complete register states for a heating circuit that is
controlled externally, and requires all of the registers to be written on every
transition - writing only some of them can leave the controller in an undefined
state.

    register                          heating    cooling    off
    32600 target_supply_temperature   setpoint   setpoint   0
    32602 cooling                     0          1          0
    32603 mode                        <preset>   <preset>   3
    32608 heating_mode                2          2          2

The specification writes 0 (continuous operation) into 32603 for heating and
cooling. This integration keeps the preset the user configured instead and only
switches a circuit that is off back on, see the module docstring of climate.py.
"""

from unittest.mock import MagicMock, patch

from aiosolarfocus import ApiVersion, ComponentId
import pytest
from pytest_homeassistant_custom_component.common import (
    mock_restore_cache_with_extra_data,
)

from custom_components.solarfocus.climate import (
    CLIMATE_TYPES,
    DEFAULT_TARGET_TEMPERATURE,
    PRESET_AUTO,
    PRESET_OFF,
    SolarfocusClimateEntity,
)
from custom_components.solarfocus.const import (
    HEATING_CIRCUIT_COMPONENT,
    HEATING_CIRCUIT_COMPONENT_PREFIX,
)
from custom_components.solarfocus.entity import SolarfocusEntity, create_description
from homeassistant.components.climate.const import (
    PRESET_COMFORT,
    PRESET_ECO,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import State

from .conftest import (
    build_client,
    build_config_entry,
    build_coordinator,
    set_reading,
    written_by_name,
)

# The registers the specification requires to be written together.
REGISTERS = ("target_supply_temperature", "cooling", "mode", "heating_mode")

STATE_OFF = 0
STATE_HEATING = 2
STATE_COOLING = 23

MODE_CONTINUOUS = 0
MODE_AUTO = 2
MODE_OFF = 3


def build_climate(
    api_version: ApiVersion = ApiVersion.V_23_020,
    state: int = STATE_HEATING,
    mode: int = MODE_CONTINUOUS,
    cooling: int = 0,
    target_supply_temperature: float = 38.0,
) -> SolarfocusClimateEntity:
    """Return a thermostat for heating circuit 1 over a fake controller."""
    entry = build_config_entry(api_version=api_version.label, heating_circuit=1)
    client = build_client(entry)

    set_reading(client, ComponentId.HEATING_CIRCUITS, "state", state)
    set_reading(client, ComponentId.HEATING_CIRCUITS, "mode", mode)
    set_reading(client, ComponentId.HEATING_CIRCUITS, "cooling", cooling)
    set_reading(
        client,
        ComponentId.HEATING_CIRCUITS,
        "target_supply_temperature",
        target_supply_temperature,
    )
    set_reading(client, ComponentId.HEATING_CIRCUITS, "supply_temperature", 36.5)

    entity = SolarfocusClimateEntity(
        build_coordinator(entry, client),
        create_description(
            HEATING_CIRCUIT_COMPONENT,
            HEATING_CIRCUIT_COMPONENT_PREFIX,
            "1",
            CLIMATE_TYPES[0],
        ),
    )
    entity.async_write_ha_state = MagicMock()
    return entity


def written(climate: SolarfocusClimateEntity) -> dict[str, float]:
    """Return the registers the thermostat wrote, keyed by their name.

    They go out as one grouped write now, so what a test watches is the wire
    rather than a call of the entity's own setter per register.
    """
    return written_by_name(climate.coordinator.client, ComponentId.HEATING_CIRCUITS)


@pytest.fixture(name="climate")
def climate_fixture() -> SolarfocusClimateEntity:
    """Return a thermostat of a circuit running in heating mode."""
    return build_climate()


# --- the three register states of section 6.2 --------------------------------


async def test_heating_writes_every_register(climate) -> None:
    """6.2.1, the circuit is switched to heating."""
    await climate.async_set_hvac_mode(HVACMode.HEAT)

    assert written(climate) == {
        "target_supply_temperature": 38.0,
        "cooling": 0,
        "mode": MODE_CONTINUOUS,
        "heating_mode": 2,
    }


async def test_cooling_writes_every_register(climate) -> None:
    """6.2.2, the circuit is switched to cooling."""
    await climate.async_set_hvac_mode(HVACMode.COOL)

    assert written(climate) == {
        # No cooling setpoint has been set yet, a heating one must not be reused
        "target_supply_temperature": DEFAULT_TARGET_TEMPERATURE[HVACMode.COOL],
        "cooling": 1,
        "mode": MODE_CONTINUOUS,
        "heating_mode": 2,
    }


async def test_off_writes_every_register(climate) -> None:
    """6.2.3, the circuit is switched off, including the setpoint of 0."""
    await climate.async_set_hvac_mode(HVACMode.OFF)

    assert written(climate) == {
        "target_supply_temperature": 0,
        "cooling": 0,
        "mode": MODE_OFF,
        "heating_mode": 2,
    }


@pytest.mark.parametrize(
    "hvac_mode", [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF], ids=str
)
async def test_no_register_is_left_out(climate, hvac_mode: HVACMode) -> None:
    """The specification requires all four registers on every transition."""
    await climate.async_set_hvac_mode(hvac_mode)

    assert set(written(climate)) == set(REGISTERS)


# --- the preset deviation ----------------------------------------------------


async def test_switching_on_keeps_the_configured_preset() -> None:
    """A circuit on an auto schedule keeps it when the mode is switched."""
    climate = build_climate(mode=MODE_AUTO)

    await climate.async_set_hvac_mode(HVACMode.COOL)

    assert written(climate)["mode"] == MODE_AUTO


async def test_switching_on_a_circuit_that_is_off_selects_continuous() -> None:
    """A circuit that is switched off has to be switched back on."""
    climate = build_climate(state=STATE_OFF, mode=MODE_OFF)

    await climate.async_set_hvac_mode(HVACMode.HEAT)

    assert written(climate)["mode"] == MODE_CONTINUOUS


# --- api versions ------------------------------------------------------------


async def test_cooling_needs_api_version_22_090() -> None:
    """Register 32608 does not exist below 22.090, so cooling is not offered."""
    old = build_climate(api_version=ApiVersion.V_21_140)
    new = build_climate(api_version=ApiVersion.V_22_090)

    assert old.hvac_modes == [HVACMode.OFF, HVACMode.HEAT]
    assert new.hvac_modes == [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL]


async def test_heating_mode_is_not_written_below_22_090() -> None:
    """Writing a register the api version does not have raises AttributeError."""
    climate = build_climate(api_version=ApiVersion.V_21_140)

    await climate.async_set_hvac_mode(HVACMode.HEAT)

    assert "heating_mode" not in written(climate)


async def test_a_cooling_circuit_reports_cooling() -> None:
    """The cooling register decides between heating and cooling."""
    assert build_climate(cooling=1).hvac_mode == HVACMode.COOL
    assert build_climate(cooling=0).hvac_mode == HVACMode.HEAT
    assert build_climate(state=STATE_OFF).hvac_mode == HVACMode.OFF


async def test_an_old_circuit_never_reports_cooling() -> None:
    """Below 22.090 the cooling register is not part of the mode."""
    climate = build_climate(api_version=ApiVersion.V_21_140, cooling=1)

    assert climate.hvac_mode == HVACMode.HEAT


# --- the flow setpoint -------------------------------------------------------


async def test_the_setpoint_survives_being_switched_off(climate) -> None:
    """Switching off writes 0, switching back on restores the setpoint."""
    await climate.async_set_temperature(**{ATTR_TEMPERATURE: 41.5})

    # The circuit is off, register 32600 reads 0
    climate.coordinator.api.heating_circuits[0].target_supply_temperature.scaled_value = 0
    climate.coordinator.api.heating_circuits[0].state.scaled_value = STATE_OFF

    await climate.async_set_hvac_mode(HVACMode.HEAT)

    assert written(climate)["target_supply_temperature"] == 41.5


async def test_each_mode_keeps_its_own_setpoint(climate) -> None:
    """A heating setpoint is far outside the cooling range and vice versa."""
    await climate.async_set_temperature(**{ATTR_TEMPERATURE: 41.5})

    await climate.async_set_hvac_mode(HVACMode.COOL)
    assert written(climate)["target_supply_temperature"] == 19.0

    climate.coordinator.api.heating_circuits[0].cooling.scaled_value = 1
    await climate.async_set_temperature(**{ATTR_TEMPERATURE: 18.0})

    climate.coordinator.api.heating_circuits[0].cooling.scaled_value = 0
    await climate.async_set_hvac_mode(HVACMode.COOL)

    assert written(climate)["target_supply_temperature"] == 18.0


async def test_setting_a_temperature_while_off_only_remembers_it() -> None:
    """Register 32600 has to stay 0 while the circuit is switched off."""
    climate = build_climate(state=STATE_OFF, target_supply_temperature=0)

    await climate.async_set_temperature(**{ATTR_TEMPERATURE: 40.0})

    assert not written(climate)
    assert climate.target_temperature == 40.0


async def test_setting_a_temperature_writes_the_setpoint(climate) -> None:
    """A running circuit takes the setpoint immediately."""
    await climate.async_set_temperature(**{ATTR_TEMPERATURE: 42.0})

    assert written(climate) == {"target_supply_temperature": 42.0}


async def test_a_call_without_a_temperature_writes_nothing(climate) -> None:
    """The service can be called with other attributes only."""
    await climate.async_set_temperature(hvac_mode=HVACMode.HEAT)

    assert not written(climate)


async def test_the_setpoint_of_a_switched_off_circuit_is_the_remembered_one() -> None:
    """Register 32600 reads 0 while off, which is not a usable setpoint."""
    climate = build_climate(state=STATE_OFF, target_supply_temperature=0)

    assert climate.target_temperature == DEFAULT_TARGET_TEMPERATURE[HVACMode.HEAT]


# --- condensation ------------------------------------------------------------


async def test_switching_to_cooling_warns_about_the_dew_point(
    climate, caplog: pytest.LogCaptureFixture
) -> None:
    """The controller stops watching the dew point once 32602 is written."""
    await climate.async_set_hvac_mode(HVACMode.COOL)

    assert "dew point" in caplog.text
    assert "condensation" in caplog.text


async def test_the_dew_point_warning_is_logged_once(
    climate, caplog: pytest.LogCaptureFixture
) -> None:
    """A thermostat in cooling mode must not warn on every service call."""
    await climate.async_set_hvac_mode(HVACMode.COOL)
    await climate.async_set_hvac_mode(HVACMode.COOL)

    warnings = [record for record in caplog.records if record.levelname == "WARNING"]
    assert len(warnings) == 1


async def test_heating_does_not_warn(climate, caplog: pytest.LogCaptureFixture) -> None:
    """Heating leaves the dew point monitoring of the controller alone."""
    await climate.async_set_hvac_mode(HVACMode.HEAT)

    assert "dew point" not in caplog.text


# --- what the thermostat reports ---------------------------------------------


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (STATE_OFF, HVACAction.OFF),
        (11, HVACAction.OFF),
        (228, HVACAction.OFF),
        (31, HVACAction.IDLE),
        (23, HVACAction.COOLING),
        (24, HVACAction.COOLING),
        (STATE_HEATING, HVACAction.HEATING),
    ],
)
def test_hvac_action(state: int, expected: HVACAction) -> None:
    """The device state maps to what the circuit is currently doing."""
    assert build_climate(state=state).hvac_action == expected


@pytest.mark.parametrize(
    ("mode", "preset"),
    [(0, PRESET_COMFORT), (1, PRESET_ECO), (2, PRESET_AUTO), (3, PRESET_OFF)],
)
def test_preset_mode(mode: int, preset: str) -> None:
    """Every device mode has a preset."""
    climate = build_climate(mode=mode)

    assert climate.preset_mode == preset
    assert preset in climate.preset_modes


@pytest.mark.parametrize(
    ("preset", "expected"),
    [(PRESET_COMFORT, 0), (PRESET_ECO, 1), (PRESET_AUTO, 2), (PRESET_OFF, 3)],
)
async def test_set_preset_mode(climate, preset: str, expected: int) -> None:
    """Selecting a preset writes the numeric mode."""
    await climate.async_set_preset_mode(preset)

    assert written(climate) == {"mode": expected}


@pytest.mark.parametrize(
    ("cooling", "min_temp", "max_temp"), [(0, 22.0, 45.0), (1, 7.0, 35.0)]
)
def test_temperature_range_follows_cooling(
    cooling: int, min_temp: float, max_temp: float
) -> None:
    """A cooling circuit has a different valid range than a heating one."""
    climate = build_climate(cooling=cooling)

    assert climate.min_temp == min_temp
    assert climate.max_temp == max_temp


def test_temperatures() -> None:
    """The thermostat works on the supply temperature.

    Register 32600 holds tenths of a degree, so 40.123 is not a reading it can
    give: the library rounds to the precision the scale carries, where the
    predecessor passed `40.123000000000005` through for Home Assistant to
    record.
    """
    climate = build_climate(target_supply_temperature=40.123)

    assert climate.current_temperature == 36.5
    assert climate.target_temperature == 40.1
    assert climate.temperature_unit == UnitOfTemperature.CELSIUS


def test_supported_features_include_the_setpoint(climate) -> None:
    """Writing register 32600 requires the target temperature feature."""
    assert ClimateEntityFeature.TARGET_TEMPERATURE in climate.supported_features


# --- restoring after a restart ------------------------------------------------


async def test_setpoints_are_stored_for_a_restart(climate) -> None:
    """The remembered setpoints are written to the restore state."""
    await climate.async_set_temperature(**{ATTR_TEMPERATURE: 41.5})

    assert climate.extra_restore_state_data.as_dict() == {
        "target_temperatures": {"heat": 41.5},
        "active_mode": "heat",
    }


async def test_setpoints_are_restored_after_a_restart(climate) -> None:
    """A restart must not lose the setpoint of a switched off circuit."""
    restored = MagicMock()
    restored.as_dict.return_value = {
        "target_temperatures": {"heat": 41.5, "cool": 18.0},
        "active_mode": "cool",
    }

    with (
        patch.object(SolarfocusEntity, "async_added_to_hass"),
        patch.object(climate, "async_get_last_extra_data", return_value=restored),
    ):
        await climate.async_added_to_hass()

    assert climate._target_temperatures == {
        HVACMode.HEAT: 41.5,
        HVACMode.COOL: 18.0,
    }
    assert climate._active_mode == HVACMode.COOL


async def test_a_first_start_has_nothing_to_restore(climate) -> None:
    """Without stored data the defaults stay in place."""
    with (
        patch.object(SolarfocusEntity, "async_added_to_hass"),
        patch.object(climate, "async_get_last_extra_data", return_value=None),
    ):
        await climate.async_added_to_hass()

    assert climate._target_temperatures == {}
    assert climate._active_mode == HVACMode.HEAT


# --- turn on and off ---------------------------------------------------------


async def test_turn_off(climate) -> None:
    """Turning off is the off state of the specification."""
    await climate.async_turn_off()

    assert written(climate)["mode"] == MODE_OFF
    assert written(climate)["target_supply_temperature"] == 0


async def test_turn_on_heats(climate) -> None:
    """Turning on never starts cooling on its own."""
    await climate.async_turn_on()

    assert written(climate)["cooling"] == 0


# --- wiring ------------------------------------------------------------------


async def test_the_thermostat_restores_its_setpoint_from_storage(
    hass, enable_custom_integrations, mock_client
) -> None:
    """A restart must not lose the setpoint of a circuit that is switched off.

    Goes through the platform rather than calling async_added_to_hass directly,
    so that the restore is exercised the way Home Assistant drives it.
    """
    circuit = ComponentId.HEATING_CIRCUITS
    mock_client.reads(circuit, "state", STATE_OFF)
    mock_client.reads(circuit, "mode", MODE_OFF)
    mock_client.reads(circuit, "cooling", 0)
    # The circuit is switched off, so register 32600 reads 0
    mock_client.reads(circuit, "target_supply_temperature", 0)
    mock_client.reads(circuit, "supply_temperature", 21.0)

    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State("climate.heating_circuit_1_thermostat", HVACMode.OFF),
                {"target_temperatures": {"heat": 41.5}, "active_mode": "heat"},
            ),
        ),
    )

    entry = build_config_entry(heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    states = [state for state in hass.states.async_all() if state.domain == "climate"]
    assert len(states) == 1
    assert states[0].state == HVACMode.OFF
    # Without the restore the thermostat would fall back to the default
    assert states[0].attributes["temperature"] == 41.5
