"""The two things that need a person rather than a retry.

A repair issue is for what the integration cannot fix on its own. Both of these
are otherwise invisible: one is a log line written once at migration, the other
is a component quietly keeping its last value for good.
"""

from custom_components.solarfocus.const import CONF_BOILER, CONF_HEATING_CIRCUIT, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .conftest import build_config_entry


def _issue(hass: HomeAssistant, issue_id: str):
    return ir.async_get(hass).async_get_issue(DOMAIN, issue_id)


async def _setup(hass: HomeAssistant, **options):
    entry = build_config_entry(**options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_no_issue_for_an_entry_that_is_fine(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """A working entry raises nothing, which is what makes the rest mean something."""
    entry = await _setup(hass, heating_circuit=1, boiler=1)

    assert not ir.async_get(hass).issues
    assert entry.unique_id is not None


async def test_the_duplicate_the_migration_left_behind_is_reported(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """Two entries on one controller, from before the address identified one.

    The v7 migration leaves the second one without a unique id rather than
    colliding, so it keeps working and nothing says why there are two of every
    entity. Which one to remove is the user's call.
    """
    entry = build_config_entry(heating_circuit=1)
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, unique_id=None)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    issue = _issue(hass, f"duplicate_entry_{entry.entry_id}")

    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_placeholders["address"] == "solarfocus.local:502"


async def test_the_duplicate_issue_clears_once_the_entry_has_an_address(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """Removing the other entry and reloading is the fix, so it has to clear."""
    entry = build_config_entry(heating_circuit=1)
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, unique_id=None)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert _issue(hass, f"duplicate_entry_{entry.entry_id}") is not None

    hass.config_entries.async_update_entry(entry, unique_id="solarfocus.local:502")
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert _issue(hass, f"duplicate_entry_{entry.entry_id}") is None


async def test_a_component_that_answers_nothing_is_reported(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """A register range the firmware does not answer fails on every poll.

    The entities keep their last value rather than going unavailable, so the
    heating system looks stopped rather than partly unreadable.
    """
    api.update_heating.return_value = False

    entry = await _setup(hass, heating_circuit=1, boiler=1)

    issue = _issue(
        hass, f"component_unavailable_{entry.entry_id}_{CONF_HEATING_CIRCUIT}"
    )

    assert issue is not None
    assert issue.translation_placeholders["component"] == CONF_HEATING_CIRCUIT
    assert issue.translation_placeholders["address"] == "solarfocus.local:502"
    # The component that reads fine has nothing raised against it
    assert _issue(hass, f"component_unavailable_{entry.entry_id}_{CONF_BOILER}") is None


async def test_a_component_coming_back_clears_only_its_own_issue(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """One issue per component, so a recovery leaves the others standing.

    The buffer reads fine throughout: every configured component failing is an
    outage rather than a partial failure, and fails the refresh instead.
    """
    api.update_heating.return_value = False
    api.update_boiler.return_value = False

    entry = await _setup(hass, heating_circuit=1, boiler=1, buffer=1)

    heating = f"component_unavailable_{entry.entry_id}_{CONF_HEATING_CIRCUIT}"
    boiler = f"component_unavailable_{entry.entry_id}_{CONF_BOILER}"

    assert _issue(hass, heating) is not None
    assert _issue(hass, boiler) is not None

    api.update_heating.return_value = True
    await entry.runtime_data.async_refresh()

    assert _issue(hass, heating) is None
    assert _issue(hass, boiler) is not None


async def test_nothing_is_raised_when_the_whole_system_is_unreachable(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """That is not a repair, it is an outage.

    Every configured component failing fails the refresh instead, which makes
    the entities unavailable and has Home Assistant retry. Asking the user to
    check their component selection for it would be wrong.
    """
    api.update_heating.return_value = False
    api.connect.return_value = False
    api.is_connected = False

    entry = build_config_entry(heating_circuit=1)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert not ir.async_get(hass).issues
