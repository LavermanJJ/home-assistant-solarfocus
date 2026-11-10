"""Test the Solarfocus config flow.

Covers the `config-flow-test-coverage` item of Home Assistant's integration
quality scale (issue #125): every step, every error path and the options flow.
"""

from unittest.mock import patch

from aiosolarfocus import (
    ApiVersion,
    ComponentCounts,
    Detection,
    SolarfocusProtocolError,
    Systems,
)
import pytest

from custom_components.solarfocus.config_flow import (
    CannotConnect,
    InvalidAuth,
    InvalidScanInterval,
    _detected_differently,
    _suggested_components,
    validate_input,
)
from custom_components.solarfocus.const import (
    CONF_BIOMASS_BOILER,
    CONF_BOILER,
    CONF_BUFFER,
    CONF_CIRCULATION,
    CONF_DIFFERENTIAL_MODULE,
    CONF_DOOR_CONTACT_INVERTED,
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
    CONF_API_VERSION: ApiVersion.V_23_020.label,
}

VAMPAIR_COMPONENTS = {
    CONF_HEATING_CIRCUIT: 2,
    CONF_BUFFER: 1,
    CONF_BOILER: 1,
    CONF_FRESH_WATER_MODULE: 0,
    CONF_CIRCULATION: 0,
    CONF_DIFFERENTIAL_MODULE: 0,
    CONF_HEATPUMP: True,
    CONF_PHOTOVOLTAIC: False,
    CONF_SOLAR: 0,
}

THERMINATOR_COMPONENTS = {
    CONF_HEATING_CIRCUIT: 1,
    CONF_BUFFER: 1,
    CONF_BOILER: 1,
    CONF_FRESH_WATER_MODULE: 1,
    CONF_CIRCULATION: 2,
    CONF_DIFFERENTIAL_MODULE: 1,
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


@pytest.mark.parametrize("step", ["user", "reconfigure"])
async def test_every_api_version_of_the_library_is_offered(
    hass: HomeAssistant, enable_custom_integrations, mock_client, step: str
) -> None:
    """Regression test for #218: 25.100 was missing from the hand-kept list.

    Every version `pysolarfocus` speaks is one a controller in the field can be
    on, so leaving one out means the user picks a lower one and silently loses
    the registers added since. Both forms that ask for the version read the
    same list, newest first.
    """
    if step == "user":
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
    else:
        entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
        entry.add_to_hass(hass)
        result = await _start_reconfigure(hass, entry)

    versions = _offered_api_versions(result)

    # `label`, not `value`: an `ApiVersion` is numbered so that `>=` is the
    # comparison the register table needs, and the entry stores the version
    # the way the controller prints it on its own screen.
    assert versions == [api_version.label for api_version in reversed(ApiVersion)]
    assert ApiVersion.V_25_100.label in versions


def _offered_api_versions(result) -> list[str]:
    """Return the versions the version selector of a form offers, in order."""
    schema = result["data_schema"].schema
    selector_config = next(
        value.config for key, value in schema.items() if key.schema == CONF_API_VERSION
    )
    return [option["value"] for option in selector_config["options"]]


async def test_a_newly_offered_api_version_can_be_chosen(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """The version the selector gained is the version the entry ends up on."""
    result = await _start_user_step(
        hass, {**USER_INPUT, CONF_API_VERSION: ApiVersion.V_25_100.label}
    )

    with patch("custom_components.solarfocus.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], VAMPAIR_COMPONENTS
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_VERSION] == ApiVersion.V_25_100.label


async def test_full_flow_vampair(
    hass: HomeAssistant, enable_custom_integrations, mock_client
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
    # What it takes to read the system is data, what the user chose about it
    # is options
    assert result["data"] == {
        CONF_NAME: DEFAULT_NAME,
        CONF_SOLARFOCUS_SYSTEM: Systems.VAMPAIR,
        CONF_HOST: "solarfocus.local",
        CONF_PORT: 502,
        CONF_API_VERSION: ApiVersion.V_23_020.label,
    }
    assert result["options"] == {
        CONF_SCAN_INTERVAL: 10,
        CONF_HEATING_CIRCUIT: 2,
        CONF_BUFFER: 1,
        CONF_BOILER: 1,
        CONF_FRESH_WATER_MODULE: 0,
        CONF_CIRCULATION: 0,
        CONF_DIFFERENTIAL_MODULE: 0,
        CONF_PHOTOVOLTAIC: False,
        CONF_SOLAR: 0,
        CONF_HEATPUMP: True,
        # A heat pump system never has a biomass boiler
        CONF_BIOMASS_BOILER: False,
        # Not asked in the wizard - see #91. A vampair never has a door
        # contact either, so this is only ever changed under Configure.
        CONF_DOOR_CONTACT_INVERTED: False,
    }
    assert len(setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "system",
    [
        Systems.THERMINATOR,
        Systems.ECOTOP,
        # Regression test for #217: the component step branched on the three
        # systems the dropdown used to offer and had no else, so a fourth left
        # both heat source flags unset and raised `KeyError` on the next line.
        Systems.PELLETELEGANCE,
        Systems.OCTOPLUS,
    ],
)
async def test_full_flow_biomass_systems(
    hass: HomeAssistant, enable_custom_integrations, mock_client, system: Systems
) -> None:
    """Biomass systems are stored with the heat pump disabled.

    A therminator is not asked for a fresh water module, which it cannot have,
    and is stored with none.
    """
    fresh_water_modules = 0 if system is Systems.THERMINATOR else 1
    result = await _start_user_step(hass, {**USER_INPUT, CONF_SOLARFOCUS_SYSTEM: system})

    assert result["step_id"] == "component"

    with patch("custom_components.solarfocus.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                option: value
                for option, value in THERMINATOR_COMPONENTS.items()
                if option != CONF_FRESH_WATER_MODULE or fresh_water_modules
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SOLARFOCUS_SYSTEM] == system
    assert result["options"][CONF_BIOMASS_BOILER] is True
    assert result["options"][CONF_HEATPUMP] is False
    assert result["options"][CONF_SOLAR] == 2
    assert result["options"][CONF_FRESH_WATER_MODULE] == fresh_water_modules
    assert result["options"][CONF_CIRCULATION] == 2
    assert result["options"][CONF_DIFFERENTIAL_MODULE] == 1
    assert result["options"][CONF_DOOR_CONTACT_INVERTED] is False


async def test_form_cannot_connect(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """A device that does not answer keeps the user on the first step."""
    mock_client.offline()

    result = await _start_user_step(hass, USER_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_recovers_after_connection_error(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """The user can retry once the device is reachable."""
    mock_client.offline()
    result = await _start_user_step(hass, USER_INPUT)
    assert result["errors"] == {"base": "cannot_connect"}

    mock_client.online()
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
    hass: HomeAssistant, enable_custom_integrations, mock_client
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
    hass: HomeAssistant, enable_custom_integrations, mock_client
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
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """A second entry for the same address would poll one system twice."""
    build_config_entry().add_to_hass(hass)

    result = await _start_user_step(hass, USER_INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_a_second_system_can_be_added(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """A different address is a different heating system."""
    build_config_entry().add_to_hass(hass)

    result = await _start_user_step(
        hass, {**USER_INPUT, CONF_HOST: "10.0.0.9", CONF_NAME: "Solarfocus cabin"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "component"


async def test_a_second_system_may_share_the_name_of_the_first(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """Nothing of an entry is identified by its name any more.

    A second entry under a name that is taken used to give every entity of it
    the unique id an entity of the first already had, so the setup refused one.
    Entities are identified by the entry id since version 10, and two heating
    systems that the user thinks of under one name are their business.
    """
    build_config_entry().add_to_hass(hass)

    result = await _start_user_step(hass, {**USER_INPUT, CONF_HOST: "10.0.0.9"})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "component"


async def test_a_different_port_is_a_different_system(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """Two controllers can sit behind one address on different ports."""
    build_config_entry().add_to_hass(hass)

    result = await _start_user_step(
        hass, {**USER_INPUT, CONF_PORT: 503, CONF_NAME: "Solarfocus cabin"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "component"


async def test_validate_input_raises_cannot_connect(
    hass: HomeAssistant, mock_client
) -> None:
    """Validate_input surfaces a failed connection."""
    mock_client.offline()

    with pytest.raises(CannotConnect):
        await validate_input(hass, USER_INPUT)


async def test_validate_input_raises_invalid_scan_interval(
    hass: HomeAssistant, mock_client
) -> None:
    """Validate_input enforces the minimum scan interval."""
    with pytest.raises(InvalidScanInterval):
        await validate_input(hass, {**USER_INPUT, CONF_SCAN_INTERVAL: 4})


async def test_validate_input_returns_title(hass: HomeAssistant, mock_client) -> None:
    """Validate_input returns the entry title on success."""
    info = await validate_input(hass, USER_INPUT)

    assert info["title"] == DEFAULT_NAME
    # What the controller reported, for the forms that follow.
    assert info["detection"].api_version is ApiVersion.V_23_020


@pytest.mark.parametrize(
    "system", [Systems.VAMPAIR, Systems.THERMINATOR, Systems.ECOTOP]
)
async def test_options_flow_form(
    hass: HomeAssistant, enable_custom_integrations, mock_client, system: Systems
) -> None:
    """Each system gets an options form prefilled from the stored options."""
    entry = build_config_entry(system, heating_circuit=1, buffer=1, boiler=1)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"] is not None


OPTIONS_INPUT = {
    CONF_SCAN_INTERVAL: 30,
    CONF_HEATING_CIRCUIT: 3,
    CONF_BUFFER: 2,
    CONF_BOILER: 1,
    CONF_FRESH_WATER_MODULE: 1,
    CONF_CIRCULATION: 1,
    CONF_DIFFERENTIAL_MODULE: 1,
    CONF_HEATPUMP: True,
    CONF_PHOTOVOLTAIC: True,
    CONF_SOLAR: 1,
}


async def test_options_flow_updates_options(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """Submitting the options form stores the new values."""
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    with patch("custom_components.solarfocus.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], OPTIONS_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SCAN_INTERVAL] == 30
    assert result["data"][CONF_HEATING_CIRCUIT] == 3
    assert result["data"][CONF_HEATPUMP] is True
    assert result["data"][CONF_BIOMASS_BOILER] is False


async def test_the_options_form_does_not_ask_for_the_connection(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """Where the system is belongs to the entry data and the reconfigure flow.

    Asking for it here as well was how the same setting ended up in both
    halves of the entry, and how a user came to the form to add a heating
    circuit and left having changed the address.
    """
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    fields = {key.schema for key in result["data_schema"].schema}

    assert fields.isdisjoint({CONF_HOST, CONF_PORT, CONF_API_VERSION, CONF_NAME})
    assert CONF_SCAN_INTERVAL in fields
    assert CONF_HEATING_CIRCUIT in fields


async def test_saving_options_leaves_the_connection_alone(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """The data of the entry is not the options flow's to write."""
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    before = dict(entry.data)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(result["flow_id"], OPTIONS_INPUT)
    await hass.async_block_till_done()

    assert entry.data == before
    assert entry.options[CONF_SCAN_INTERVAL] == 30
    assert entry.unique_id == "solarfocus.local:502"


async def test_a_legacy_duplicate_can_still_edit_its_options(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """The migration leaves one of two entries for a system without a unique id.

    That entry shares its address with the other one by definition, so nothing
    about saving its options may refuse it - that would lock the entry out of
    its own form.
    """
    first = build_config_entry()
    first.add_to_hass(hass)
    duplicate = build_config_entry(Systems.VAMPAIR, heatpump=True)
    duplicate.add_to_hass(hass)
    hass.config_entries.async_update_entry(duplicate, unique_id=None)

    result = await hass.config_entries.options.async_init(duplicate.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], OPTIONS_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert duplicate.options[CONF_SCAN_INTERVAL] == 30
    # It stays without one; the address belongs to the other entry.
    assert duplicate.unique_id is None


async def test_options_flow_biomass_system_disables_heatpump(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """A therminator keeps the biomass boiler flag and never enables the heat pump."""
    entry = build_config_entry(
        Systems.THERMINATOR, heating_circuit=1, biomassboiler=True
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    with patch("custom_components.solarfocus.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_SCAN_INTERVAL: 10,
                CONF_HEATING_CIRCUIT: 1,
                CONF_BUFFER: 1,
                CONF_BOILER: 1,
                CONF_CIRCULATION: 0,
                CONF_DIFFERENTIAL_MODULE: 0,
                CONF_BIOMASS_BOILER: True,
                CONF_PHOTOVOLTAIC: False,
                CONF_SOLAR: 0,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BIOMASS_BOILER] is True
    assert result["data"][CONF_HEATPUMP] is False
    # Not asked of a therminator, and still an option every platform reads.
    assert result["data"][CONF_FRESH_WATER_MODULE] == 0


# --- what the controller says it is ------------------------------------------


def _detection(
    system: Systems = Systems.VAMPAIR,
    api_version: ApiVersion = ApiVersion.V_23_020,
    *,
    confident: bool = True,
    photovoltaic: bool = False,
    **counts: int,
) -> Detection:
    """Return what a controller of this kind would have been detected as."""
    return Detection(
        api_version=api_version,
        system=system,
        counts=ComponentCounts(**counts),
        has_heat_pump=confident and system is Systems.VAMPAIR,
        has_biomass_boiler=confident and system is not Systems.VAMPAIR,
        has_photovoltaic=photovoltaic,
        has_fresh_water_module_cascade=False,
        has_circulation_module=False,
        evidence={},
        reads=0,
    )


@pytest.mark.parametrize(
    ("detected", "system", "api_version"),
    [
        # Exactly what was chosen.
        (_detection(), Systems.VAMPAIR, "23.020"),
        # No release between the two added a register to date it by.
        (_detection(api_version=ApiVersion.V_25_030), Systems.VAMPAIR, "25.100"),
        # 25.020 and 25.030 added theirs together.
        (_detection(api_version=ApiVersion.V_25_030), Systems.VAMPAIR, "25.020"),
        # Nothing in the registers separates these two, and the detection
        # calls both a pellet elegance.
        (_detection(Systems.PELLETELEGANCE), Systems.ECOTOP, "23.020"),
        # A heat generator that did not identify itself is a default, not a
        # finding.
        (_detection(Systems.VAMPAIR, confident=False), Systems.THERMINATOR, "23.020"),
    ],
)
def test_a_choice_the_controller_does_not_contradict_is_not_questioned(
    detected: Detection, system: Systems, api_version: str
) -> None:
    assert _detected_differently(detected, system, api_version) is None


@pytest.mark.parametrize(
    ("detected", "system", "api_version", "expected"),
    [
        # The registers of a later release are there and would go unread.
        (
            _detection(api_version=ApiVersion.V_26_020),
            Systems.VAMPAIR,
            "23.020",
            {"system": "Vampair", "api_version": "26.020"},
        ),
        # The registers of the chosen release are not there to read.
        (
            _detection(api_version=ApiVersion.V_23_020),
            Systems.VAMPAIR,
            "25.030",
            {"system": "Vampair", "api_version": "23.020"},
        ),
        (
            _detection(Systems.THERMINATOR),
            Systems.VAMPAIR,
            "23.020",
            {"system": "Therminator", "api_version": "23.020"},
        ),
        # The version is still a finding where the system is not, and the
        # system named is then the one that was chosen.
        (
            _detection(Systems.VAMPAIR, ApiVersion.V_26_020, confident=False),
            Systems.ECOTOP,
            "23.020",
            {"system": "Ecotop", "api_version": "26.020"},
        ),
    ],
)
def test_a_choice_the_controller_contradicts_is_named(
    detected: Detection, system: Systems, api_version: str, expected: dict[str, str]
) -> None:
    assert _detected_differently(detected, system, api_version) == expected


def test_nothing_detected_questions_nothing() -> None:
    assert _detected_differently(None, Systems.VAMPAIR, "23.020") is None
    assert _suggested_components(None, Systems.VAMPAIR) == {}
    # A controller that reported nothing was not understood, and a form of
    # zeroes is a worse start than the defaults.
    assert _suggested_components(_detection(), Systems.VAMPAIR) == {}


def test_a_therminator_is_not_suggested_the_fresh_water_module_it_cannot_have() -> None:
    detected = _detection(Systems.THERMINATOR, heating_circuits=2, fresh_water_modules=1)

    assert _suggested_components(detected, Systems.THERMINATOR)[CONF_FRESH_WATER_MODULE] == 0
    assert _suggested_components(detected, Systems.ECOTOP)[CONF_FRESH_WATER_MODULE] == 1


async def test_a_contradicted_choice_is_questioned_once_and_then_taken(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """The controller's own screen outranks what its registers suggest."""
    detected = _detection(Systems.THERMINATOR, ApiVersion.V_26_020)

    with patch(
        "custom_components.solarfocus.config_flow._detect", return_value=detected
    ):
        result = await _start_user_step(hass, USER_INPUT)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "detected_differently"}
        assert result["description_placeholders"] == {
            "system": "Therminator",
            "api_version": "26.020",
        }
        # The form comes back as it was filled in, not as its defaults.
        suggested = {
            str(marker): marker.description["suggested_value"]
            for marker in result["data_schema"].schema
        }
        assert suggested[CONF_HOST] == "solarfocus.local"
        assert suggested[CONF_API_VERSION] == "23.020"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["step_id"] == "component"


async def test_a_corrected_choice_is_checked_again(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """Sending a different answer is not the same as insisting on the first."""
    detected = _detection(Systems.THERMINATOR, ApiVersion.V_26_020)

    with patch(
        "custom_components.solarfocus.config_flow._detect", return_value=detected
    ):
        result = await _start_user_step(hass, USER_INPUT)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**USER_INPUT, CONF_API_VERSION: ApiVersion.V_26_020.label},
        )
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "detected_differently"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                **USER_INPUT,
                CONF_SOLARFOCUS_SYSTEM: Systems.THERMINATOR,
                CONF_API_VERSION: ApiVersion.V_26_020.label,
            },
        )

    assert result["step_id"] == "component"


async def test_the_component_form_starts_from_what_the_controller_reported(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    detected = _detection(heating_circuits=3, buffers=2, solar=1, photovoltaic=True)

    with patch(
        "custom_components.solarfocus.config_flow._detect", return_value=detected
    ):
        result = await _start_user_step(hass, USER_INPUT)

    assert result["step_id"] == "component"
    suggested = {
        str(marker): marker.description["suggested_value"]
        for marker in result["data_schema"].schema
        if marker.description
    }
    assert suggested[CONF_HEATING_CIRCUIT] == 3
    assert suggested[CONF_BUFFER] == 2
    assert suggested[CONF_BOILER] == 0
    assert suggested[CONF_SOLAR] == 1
    assert suggested[CONF_PHOTOVOLTAIC] is True
    # Which heat source there is follows the system, and is not suggested.
    assert CONF_HEATPUMP not in suggested


async def test_a_controller_that_cannot_be_detected_is_still_set_up_by_hand(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """Detection is advice for the forms, never a condition of getting through."""
    with patch(
        "aiosolarfocus.SolarfocusClient.detect",
        side_effect=SolarfocusProtocolError("asked for 1 registers and got 2"),
    ):
        result = await _start_user_step(hass, USER_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "component"
    assert not result.get("errors")


# --- reconfigure -------------------------------------------------------------

RECONFIGURE_INPUT = {
    CONF_HOST: "10.0.0.5",
    CONF_PORT: 503,
    CONF_SCAN_INTERVAL: 30,
    CONF_API_VERSION: ApiVersion.V_25_030.label,
}


async def _start_reconfigure(hass: HomeAssistant, entry) -> dict:
    """Open the reconfigure form of an entry."""
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )


async def test_reconfigure_form_starts_from_the_current_connection(
    hass: HomeAssistant, enable_custom_integrations, mock_client
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
    hass: HomeAssistant, enable_custom_integrations, mock_client
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

    assert entry.data[CONF_HOST] == "10.0.0.5"
    assert entry.data[CONF_PORT] == 503
    assert entry.options[CONF_SCAN_INTERVAL] == 30
    assert entry.data[CONF_API_VERSION] == ApiVersion.V_25_030.label
    assert entry.unique_id == "10.0.0.5:503"


async def test_reconfigure_reloads_the_entry_once(
    hass: HomeAssistant, enable_custom_integrations, mock_client
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
    hass: HomeAssistant, enable_custom_integrations, mock_client
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


async def test_reconfigure_changes_the_system(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """Regression test for #217.

    Which system an entry is was asked once in the user step and never again,
    so an owner who picked the nearest of the three that used to be offered
    could only correct it by deleting the entry and losing its history.
    """
    entry = build_config_entry(
        Systems.ECOTOP, heating_circuit=1, biomassboiler=True
    )
    entry.add_to_hass(hass)

    result = await _start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**RECONFIGURE_INPUT, CONF_SOLARFOCUS_SYSTEM: Systems.PELLETELEGANCE},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_SOLARFOCUS_SYSTEM] == Systems.PELLETELEGANCE


async def test_reconfigure_starts_from_the_current_system(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """The system is being corrected, not chosen again from scratch."""
    entry = build_config_entry(Systems.ECOTOP, biomassboiler=True)
    entry.add_to_hass(hass)

    result = await _start_reconfigure(hass, entry)

    defaults = {
        key.schema: key.default() for key in result["data_schema"].schema if key.default
    }

    assert defaults[CONF_SOLARFOCUS_SYSTEM] == Systems.ECOTOP


async def test_reconfigure_between_biomass_systems_keeps_the_heat_source(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """Both have a biomass boiler, so there is nothing to switch over.

    Someone who turned the biomass boiler off in the options meant it, and
    correcting the model of the boiler is no reason to turn it back on.
    """
    entry = build_config_entry(
        Systems.ECOTOP, heating_circuit=1, biomassboiler=False
    )
    entry.add_to_hass(hass)

    result = await _start_reconfigure(hass, entry)
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**RECONFIGURE_INPUT, CONF_SOLARFOCUS_SYSTEM: Systems.PELLETELEGANCE},
    )
    await hass.async_block_till_done()

    assert entry.options[CONF_BIOMASS_BOILER] is False
    assert entry.options[CONF_HEATPUMP] is False


async def test_reconfigure_to_a_therminator_drops_the_fresh_water_modules(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """The one system that cannot have one, and the library refuses to be told so.

    Carried over, the count would fail the setup the reconfiguration ends in.
    """
    entry = build_config_entry(
        Systems.ECOTOP, heating_circuit=1, biomassboiler=True, fresh_water_module=2
    )
    entry.add_to_hass(hass)

    result = await _start_reconfigure(hass, entry)
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**RECONFIGURE_INPUT, CONF_SOLARFOCUS_SYSTEM: Systems.THERMINATOR},
    )
    await hass.async_block_till_done()

    assert entry.options[CONF_FRESH_WATER_MODULE] == 0


async def test_the_options_of_a_therminator_do_not_ask_for_a_fresh_water_module(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    therminator = build_config_entry(Systems.THERMINATOR, biomassboiler=True)
    ecotop = build_config_entry(Systems.ECOTOP, biomassboiler=True)
    asked = {}
    for entry in (therminator, ecotop):
        entry.add_to_hass(hass)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        asked[entry.data[CONF_SOLARFOCUS_SYSTEM]] = {
            str(marker) for marker in result["data_schema"].schema
        }

    assert CONF_FRESH_WATER_MODULE not in asked[Systems.THERMINATOR]
    assert CONF_FRESH_WATER_MODULE in asked[Systems.ECOTOP]


async def test_reconfigure_to_a_heat_pump_switches_the_heat_source(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """The component step only ever offers the heat source the system has.

    So crossing between them here has to switch the flags over, or the entry
    would go on reading a biomass boiler the vampair does not have.
    """
    entry = build_config_entry(
        Systems.ECOTOP, heating_circuit=1, biomassboiler=True
    )
    entry.add_to_hass(hass)

    result = await _start_reconfigure(hass, entry)
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**RECONFIGURE_INPUT, CONF_SOLARFOCUS_SYSTEM: Systems.VAMPAIR},
    )
    await hass.async_block_till_done()

    assert entry.options[CONF_HEATPUMP] is True
    assert entry.options[CONF_BIOMASS_BOILER] is False


async def test_reconfigure_to_a_biomass_system_switches_the_heat_source(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """And the same crossing the other way."""
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)

    result = await _start_reconfigure(hass, entry)
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**RECONFIGURE_INPUT, CONF_SOLARFOCUS_SYSTEM: Systems.PELLETELEGANCE},
    )
    await hass.async_block_till_done()

    assert entry.options[CONF_BIOMASS_BOILER] is True
    assert entry.options[CONF_HEATPUMP] is False


async def test_reconfigure_refuses_the_address_of_another_entry(
    hass: HomeAssistant, enable_custom_integrations, mock_client
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
    assert entry.data[CONF_HOST] == "solarfocus.local"


async def test_reconfigure_reports_a_system_it_cannot_reach(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """An address that answers nothing is the mistake this form is for."""
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)

    mock_client.offline()

    result = await _start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data[CONF_HOST] == "solarfocus.local"


async def test_reconfigure_rejects_a_polling_interval_below_five(
    hass: HomeAssistant, enable_custom_integrations, mock_client
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
    hass: HomeAssistant, enable_custom_integrations, mock_client
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
    assert entry.data[CONF_HOST] == "10.0.0.5"
    assert entry.unique_id is None


async def test_reconfigure_reports_an_unexpected_failure(
    hass: HomeAssistant, enable_custom_integrations, mock_client
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
    assert entry.data[CONF_HOST] == "solarfocus.local"


async def test_options_flow_scan_interval_below_minimum(
    hass: HomeAssistant, enable_custom_integrations, mock_client
) -> None:
    """The options form has the same floor, and reports it the same way."""
    entry = build_config_entry(Systems.VAMPAIR, heating_circuit=1, heatpump=True)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**OPTIONS_INPUT, CONF_SCAN_INTERVAL: 1}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_SCAN_INTERVAL: "invalid_scan_interval"}
