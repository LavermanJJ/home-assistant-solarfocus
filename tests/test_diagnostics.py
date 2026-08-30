"""What a diagnostics download says about an entry.

The point of the file is that a user can attach one to an issue, so the two
things worth testing are that everything needed to reproduce their setup is in
it, and that the address of their controller is not.
"""

import json

from aiosolarfocus import ApiVersion, ComponentId
from aiosolarfocus import __version__ as aiosolarfocus_version
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)

from custom_components.solarfocus.diagnostics import async_get_config_entry_diagnostics
from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import ExtendedJSONEncoder
from homeassistant.setup import async_setup_component

from .conftest import CURRENT_VERSION, build_config_entry


async def _diagnostics(hass: HomeAssistant, **options) -> dict:
    """Set an entry up and return its diagnostics."""
    entry = build_config_entry(**options)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return await async_get_config_entry_diagnostics(hass, entry)


async def test_diagnostics_hide_the_address_of_the_controller(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """The host is the one thing in the options a user should not have to strip."""
    diagnostics = await _diagnostics(hass, heating_circuit=1)

    assert diagnostics["entry"]["data"][CONF_HOST] == REDACTED
    # The port says nothing on its own and tells a non-standard setup apart
    assert diagnostics["entry"]["data"][CONF_PORT] == 502
    assert "solarfocus.local" not in str(diagnostics)


async def test_diagnostics_name_the_library_version_actually_installed(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """The manifest pins a version; a report has to say what is really there.

    fklein1980 ran a stale aiosolarfocus against a controller and nothing in
    the output said so (#237). A diagnostics download falls into the same trap,
    and it is the one artefact an issue is usually written from.
    """
    diagnostics = await _diagnostics(hass, heating_circuit=1)

    assert diagnostics["aiosolarfocus"] == aiosolarfocus_version


async def test_home_assistant_serves_the_download(
    hass: HomeAssistant,
    hass_client,
    enable_custom_integrations,
    mock_client,
) -> None:
    """Only a module named `diagnostics.py` next to the platforms is found at all.

    Going through the http api is what tells a working download apart from a
    working function: nothing declares the platform, Home Assistant looks for
    the module by name.
    """
    entry = build_config_entry(heating_circuit=1)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "diagnostics", {})

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diagnostics["entry"]["data"][CONF_HOST] == REDACTED
    assert (
        diagnostics["components"]["heating_circuits.1"]["supply_temperature"]["value"]
        == 0
    )


async def test_diagnostics_survive_being_written_out(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """Home Assistant serves the download as JSON, so it has to encode.

    Nothing in a register is exotic, but the system of an entry is an enum and
    the values come out of a library, which is where this would break.
    """
    diagnostics = await _diagnostics(hass, heating_circuit=1, heatpump=True)

    assert json.loads(json.dumps(diagnostics, cls=ExtendedJSONEncoder))


async def test_diagnostics_describe_how_the_entry_is_configured(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """The component counts and the api version are what a report has to state."""
    diagnostics = await _diagnostics(hass, heating_circuit=2, boiler=1)

    entry = diagnostics["entry"]

    assert entry["version"] == CURRENT_VERSION
    assert entry["options"]["heating_circuit"] == 2
    assert entry["data"]["api_version"] == ApiVersion.V_23_020.label
    assert entry["data"]["system"] is not None


async def test_diagnostics_report_the_registers_of_every_component(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """A value the heating system reports is the point of the whole download.

    The components that can exist several times over are a list even when only
    one is configured, so that the index in an entity name lines up with it.
    """
    diagnostics = await _diagnostics(hass, heating_circuit=1, heatpump=True)

    components = diagnostics["components"]
    circuit = components["heating_circuits.1"]

    assert circuit["supply_temperature"]["value"] == 0
    assert "mixer_valve" in circuit
    assert components["heat_pump"]["compressor_speed"]["value"] == 0
    # A calculated value is not a register but is read like one, and it is the
    # first thing asked about when a COP looks wrong
    assert "cop_heating" in components["heat_pump"]
    # More than the value: the address it came from, the raw words before
    # scaling and the unit. A sentinel reading has a raw value and no decoded
    # one, which is how a report tells "no sensor fitted" from "never read" -
    # and it is the same shape as `python -m aiosolarfocus dump`.
    assert circuit["supply_temperature"]["address"] == 1100
    assert circuit["supply_temperature"]["unit"] == "°C"
    assert circuit["supply_temperature"]["raw"] == 0


async def test_diagnostics_leave_out_a_component_that_is_not_configured(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """A component the user does not have is not in the snapshot at all.

    It used to be reported as `null`, because the shape of the download was a
    fixed list of every component the integration knows. The snapshot is what
    the entry actually has.
    """
    diagnostics = await _diagnostics(hass, heating_circuit=1)

    assert set(diagnostics["components"]) == {"heating_circuits.1"}


async def test_diagnostics_name_the_components_that_could_not_be_read(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """Which component is failing is what a partial failure comes down to.

    It is only in the log otherwise, once, so a download taken later would not
    show it at all.
    """
    entry = build_config_entry(heating_circuit=1, boiler=1)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["coordinator"]["last_update_success"] is True
    assert diagnostics["coordinator"]["failed_components"] == []

    mock_client.silence(ComponentId.BOILERS)
    await entry.runtime_data.async_refresh()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["coordinator"]["last_update_success"] is True
    assert diagnostics["coordinator"]["failed_components"] == ["boiler.1"]


async def test_diagnostics_do_not_blame_one_component_for_a_whole_outage(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """A component named here is one that fails while the others read fine.

    When the heating system stops answering altogether the refresh fails, and
    that is what the download says. Naming the component that happened to be
    failing before would point a report at the wrong thing.
    """
    entry = build_config_entry(heating_circuit=1, boiler=1)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_client.silence(ComponentId.BOILERS)
    await entry.runtime_data.async_refresh()

    assert (await async_get_config_entry_diagnostics(hass, entry))["coordinator"][
        "failed_components"
    ] == ["boiler.1"]

    mock_client.silence(ComponentId.HEATING_CIRCUITS)
    await entry.runtime_data.async_refresh()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["coordinator"]["last_update_success"] is False
    assert diagnostics["coordinator"]["failed_components"] == []
