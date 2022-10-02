"""Coordinator for Solarfocus integration"""

from datetime import timedelta
import logging
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pysolarfocus import SolarfocusAPI

from .const import (
    CONF_BOILER,
    CONF_BUFFER,
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
    CONF_PELLETSBOILER,
    CONF_PHOTOVOLTAIC,
    DOMAIN,
    FIELD_BOILER_MODE,
    FIELD_BOILER_MODE_DEFAULT,
    FIELD_HEATING_MODE,
    FIELD_HEATING_MODE_DEFAULT,
    FIELD_HEATING_OPERATION_MODE,
    FIELD_HEATING_OPERATION_MODE_DEFAULT,
    FIELD_SMARTGRID_STATE,
    FIELD_SMARTGRID_STATE_DEFAULT,
)

_LOGGER = logging.getLogger(__name__)


class SolarfocusDataUpdateCoordinator(DataUpdateCoordinator):
    """Get the latest data and update the states."""

    def __init__(self, hass, modbus_client, entry):
        """Init the Solarfocus data object."""

        self.api = SolarfocusAPI(modbus_client, 1)
        self.api.connect()
        
        self.name = entry.title
        self._entry = entry
        self.hass = hass

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=self._entry.data[CONF_SCAN_INTERVAL]),
        )

    async def _async_update_data(self):
        """Update data via library."""
        
        if not self.api.is_connected():
            self.api.connect()

        success = True

        if self._entry.data[CONF_HEATING_CIRCUIT]:
            success &= True and await self.hass.async_add_executor_job(
                self.api.update_heating
            )

        if self._entry.data[CONF_BUFFER]:
            success &= True and await self.hass.async_add_executor_job(
                self.api.update_buffer
            )

        if self._entry.data[CONF_BOILER]:
            success &= True and await self.hass.async_add_executor_job(
                self.api.update_boiler
            )

        if self._entry.data[CONF_HEATPUMP]:
            success &= True and await self.hass.async_add_executor_job(
                self.api.update_heatpump
            )

        if self._entry.data[CONF_PHOTOVOLTAIC]:
            success &= True and await self.hass.async_add_executor_job(
                self.api.update_photovoltaic
            )

        if self._entry.data[CONF_PELLETSBOILER]:
            success &= True and await self.hass.async_add_executor_job(
                self.api.update_pelletsboiler
            )

        if not success:
            _LOGGER.debug("Data updated failed")
        else:
            _LOGGER.debug("Data updated successfully")

    async def update_hp_smart_grid(self, value: str):
        """Set Smart Grid Mode"""
        _LOGGER.debug("update_hp_smart_grid: %s", (int(value) == 4))
        await self._update(self.api.hp_smart_grid_request_operation, (int(value) == 4))
        await self.hass.async_add_executor_job(self.api.update_heatpump)

    async def update_hc1_cooling(self, value: str):
        """Set Cooling"""
        _LOGGER.debug("update_hc1_cooling: %s", bool(int(value)))
        await self._update(self.api.hc1_enable_cooling, bool(int(value)))
        await self.hass.async_add_executor_job(self.api.update_heating)

    async def update_hc1_mode_holding(self, value: str):
        """Set Heating Mode"""
        _LOGGER.debug("update_hc1_mode_holding: %s", int(value))
        await self._update(self.api.hc1_set_mode, int(value))
        await self.hass.async_add_executor_job(self.api.update_heating)

    async def update_hc1_target_temperatur(self, value: float):
        """Set Heating target supply temperature"""
        _LOGGER.debug("update_hc1_target_temperatur: %f", value)
        await self._update(self.api.hc1_set_target_supply_temperature, value)
        await self.hass.async_add_executor_job(self.api.update_heating)

    async def update_bo1_target_temperatur(self, value: float):
        """Set Boiler target temperature"""
        _LOGGER.debug("update_bo1_target_temperatur: %s", value)
        await self._update(self.api.bo1_set_target_temperature, value)
        await self.hass.async_add_executor_job(self.api.update_boiler)

    async def update_bo1_mode_holding(self, value: str):
        """Set Boiler Mode"""
        _LOGGER.debug("update_bo1_mode: %s", int(value))
        await self._update(self.api.bo1_set_mode, int(value))
        await self.hass.async_add_executor_job(self.api.update_boiler)

    async def trigger_bo1_enable_single_charge(self):
        """Trigger Boiler Single Charge"""
        _LOGGER.debug("trigger_bo1_single_charge")
        await self._update(self.api.bo1_enable_single_charge, True)

    async def trigger_bo1_enable_circulation(self):
        """Trigger Boiler Circulation Reuqest"""
        _LOGGER.debug("bo1_enable_circulation")
        await self._update(self.api.bo1_enable_circulation, True)

    async def _update(self, func, value):

        if not self.api.is_connected():
            self.api.connect()

        if not await self.hass.async_add_executor_job(func, value):
            _LOGGER.debug("Writing Data failed")
        else:
            _LOGGER.debug("Writing Data successfully")


class SolarfocusServiceCoordinator:
    """Coordinate service calls"""

    data_update_coordinator = None

    def __init__(self, data_update_coordinator: SolarfocusDataUpdateCoordinator):
        """Init the Solarfocus data object."""
        self.data_update_coordinator = data_update_coordinator

    async def set_operation_mode(self, call):
        """Handle the set operation mode service call."""
        mode = call.data.get(
            FIELD_HEATING_OPERATION_MODE, FIELD_HEATING_OPERATION_MODE_DEFAULT
        )
        _LOGGER.debug("set_operation_mode: state = %s", mode)
        await self.data_update_coordinator.update_hc1_cooling(mode)

    async def set_heating_mode(self, call):
        """Handle the set heating mode service call."""
        mode = call.data.get(FIELD_HEATING_MODE, FIELD_HEATING_MODE_DEFAULT)
        _LOGGER.debug("set_heating_mode: state = %s", mode)
        await self.data_update_coordinator.update_hc1_mode_holding(mode)

    async def set_boiler_mode(self, call):
        """Handle the set boiler mode service call."""
        mode = call.data.get(FIELD_BOILER_MODE, FIELD_BOILER_MODE_DEFAULT)
        _LOGGER.debug("set_boiler_mode: state = %s", mode)
        await self.data_update_coordinator.update_bo1_mode_holding(mode)

    async def set_smart_grid(self, call):
        """Handle the set smart grid service call."""
        state = call.data.get(FIELD_SMARTGRID_STATE, FIELD_SMARTGRID_STATE_DEFAULT)
        _LOGGER.debug("set_smart_grid: state = %s", state)
        await self.data_update_coordinator.update_hp_smart_grid(state)
