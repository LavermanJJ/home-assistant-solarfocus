"""Climate for Solarfocus integration."""

from dataclasses import dataclass
import logging
from typing import Any, cast, override

from aiosolarfocus import (
    HeatingCircuitCooling,
    HeatingCircuitHeatingMode,
    HeatingCircuitMode,
)
from aiosolarfocus.components.heating_circuit import HeatingCircuit

from homeassistant.components.climate import ClimateEntity, ClimateEntityDescription
from homeassistant.components.climate.const import (
    PRESET_COMFORT,
    PRESET_ECO,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from .const import (
    CONF_HEATING_CIRCUIT,
    HEATING_CIRCUIT_COMPONENT,
    HEATING_CIRCUIT_COMPONENT_PREFIX,
)
from .coordinator import SolarfocusConfigEntry, SolarfocusDataUpdateCoordinator
from .entity import SolarfocusEntity, SolarfocusEntityDescription, create_description

_LOGGER = logging.getLogger(__name__)

# Every write is a read-modify-commit sequence on a component, so two of them
# running at once can interleave on the same registers. This limits Home
# Assistant to one in-flight service call per platform; it does not cover the
# reads the coordinator does, which is why writes re-read their component.
PARALLEL_UPDATES = 1


PRESET_AUTO = "auto"
PRESET_OFF = "off"

SOLARFOCUS_MODE_TO_PRESET = {
    0: PRESET_COMFORT,
    1: PRESET_ECO,
    2: PRESET_AUTO,
    3: PRESET_OFF,
}

PRESET_TO_SOLARFOCUS_MODE = {
    value: key for key, value in SOLARFOCUS_MODE_TO_PRESET.items()
}

# Section 6.2 of the Solarfocus Modbus specification, "Vorlaufsolltemperatur wird
# an ecomanager-touch geschickt": the external controller takes over the heating
# circuit and writes these four registers together.
#
#            32600 target_supply_temperature   32602 cooling
#            32603 mode                        32608 heating_mode
#
# heating    setpoint  0  <preset>  2
# cooling    setpoint  1  <preset>  2
# off        0         0  3         2
#
# The specification writes 0 (continuous operation) into 32603 for heating and
# cooling. We keep the preset the user has configured instead and only switch the
# circuit back on when it is off, so that a comfort, eco or auto schedule is not
# silently discarded.

# Register 32602 "Kühlen"
COOLING_OFF = 0
COOLING_ON = 1

# Register 32603 "Heizkreisbetriebsart"
OPERATING_MODE_CONTINUOUS = 0
OPERATING_MODE_OFF = 3

# Register 32608 "Heizkreismodus"
HEATING_MODE_HEATING_AND_COOLING = 2

# Heating circuit states that mean the circuit is actively cooling.
COOLING_STATES = [23, 24]

# Used until the user has set a flow temperature for the mode themselves.
DEFAULT_TARGET_TEMPERATURE = {HVACMode.HEAT: 30.0, HVACMode.COOL: 19.0}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SolarfocusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Solarfocus config entry."""
    coordinator = config_entry.runtime_data
    entities = []

    for i in range(config_entry.options[CONF_HEATING_CIRCUIT]):
        for description in CLIMATE_TYPES:
            _description = create_description(
                HEATING_CIRCUIT_COMPONENT,
                HEATING_CIRCUIT_COMPONENT_PREFIX,
                str(i + 1),
                description,
            )

            entity = SolarfocusClimateEntity(coordinator, _description)
            entities.append(entity)

    async_add_entities(entities)


@dataclass(frozen=True, kw_only=True)
class SolarfocusClimateEntityDescription(
    SolarfocusEntityDescription, ClimateEntityDescription
):
    """Description of a Solarfocus number entity."""


@dataclass
class SolarfocusClimateExtraStoredData(ExtraStoredData):
    """Flow setpoints the thermostat has to survive a restart with."""

    target_temperatures: dict[str, float]
    active_mode: str

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a serializable representation."""
        return {
            "target_temperatures": self.target_temperatures,
            "active_mode": self.active_mode,
        }


class SolarfocusClimateEntity(SolarfocusEntity, RestoreEntity, ClimateEntity):
    """Representation of a Solarfocus number entity."""

    # `thermostat` and `domestic_hot_water` are labels rather than register
    # names: this entity reads and writes several registers of its component.
    reads_no_single_register = True

    entity_description: SolarfocusClimateEntityDescription

    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        coordinator: SolarfocusDataUpdateCoordinator,
        description: SolarfocusClimateEntityDescription,
    ) -> None:
        """Initialize the Solarfocus select entity."""
        super().__init__(coordinator, description)

        # Switching the circuit off writes register 32600 to 0, so the setpoint
        # has to be remembered to be able to switch the circuit back on.
        self._target_temperatures: dict[HVACMode, float] = {}
        self._active_mode = HVACMode.HEAT
        self._dew_point_warning_logged = False

    @property
    @override
    def extra_restore_state_data(self) -> SolarfocusClimateExtraStoredData:
        """Return the setpoints to restore after a restart."""
        return SolarfocusClimateExtraStoredData(
            target_temperatures={
                mode.value: temperature
                for mode, temperature in self._target_temperatures.items()
            },
            active_mode=self._active_mode.value,
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the setpoints the user has set before the restart."""
        await super().async_added_to_hass()

        if (last_data := await self.async_get_last_extra_data()) is None:
            return

        restored = last_data.as_dict()

        self._target_temperatures = {
            HVACMode(mode): float(temperature)
            for mode, temperature in restored.get("target_temperatures", {}).items()
            if mode in (HVACMode.HEAT, HVACMode.COOL)
        }

        if (active_mode := restored.get("active_mode")) in (
            HVACMode.HEAT,
            HVACMode.COOL,
        ):
            self._active_mode = HVACMode(active_mode)

    @property
    def cooling_supported(self) -> bool:
        """Return whether the circuit can be switched to "Heizen + Kühlen".

        Asked of the register that answers it rather than of a version number:
        `heating_mode` is register 32608, which arrived in 22.090, and the
        library resolves what this firmware and this system actually have. A
        version comparison here was the integration keeping a second copy of
        that fact.
        """
        return self.component.supports("heating_mode")

    @property
    @override
    def max_temp(self) -> float:
        """Return max temperature."""
        if self._get_native_value("cooling"):
            return 35.0
        return 45.0

    @property
    @override
    def min_temp(self) -> float:
        """Return minimum temperature."""
        if self._get_native_value("cooling"):
            return 7.0
        return 22.0

    @property
    @override
    def target_temperature(self) -> float:
        """Return target supply temperature."""
        if value := self._get_native_value("target_supply_temperature"):
            return round(float(value), 2)

        # The circuit is switched off, register 32600 has been written to 0
        return self._remembered_target_temperature(self._active_mode)

    def _remembered_target_temperature(self, hvac_mode: HVACMode) -> float:
        """Return the setpoint to write when switching the circuit to a mode."""
        if (temperature := self._target_temperatures.get(hvac_mode)) is not None:
            return temperature

        # Only the setpoint of the mode the circuit currently runs in can be
        # reused, a heating setpoint is far outside the cooling range.
        value = self._get_native_value("target_supply_temperature")
        if value and self.hvac_mode == hvac_mode:
            return round(float(value), 2)

        return DEFAULT_TARGET_TEMPERATURE[hvac_mode]

    @property
    @override
    def current_temperature(self) -> float:
        """Return current temperature."""
        # if self._get_native_value("target_room_temperatur"):
        #    return self._get_native_value("room_temperature")

        return cast(float, self._get_native_value("supply_temperature"))

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Return hvac target hvac state."""
        if self._get_native_value("state") in [0]:
            return HVACMode.OFF

        if self.cooling_supported and self._get_native_value("cooling"):
            return HVACMode.COOL

        return HVACMode.HEAT

    @property
    @override
    def hvac_action(self) -> HVACAction:
        """Return hvac action."""
        state = self._get_native_value("state")

        if state in [
            0,
            6,
            7,
            9,
            10,
            11,
            27,
            28,
            30,
            200,
            202,
            212,
            214,
            215,
            227,
            228,
            211,
        ]:
            return HVACAction.OFF
        if state in [31]:
            return HVACAction.IDLE
        if state in COOLING_STATES:
            return HVACAction.COOLING
        return HVACAction.HEATING

    @property
    @override
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available operation modes."""
        modes = [HVACMode.OFF, HVACMode.HEAT]
        if self.cooling_supported:
            modes.append(HVACMode.COOL)
        return modes

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return preset mode."""
        mode = self._get_native_value("mode")
        return SOLARFOCUS_MODE_TO_PRESET.get(mode)

    @property
    @override
    def preset_modes(self) -> list[str]:
        """Return available preset modes."""
        presets = []
        presets.append(PRESET_COMFORT)
        presets.append(PRESET_ECO)
        presets.append(PRESET_AUTO)
        presets.append(PRESET_OFF)
        return presets

    # @property
    # def current_humidity(self) -> int:
    #    return self._get_native_value("humidity")

    @property
    @override
    def temperature_unit(self) -> str:
        """Return temperature unit."""
        return UnitOfTemperature.CELSIUS

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        _LOGGER.info("Set HVAC Mode: %s", hvac_mode)

        if hvac_mode == HVACMode.OFF:
            await self._write_heating_circuit(
                target_supply_temperature=0,
                cooling=COOLING_OFF,
                operating_mode=OPERATING_MODE_OFF,
            )
            return

        if hvac_mode == HVACMode.COOL:
            self._log_dew_point_warning()

        self._active_mode = hvac_mode
        await self._write_heating_circuit(
            target_supply_temperature=self._remembered_target_temperature(hvac_mode),
            cooling=COOLING_ON if hvac_mode == HVACMode.COOL else COOLING_OFF,
            operating_mode=self._operating_mode(),
        )

    def _operating_mode(self) -> int:
        """Return the value for register 32603 "Heizkreisbetriebsart".

        A circuit that is switched off has to be switched back on, any other
        setting is the preset the user has configured and is kept.
        """
        mode = self._get_native_value("mode")
        if mode == OPERATING_MODE_OFF:
            return OPERATING_MODE_CONTINUOUS
        return int(mode)

    async def _write_heating_circuit(
        self, target_supply_temperature: float, cooling: int, operating_mode: int
    ) -> None:
        """Write the registers section 6.2 requires to be written together.

        Writing only some of them can leave the controller in an undefined state.
        They go out under one hold of the transport lock now, in the order this
        entity has always written them, so no poll of the coordinator lands
        between two of them. It used to be four separate blocking writes, each
        followed by re-reading the whole component.

        Register 32608 does not exist below api version 22.090; a circuit that old
        cannot cool anyway, so heating and off are written without it.
        """
        component = cast(HeatingCircuit, self.component)

        await component.set_operating_state(
            target_supply_temperature=target_supply_temperature,
            cooling=HeatingCircuitCooling(cooling),
            mode=HeatingCircuitMode(operating_mode),
            heating_mode=(
                HeatingCircuitHeatingMode(HEATING_MODE_HEATING_AND_COOLING)
                if self.cooling_supported
                else None
            ),
        )

        self.async_write_ha_state()

    def _log_dew_point_warning(self) -> None:
        """Warn that the controller stops watching the dew point, once."""
        if self._dew_point_warning_logged:
            return

        self._dew_point_warning_logged = True
        _LOGGER.warning(
            "Heating circuit %s has been switched to cooling. Writing register 32602 "
            "disables the dew point monitoring of the Solarfocus controller, so the "
            "flow temperature has to be kept above the dew point of every room from "
            "Home Assistant to avoid condensation damage to the building",
            self.entity_description.component_idx,
        )

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        mode = PRESET_TO_SOLARFOCUS_MODE.get(preset_mode)
        _LOGGER.info("Set Preset Mode: %s (mapped mode: %s)", preset_mode, mode)

        if mode is None:
            # Home Assistant only offers the presets this entity declares, so
            # this is a service call naming one that does not exist. It used to
            # write the `None` to the register.
            _LOGGER.warning("Unknown preset mode %s, nothing written", preset_mode)
            return

        await self._async_set_native_value("mode", HeatingCircuitMode(mode))

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the flow setpoint of the mode the circuit is running in."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        _LOGGER.info("Set Temperature: %s", temperature)
        hvac_mode = self.hvac_mode

        if hvac_mode == HVACMode.OFF:
            # Register 32600 has to stay 0 while the circuit is switched off, so
            # the setpoint is only remembered for the next time it is switched on.
            self._target_temperatures[self._active_mode] = float(temperature)
            self.async_write_ha_state()
            return

        self._active_mode = hvac_mode
        self._target_temperatures[hvac_mode] = float(temperature)
        await self._async_set_native_value("target_supply_temperature", temperature)

    @override
    async def async_turn_on(self) -> None:
        """Turn on - by setting HVAC mode to HEAT."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    @override
    async def async_turn_off(self) -> None:
        """Turn on - by setting HVAC mode to OFF."""
        await self.async_set_hvac_mode(HVACMode.OFF)


CLIMATE_TYPES = [
    SolarfocusClimateEntityDescription(
        key="thermostat",
    )
]
