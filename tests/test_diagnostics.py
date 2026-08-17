"""What a diagnostics download says about an entry.

The point of the file is that a user can attach one to an issue, so the two
things worth testing are that everything needed to reproduce their setup is in
it, and that the address of their controller is not.
"""

import json

from pysolarfocus import ApiVersions
from pysolarfocus.components.boiler import Boiler
from pysolarfocus.components.heat_pump import HeatPump
from pysolarfocus.components.heating_circuit import HeatingCircuit
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)

from custom_components.solarfocus.diagnostics import async_get_config_entry_diagnostics
from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import ExtendedJSONEncoder
from homeassistant.setup import async_setup_component

from .conftest import build_config_entry


async def _diagnostics(hass: HomeAssistant, api, **options) -> dict:
    """Set an entry up and return its diagnostics."""
    api.heating_circuits = [HeatingCircuit()]
    api.boilers = [Boiler()]
    api.heatpump = HeatPump(api_version=ApiVersions.V_23_020)

    entry = build_config_entry(**options)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return await async_get_config_entry_diagnostics(hass, entry)


async def test_diagnostics_hide_the_address_of_the_controller(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """The host is the one thing in the options a user should not have to strip."""
    diagnostics = await _diagnostics(hass, api, heating_circuit=1)

    assert diagnostics["entry"]["options"][CONF_HOST] == REDACTED
    # The port says nothing on its own and tells a non-standard setup apart
    assert diagnostics["entry"]["options"][CONF_PORT] == 502
    assert "solarfocus.local" not in str(diagnostics)


async def test_home_assistant_serves_the_download(
    hass: HomeAssistant,
    hass_client,
    enable_custom_integrations,
    mock_api,
    api,
) -> None:
    """Only a module named `diagnostics.py` next to the platforms is found at all.

    Going through the http api is what tells a working download apart from a
    working function: nothing declares the platform, Home Assistant looks for
    the module by name.
    """
    api.heating_circuits = [HeatingCircuit()]

    entry = build_config_entry(heating_circuit=1)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "diagnostics", {})

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diagnostics["entry"]["options"][CONF_HOST] == REDACTED
    assert diagnostics["components"]["heating_circuits"][0]["supply_temperature"] == 0


async def test_diagnostics_survive_being_written_out(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """Home Assistant serves the download as JSON, so it has to encode.

    Nothing in a register is exotic, but the system of an entry is an enum and
    the values come out of a library, which is where this would break.
    """
    diagnostics = await _diagnostics(hass, api, heating_circuit=1, heatpump=True)

    assert json.loads(json.dumps(diagnostics, cls=ExtendedJSONEncoder))


async def test_diagnostics_describe_how_the_entry_is_configured(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """The component counts and the api version are what a report has to state."""
    diagnostics = await _diagnostics(hass, api, heating_circuit=2, boiler=1)

    entry = diagnostics["entry"]

    assert entry["version"] == 7
    assert entry["options"]["heating_circuit"] == 2
    assert entry["options"]["api_version"] == ApiVersions.V_23_020.value
    assert entry["data"]["system"] is not None


async def test_diagnostics_report_the_registers_of_every_component(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """A value the heating system reports is the point of the whole download.

    The components that can exist several times over are a list even when only
    one is configured, so that the index in an entity name lines up with it.
    """
    diagnostics = await _diagnostics(hass, api, heating_circuit=1, heatpump=True)

    components = diagnostics["components"]

    assert components["heating_circuits"][0]["supply_temperature"] == 0
    assert "mixer_valve" in components["heating_circuits"][0]
    assert components["heatpump"]["compressor_speed"] == 0
    # A calculated value is not a register but is read like one, and it is the
    # first thing asked about when a COP looks wrong
    assert "cop_heating" in components["heatpump"]


async def test_diagnostics_leave_out_a_component_that_is_not_configured(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """A component the user does not have has no registers to report."""
    api.biomassboiler = None
    api.photovoltaic = None

    diagnostics = await _diagnostics(hass, api, heating_circuit=1)

    assert diagnostics["components"]["biomassboiler"] is None
    assert diagnostics["components"]["photovoltaic"] is None


async def test_diagnostics_name_the_components_that_could_not_be_read(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """Which component is failing is what a partial failure comes down to.

    It is only in the log otherwise, once, so a download taken later would not
    show it at all.
    """
    api.heating_circuits = [HeatingCircuit()]
    api.boilers = [Boiler()]

    entry = build_config_entry(heating_circuit=1, boiler=1)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["coordinator"]["last_update_success"] is True
    assert diagnostics["coordinator"]["failed_components"] == []

    api.update_boiler.return_value = False
    await entry.runtime_data.async_refresh()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["coordinator"]["last_update_success"] is True
    assert diagnostics["coordinator"]["failed_components"] == ["boiler"]


async def test_diagnostics_do_not_blame_one_component_for_a_whole_outage(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """A component named here is one that fails while the others read fine.

    When the heating system stops answering altogether the refresh fails, and
    that is what the download says. Naming the component that happened to be
    failing before would point a report at the wrong thing.
    """
    api.heating_circuits = [HeatingCircuit()]
    api.boilers = [Boiler()]

    entry = build_config_entry(heating_circuit=1, boiler=1)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    api.update_boiler.return_value = False
    await entry.runtime_data.async_refresh()

    assert (await async_get_config_entry_diagnostics(hass, entry))["coordinator"][
        "failed_components"
    ] == ["boiler"]

    api.update_heating.return_value = False
    await entry.runtime_data.async_refresh()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["coordinator"]["last_update_success"] is False
    assert diagnostics["coordinator"]["failed_components"] == []
