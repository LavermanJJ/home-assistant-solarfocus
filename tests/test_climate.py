"""Test the Solarfocus climate entity."""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.solarfocus.climate import (
    SolarfocusClimateEntity,
    SolarfocusClimateEntityDescription,
)
from custom_components.solarfocus.const import (
    HEATING_CIRCUIT_COMPONENT,
    HEATING_CIRCUIT_COMPONENT_PREFIX,
    HEATING_CIRCUIT_PREFIX,
)
from custom_components.solarfocus.entity import create_description
from homeassistant.components.climate.const import HVACMode


@pytest.fixture(name="climate")
def climate_fixture() -> SolarfocusClimateEntity:
    """Return a thermostat entity for heating circuit 1 with a mocked coordinator."""
    coordinator = MagicMock()
    coordinator._entry.title = "Solarfocus"

    description = create_description(
        HEATING_CIRCUIT_PREFIX,
        HEATING_CIRCUIT_COMPONENT,
        HEATING_CIRCUIT_COMPONENT_PREFIX,
        "1",
        SolarfocusClimateEntityDescription(key="thermostat"),
    )

    return SolarfocusClimateEntity(coordinator, description)


async def test_turn_on_sets_heat_mode(climate: SolarfocusClimateEntity) -> None:
    """Turning on writes the registers for HVACMode.HEAT."""
    with (
        patch.object(climate, "_set_native_value") as set_value,
        patch.object(climate, "_get_native_value", return_value=0),
    ):
        await climate.async_turn_on()

    # state 0 means the circuit is off, so it is switched back to mode "comfort"
    assert set_value.call_args_list == [
        (("mode", "0"),),
        (("cooling", "0"),),
    ]


async def test_turn_on_while_running_only_disables_cooling(
    climate: SolarfocusClimateEntity,
) -> None:
    """A circuit that is already running keeps its mode."""
    with (
        patch.object(climate, "_set_native_value") as set_value,
        patch.object(climate, "_get_native_value", return_value=31),
    ):
        await climate.async_turn_on()

    assert set_value.call_args_list == [(("cooling", "0"),)]


async def test_turn_off_sets_off_mode(climate: SolarfocusClimateEntity) -> None:
    """Turning off writes the register for HVACMode.OFF."""
    with (
        patch.object(climate, "_set_native_value") as set_value,
        patch.object(climate, "_get_native_value", return_value=31),
    ):
        await climate.async_turn_off()

    assert set_value.call_args_list == [(("mode", "3"),)]


@pytest.mark.parametrize(
    ("hvac_mode", "expected"),
    [
        (HVACMode.OFF, [(("mode", "3"),)]),
        (HVACMode.HEAT, [(("cooling", "0"),)]),
    ],
)
async def test_set_hvac_mode(
    climate: SolarfocusClimateEntity, hvac_mode: HVACMode, expected: list
) -> None:
    """Setting the hvac mode directly writes the same registers."""
    with (
        patch.object(climate, "_set_native_value") as set_value,
        patch.object(climate, "_get_native_value", return_value=31),
    ):
        await climate.async_set_hvac_mode(hvac_mode)

    assert set_value.call_args_list == expected
