"""Test the Solarfocus config flow.

Covers the `config-flow-test-coverage` item of Home Assistant's integration
quality scale (issue #125): every step, every error path and the options flow.
"""

from unittest.mock import patch

from pysolarfocus import ApiVersions, Systems
import pytest

from custom_components.solarfocus.config_flow import (
    CannotConnect,
    InvalidAuth,
    InvalidScanInterval,
    validate_input,
)
from custom_components.solarfocus.const import (
    CONF_BIOMASS_BOILER,
    CONF_BOILER,
    CONF_BUFFER,
    CONF_FRESH_WATER_MODULE,
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
    CONF_PHOTOVOLTAIC,
    CONF_SOLAR,
    CONF_SOLARFOCUS_SYSTEM,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import build_config_entry

USER_INPUT = {
    CONF_NAME: DEFAULT_NAME,
    CONF_HOST: "solarfocus.local",
    CONF_PORT: 502,
    CONF_SCAN_INTERVAL: 10,
    CONF_SOLARFOCUS_SYSTEM: Systems.VAMPAIR,
    CONF_API_VERSION: ApiVersions.V_23_020.value,
}

VAMPAIR_COMPONENTS = {
    CONF_HEATING_CIRCUIT: 2,
    CONF_BUFFER: 1,
    CONF_BOILER: 1,
    CONF_FRESH_WATER_MODULE: 0,
    CONF_HEATPUMP: True,
    CONF_PHOTOVOLTAIC: False,
    CONF_SOLAR: 0,
}

THERMINATOR_COMPONENTS = {
    CONF_HEATING_CIRCUIT: 1,
    CONF_BUFFER: 1,
    CONF_BOILER: 1,
    CONF_FRESH_WATER_MODULE: 1,
    CONF_BIOMASS_BOILER: True,
    CONF_PHOTOVOLTAIC: True,
    CONF_SOLAR: 2,
}


async def _start_user_step(hass: HomeAssistant, user_input: dict) -> dict:
    """Run the user step and return its result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )


async def test_form_shown_without_input(
    hass: HomeAssistant, enable_custom_integrations
) -> None:
    """The flow starts by asking for the connection details."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None


async def test_full_flow_vampair(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """A vampair system is stored with the heat pump enabled."""
    result = await _start_user_step(hass, USER_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "component"

    with patch(
        "custom_components.solarfocus.async_setup_entry", return_value=True
    ) as setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], VAMPAIR_COMPONENTS
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        CONF_NAME: DEFAULT_NAME,
        CONF_SOLARFOCUS_SYSTEM: Systems.VAMPAIR,
    }
    assert result["options"] == {
        CONF_HOST: "solarfocus.local",
        CONF_PORT: 502,
        CONF_SCAN_INTERVAL: 10,
        CONF_API_VERSION: ApiVersions.V_23_020.value,
        CONF_HEATING_CIRCUIT: 2,
        CONF_BUFFER: 1,
        CONF_BOILER: 1,
        CONF_FRESH_WATER_MODULE: 0,
        CONF_PHOTOVOLTAIC: False,
        CONF_SOLAR: 0,
        CONF_HEATPUMP: True,
        # A heat pump system never has a biomass boiler
        CONF_BIOMASS_BOILER: False,
    }
    assert len(setup_entry.mock_calls) == 1


@pytest.mark.parametrize("system", [Systems.THERMINATOR, Systems.ECOTOP])
async def test_full_flow_biomass_systems(
    hass: HomeAssistant, enable_custom_integrations, mock_api, system: Systems
) -> None:
    """Biomass systems are stored with the heat pump disabled."""
    result = await _start_user_step(hass, {**USER_INPUT, CONF_SOLARFOCUS_SYSTEM: system})

    assert result["step_id"] == "component"

    with patch("custom_components.solarfocus.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], THERMINATOR_COMPONENTS
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SOLARFOCUS_SYSTEM] == system
    assert result["options"][CONF_BIOMASS_BOILER] is True
    assert result["options"][CONF_HEATPUMP] is False
    assert result["options"][CONF_SOLAR] == 2
    assert result["options"][CONF_FRESH_WATER_MODULE] == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """A device that does not answer keeps the user on the first step."""
    api.connect.return_value = False

    result = await _start_user_step(hass, USER_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_recovers_after_connection_error(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """The user can retry once the device is reachable."""
    api.connect.return_value = False
    result = await _start_user_step(hass, USER_INPUT)
    assert result["errors"] == {"base": "cannot_connect"}

    api.connect.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "component"


async def test_form_invalid_auth(
    hass: HomeAssistant, enable_custom_integrations
) -> None:
    """An authentication problem is reported on the form."""
    with patch(
        "custom_components.solarfocus.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result = await _start_user_step(hass, USER_INPUT)

    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_unknown_error(
    hass: HomeAssistant, enable_custom_integrations
) -> None:
    """Any other exception is reported as an unknown error."""
    with patch(
        "custom_components.solarfocus.config_flow.validate_input",
        side_effect=RuntimeError("boom"),
    ):
        result = await _start_user_step(hass, USER_INPUT)

    assert result["errors"] == {"base": "unknown"}


async def test_form_scan_interval_below_minimum(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """A scan interval below five seconds is reported on the field it is in.

    It used to fall through to the broad handler and be shown as "unknown
    error", with a traceback in the log, which says nothing about the one field
    the user has to change.
    """
    result = await _start_user_step(hass, {**USER_INPUT, CONF_SCAN_INTERVAL: 1})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_SCAN_INTERVAL: "invalid_scan_interval"}


async def test_entry_is_identified_by_its_address(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """The address the controller is reached at identifies the entry."""
    result = await _start_user_step(hass, USER_INPUT)

    with patch("custom_components.solarfocus.async_setup_entry", return_value=True):
        await hass.config_entries.flow.async_configure(
            result["flow_id"], VAMPAIR_COMPONENTS
        )
        await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == "solarfocus.local:502"


async def test_the_same_system_cannot_be_added_twice(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """A second entry for the same address would poll one system twice."""
    build_config_entry().add_to_hass(hass)

    result = await _start_user_step(hass, USER_INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_a_second_system_can_be_added(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """A different address is a different heating system."""
    build_config_entry().add_to_hass(hass)

    result = await _start_user_step(
        hass, {**USER_INPUT, CONF_HOST: "10.0.0.9", CONF_NAME: "Solarfocus cabin"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "component"


async def test_a_second_system_needs_its_own_name(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """Entities are identified by the title of their entry.

    A second entry under the same name gives every entity the unique id an
    entity of the first one already has, and Home Assistant drops them all.
    """
    build_config_entry().add_to_hass(hass)

    result = await _start_user_step(hass, {**USER_INPUT, CONF_HOST: "10.0.0.9"})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_NAME: "name_exists"}


async def test_a_different_port_is_a_different_system(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """Two controllers can sit behind one address on different ports."""
    build_config_entry().add_to_hass(hass)

    result = await _start_user_step(
        hass, {**USER_INPUT, CONF_PORT: 503, CONF_NAME: "Solarfocus cabin"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "component"


async def test_validate_input_raises_cannot_connect(
    hass: HomeAssistant, mock_api, api
) -> None:
    """Validate_input surfaces a failed connection."""
    api.connect.return_value = False

    with pytest.raises(CannotConnect):
        await validate_input(hass, USER_INPUT)


async def test_validate_input_raises_invalid_scan_interval(
    hass: HomeAssistant, mock_api
) -> None:
    """Validate_input enforces the minimum scan interval."""
    with pytest.raises(InvalidScanInterval):
        await validate_input(hass, {**USER_INPUT, CONF_SCAN_INTERVAL: 4})


async def test_validate_input_returns_title(hass: HomeAssistant, mock_api) -> None:
    """Validate_input returns the entry title on success."""
    assert await validate_input(hass, USER_INPUT) == {"title": DEFAULT_NAME}


@pytest.mark.parametrize(
    "system", [Systems.VAMPAIR, Systems.THERMINATOR, Systems.ECOTOP]
)
async def test_options_flow_form(
    hass: HomeAssistant, enable_custom_integrations, mock_api, system: Systems
) -> None:
    """Each system gets an options form prefilled from the stored options."""
    entry = build_config_entry(system, heating_circuit=1, buffer=1, boiler=1)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"] is not None


async def test_options_flow_updates_options(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """Submitting the options form stores the new values."""
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    with patch("custom_components.solarfocus.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "10.0.0.5",
                CONF_PORT: 503,
                CONF_SCAN_INTERVAL: 30,
                CONF_API_VERSION: ApiVersions.V_25_030.value,
                CONF_HEATING_CIRCUIT: 3,
                CONF_BUFFER: 2,
                CONF_BOILER: 1,
                CONF_FRESH_WATER_MODULE: 1,
                CONF_HEATPUMP: True,
                CONF_PHOTOVOLTAIC: True,
                CONF_SOLAR: 1,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "10.0.0.5"
    assert result["data"][CONF_PORT] == 503
    assert result["data"][CONF_SCAN_INTERVAL] == 30
    assert result["data"][CONF_API_VERSION] == ApiVersions.V_25_030.value
    assert result["data"][CONF_HEATING_CIRCUIT] == 3
    assert result["data"][CONF_HEATPUMP] is True
    assert result["data"][CONF_BIOMASS_BOILER] is False


async def test_options_flow_follows_the_address(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """Moving an entry to another address moves its unique id along.

    A stale unique id would let the same system be added a second time under
    its new address. The move happens on the reload that saving the options
    triggers, not in the flow itself, so this runs the real setup.
    """
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "10.0.0.5",
            CONF_PORT: 503,
            CONF_SCAN_INTERVAL: 30,
            CONF_API_VERSION: ApiVersions.V_25_030.value,
            CONF_HEATING_CIRCUIT: 1,
            CONF_BUFFER: 0,
            CONF_BOILER: 0,
            CONF_FRESH_WATER_MODULE: 0,
            CONF_HEATPUMP: True,
            CONF_PHOTOVOLTAIC: False,
            CONF_SOLAR: 0,
        },
    )
    await hass.async_block_till_done()

    assert entry.options[CONF_HOST] == "10.0.0.5"
    assert entry.unique_id == "10.0.0.5:503"


async def test_saving_options_does_not_reload_against_the_old_address(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """The entry is reloaded once, with the options the user just saved.

    Updating the unique id inside the flow fired the update listener before the
    new options were stored, so the entry was reloaded twice and the first of
    those reloads connected to the address the user had just left.
    """
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_api.reset_mock()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "10.0.0.5",
            CONF_PORT: 503,
            CONF_SCAN_INTERVAL: 30,
            CONF_API_VERSION: ApiVersions.V_25_030.value,
            CONF_HEATING_CIRCUIT: 1,
            CONF_BUFFER: 0,
            CONF_BOILER: 0,
            CONF_FRESH_WATER_MODULE: 0,
            CONF_HEATPUMP: True,
            CONF_PHOTOVOLTAIC: False,
            CONF_SOLAR: 0,
        },
    )
    await hass.async_block_till_done()

    setups = [call for call in mock_api.call_args_list if "heating_circuit_count" in call.kwargs]
    assert len(setups) == 1
    assert setups[0].kwargs["ip"] == "10.0.0.5"


async def test_options_flow_rejects_the_address_of_another_entry(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """Two entries must not end up pointing at the same system."""
    other = build_config_entry()
    other.add_to_hass(hass)
    entry = build_config_entry(Systems.VAMPAIR, host="10.0.0.5", heatpump=True)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_HOST: other.options[CONF_HOST],
            CONF_PORT: other.options[CONF_PORT],
            CONF_SCAN_INTERVAL: 10,
            CONF_API_VERSION: ApiVersions.V_23_020.value,
            CONF_HEATING_CIRCUIT: 0,
            CONF_BUFFER: 0,
            CONF_BOILER: 0,
            CONF_FRESH_WATER_MODULE: 0,
            CONF_HEATPUMP: True,
            CONF_PHOTOVOLTAIC: False,
            CONF_SOLAR: 0,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {"base": "already_configured"}
    assert entry.unique_id == "10.0.0.5:502"


async def test_a_legacy_duplicate_can_still_edit_its_options(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """The migration leaves one of two entries for a system without a unique id.

    That entry shares its address with the other one by definition, so the
    duplicate check must not fire for it - it would refuse every save and lock
    the entry out of its own options form.
    """
    first = build_config_entry()
    first.add_to_hass(hass)
    duplicate = build_config_entry(Systems.VAMPAIR, heatpump=True)
    duplicate.add_to_hass(hass)
    hass.config_entries.async_update_entry(duplicate, unique_id=None)

    result = await hass.config_entries.options.async_init(duplicate.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_HOST: first.options[CONF_HOST],
            CONF_PORT: first.options[CONF_PORT],
            CONF_SCAN_INTERVAL: 30,
            CONF_API_VERSION: ApiVersions.V_23_020.value,
            CONF_HEATING_CIRCUIT: 0,
            CONF_BUFFER: 0,
            CONF_BOILER: 0,
            CONF_FRESH_WATER_MODULE: 0,
            CONF_HEATPUMP: True,
            CONF_PHOTOVOLTAIC: False,
            CONF_SOLAR: 0,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert duplicate.options[CONF_SCAN_INTERVAL] == 30
    # It stays without one; the address belongs to the other entry.
    assert duplicate.unique_id is None


async def test_options_flow_biomass_system_disables_heatpump(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """A therminator keeps the biomass boiler flag and never enables the heat pump."""
    entry = build_config_entry(Systems.THERMINATOR, heating_circuit=1, biomassboiler=True)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    with patch("custom_components.solarfocus.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "solarfocus.local",
                CONF_PORT: 502,
                CONF_SCAN_INTERVAL: 10,
                CONF_API_VERSION: ApiVersions.V_23_020.value,
                CONF_HEATING_CIRCUIT: 1,
                CONF_BUFFER: 1,
                CONF_BOILER: 1,
                CONF_FRESH_WATER_MODULE: 0,
                CONF_BIOMASS_BOILER: True,
                CONF_PHOTOVOLTAIC: False,
                CONF_SOLAR: 0,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BIOMASS_BOILER] is True
    assert result["data"][CONF_HEATPUMP] is False


async def test_options_flow_cannot_connect(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """A device that stops answering keeps the user on the options form."""
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    api.connect.return_value = False
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "unreachable",
            CONF_PORT: 502,
            CONF_SCAN_INTERVAL: 10,
            CONF_API_VERSION: ApiVersions.V_23_020.value,
            CONF_HEATING_CIRCUIT: 1,
            CONF_BUFFER: 0,
            CONF_BOILER: 0,
            CONF_FRESH_WATER_MODULE: 0,
            CONF_HEATPUMP: True,
            CONF_PHOTOVOLTAIC: False,
            CONF_SOLAR: 0,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [(InvalidAuth, "invalid_auth"), (RuntimeError("boom"), "unknown")],
)
async def test_options_flow_errors(
    hass: HomeAssistant,
    enable_custom_integrations,
    mock_api,
    side_effect: Exception,
    expected: str,
) -> None:
    """Auth and unexpected failures are reported on the options form."""
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    with patch(
        "custom_components.solarfocus.config_flow.validate_input",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "solarfocus.local",
                CONF_PORT: 502,
                CONF_SCAN_INTERVAL: 10,
                CONF_API_VERSION: ApiVersions.V_23_020.value,
                CONF_HEATING_CIRCUIT: 1,
                CONF_BUFFER: 0,
                CONF_BOILER: 0,
                CONF_FRESH_WATER_MODULE: 0,
                CONF_HEATPUMP: True,
                CONF_PHOTOVOLTAIC: False,
                CONF_SOLAR: 0,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


# --- reconfigure -------------------------------------------------------------

RECONFIGURE_INPUT = {
    CONF_HOST: "10.0.0.5",
    CONF_PORT: 503,
    CONF_SCAN_INTERVAL: 30,
    CONF_API_VERSION: ApiVersions.V_25_030.value,
}


async def _start_reconfigure(hass: HomeAssistant, entry) -> dict:
    """Open the reconfigure form of an entry."""
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )


async def test_reconfigure_form_starts_from_the_current_connection(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """The form is for correcting an address, so it starts at the current one."""
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)

    result = await _start_reconfigure(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    defaults = {
        key.schema: key.default() for key in result["data_schema"].schema if key.default
    }

    assert defaults[CONF_HOST] == "solarfocus.local"
    assert defaults[CONF_PORT] == 502


async def test_reconfigure_moves_the_entry_and_its_unique_id(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """The address is the unique id, so changing one changes the other."""
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await _start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert entry.options[CONF_HOST] == "10.0.0.5"
    assert entry.options[CONF_PORT] == 503
    assert entry.options[CONF_SCAN_INTERVAL] == 30
    assert entry.options[CONF_API_VERSION] == ApiVersions.V_25_030.value
    assert entry.unique_id == "10.0.0.5:503"


async def test_reconfigure_reloads_the_entry_once(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """Saving the new address is what reloads the entry, and only that.

    The integration registers an update listener that reloads on an options
    change. Asking the flow to reload as well reloads twice, which Home
    Assistant reports from 2026.6 and refuses from 2026.12.
    """
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as async_reload:
        result = await _start_reconfigure(hass, entry)
        await hass.config_entries.flow.async_configure(
            result["flow_id"], RECONFIGURE_INPUT
        )
        await hass.async_block_till_done()

    assert async_reload.call_args_list == [((entry.entry_id,),)]


async def test_reconfigure_leaves_the_components_alone(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """The component layout belongs to the other form.

    Asking for it again here is how a user correcting an address ends up
    removing entities they still have.
    """
    entry = build_config_entry(
        Systems.VAMPAIR, heating_circuit=3, buffer=2, boiler=1, heatpump=True
    )
    entry.add_to_hass(hass)

    result = await _start_reconfigure(hass, entry)
    await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_INPUT
    )
    await hass.async_block_till_done()

    assert entry.options[CONF_HEATING_CIRCUIT] == 3
    assert entry.options[CONF_BUFFER] == 2
    assert entry.options[CONF_HEATPUMP] is True


async def test_reconfigure_refuses_the_address_of_another_entry(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """Two entries on one controller is what the unique id is there to stop."""
    other = build_config_entry(Systems.VAMPAIR, host="10.0.0.5", port=503)
    other.add_to_hass(hass)
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)

    result = await _start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "already_configured"}
    assert entry.options[CONF_HOST] == "solarfocus.local"


async def test_reconfigure_reports_a_system_it_cannot_reach(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """An address that answers nothing is the mistake this form is for."""
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)

    api.connect.return_value = False

    result = await _start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.options[CONF_HOST] == "solarfocus.local"


async def test_reconfigure_rejects_a_polling_interval_below_five(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """The same floor the user step enforces, reported on the field itself."""
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)

    result = await _start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**RECONFIGURE_INPUT, CONF_SCAN_INTERVAL: 1}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_SCAN_INTERVAL: "invalid_scan_interval"}


async def test_reconfigure_keeps_a_duplicate_entry_without_a_unique_id(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """The migration left it without one on purpose, see #185.

    Two entries for one controller predate the unique id. Giving this one an id
    here is exactly the collision the migration avoided, and it would take the
    entities of the entry that owns the address with it.
    """
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, unique_id=None)

    result = await _start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert entry.options[CONF_HOST] == "10.0.0.5"
    assert entry.unique_id is None


async def test_reconfigure_reports_an_unexpected_failure(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """Anything the library raises is the user's problem to see, not a traceback."""
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)

    result = await _start_reconfigure(hass, entry)

    with patch(
        "custom_components.solarfocus.config_flow.validate_input",
        side_effect=ValueError("something the library did not expect"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], RECONFIGURE_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
    assert entry.options[CONF_HOST] == "solarfocus.local"


async def test_options_flow_scan_interval_below_minimum(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """The options form has the same floor, and reports it the same way."""
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "solarfocus.local",
            CONF_PORT: 502,
            CONF_SCAN_INTERVAL: 1,
            CONF_API_VERSION: ApiVersions.V_23_020.value,
            CONF_HEATING_CIRCUIT: 1,
            CONF_BUFFER: 0,
            CONF_BOILER: 0,
            CONF_FRESH_WATER_MODULE: 0,
            CONF_HEATPUMP: True,
            CONF_PHOTOVOLTAIC: False,
            CONF_SOLAR: 0,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_SCAN_INTERVAL: "invalid_scan_interval"}
