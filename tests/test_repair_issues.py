"""The two things that need a person rather than a retry.

A repair issue is for what the integration cannot fix on its own. Both of these
are otherwise invisible: one is a log line written once at migration, the other
is a component that has gone unavailable for good.
"""

from custom_components.solarfocus.const import (
    CONF_BOILER,
    CONF_BUFFER,
    CONF_FRESH_WATER_MODULE,
    CONF_HEATING_CIRCUIT,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir

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
    other = build_config_entry(heating_circuit=1)
    other.add_to_hass(hass)

    entry = build_config_entry(heating_circuit=1)
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, unique_id=None)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    issue = _issue(hass, f"duplicate_entry_{entry.entry_id}")

    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_placeholders["address"] == "solarfocus.local:502"


async def test_an_entry_alone_on_its_address_is_not_a_duplicate(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """Having no unique id is only worth reporting while something else has it.

    An entry that lost its unique id with nothing else on the address is the
    same entry the migration would have given one, so it is given one here
    rather than reported as a pair that does not exist.
    """
    entry = build_config_entry(heating_circuit=1)
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, unique_id=None)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.unique_id == "solarfocus.local:502"
    assert not ir.async_get(hass).issues


async def test_the_duplicate_issue_clears_once_the_other_entry_is_gone(
    hass: HomeAssistant, enable_custom_integrations, mock_api
) -> None:
    """Doing what the issue asks has to be what clears it.

    The user removes one of the two entries; the one they keep is still the
    one the migration left without a unique id, and takes the address over on
    its next load. Without that it asks them again for something they did.
    """
    other = build_config_entry(heating_circuit=1)
    other.add_to_hass(hass)

    entry = build_config_entry(heating_circuit=1)
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, unique_id=None)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert _issue(hass, f"duplicate_entry_{entry.entry_id}") is not None

    await hass.config_entries.async_remove(other.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.unique_id == "solarfocus.local:502"
    assert _issue(hass, f"duplicate_entry_{entry.entry_id}") is None


async def test_removing_an_entry_takes_its_issues_with_it(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """An issue outlives the entry it names, which the registry does not notice.

    What is left behind is a warning about a heating system that is no longer
    configured, naming an entry the user cannot open, until Home Assistant is
    restarted.
    """
    api.update_heating.return_value = False

    entry = await _setup(hass, heating_circuit=1, boiler=1)

    assert _issue(
        hass, f"component_unavailable_{entry.entry_id}_{CONF_HEATING_CIRCUIT}"
    ) is not None

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert not ir.async_get(hass).issues


async def test_switching_a_failing_component_off_clears_its_issue(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """The issue asks the user to switch the component off, so that has to work.

    Doing it saves the options, which reloads the entry into a coordinator that
    has never seen the component fail - and one that never reads it again, so
    nothing about the failure changes for it to notice.
    """
    api.update_boiler.return_value = False

    entry = await _setup(hass, heating_circuit=1, boiler=1)
    issue_id = f"component_unavailable_{entry.entry_id}_{CONF_BOILER}"

    assert _issue(hass, issue_id) is not None

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_BOILER: 0}
    )
    await hass.async_block_till_done()

    assert _issue(hass, issue_id) is None


async def test_a_component_that_answers_nothing_is_reported(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """A register range the firmware does not answer fails on every poll.

    The entities of that component are unavailable while it lasts, and nothing
    in the entry says why: the log line that does is written once.
    """
    api.update_heating.return_value = False

    entry = await _setup(hass, heating_circuit=1, boiler=1)

    issue = _issue(
        hass, f"component_unavailable_{entry.entry_id}_{CONF_HEATING_CIRCUIT}"
    )

    assert issue is not None
    assert issue.translation_placeholders["component"] == "Heating circuit 1"
    assert issue.translation_placeholders["address"] == "solarfocus.local:502"
    # The component that reads fine has nothing raised against it
    assert _issue(hass, f"component_unavailable_{entry.entry_id}_{CONF_BOILER}") is None


async def test_the_issue_names_the_component_the_way_the_device_page_does(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """The option is what the coordinator calls a component, not what a user does.

    `fresh_water_module` is what the entry stores it under; `Fresh water module`
    is what the device page has said since there is a device per component. An
    issue naming the option asks the user to recognise their heating system in
    a configuration key.

    Every instance is named, because every instance is behind the issue: the
    library reads both fresh water modules in one call, so one that answers
    nothing is both of them as far as anything here can tell.
    """
    api.update_fresh_water_modules.return_value = False

    entry = await _setup(hass, heating_circuit=1, fresh_water_module=2)

    issue = _issue(
        hass, f"component_unavailable_{entry.entry_id}_{CONF_FRESH_WATER_MODULE}"
    )

    assert issue is not None
    assert issue.translation_placeholders["component"] == (
        "Fresh water module 1, Fresh water module 2"
    )


async def test_the_issue_names_the_component_in_the_language_of_the_system(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """The device name is translated, so the issue that borrows it is too.

    Which is the other half of what the option leaks: `heating_circuit` is an
    English configuration key in the middle of a German sentence, and the
    device page next to it says `Heizkreis 1`.
    """
    await hass.config.async_update(language="de")

    api.update_heating.return_value = False

    entry = await _setup(hass, heating_circuit=1, boiler=1)

    issue = _issue(
        hass, f"component_unavailable_{entry.entry_id}_{CONF_HEATING_CIRCUIT}"
    )

    assert issue is not None
    assert issue.translation_placeholders["component"] == "Heizkreis 1"


async def test_the_issue_calls_the_component_what_the_user_renamed_it_to(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """A renamed device is the name the user knows that component by.

    Nothing else they read says `Boiler 1` any more, so an issue that does is
    about a component they cannot place.
    """
    api.update_boiler.return_value = False

    entry = await _setup(hass, heating_circuit=1, boiler=1)
    registry = dr.async_get(hass)
    device = registry.async_get_device({(DOMAIN, f"{entry.entry_id}_bo1")})

    assert device is not None
    registry.async_update_device(device.id, name_by_user="Dusche")
    await entry.runtime_data.async_refresh()

    issue = _issue(hass, f"component_unavailable_{entry.entry_id}_{CONF_BOILER}")

    assert issue is not None
    assert issue.translation_placeholders["component"] == "Dusche"


async def test_the_issue_links_the_device_pages_of_the_component(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """The issue is about a device and there is no device field to say so.

    A repair issue takes placeholders and nothing that binds it to a device, so
    the link is markdown in the description - one per instance, because the
    issue covers all of them. What it has to point at is a device that is in
    the registry: a link to a page that does not exist is worse than no link.
    """
    api.update_buffer.return_value = False

    entry = await _setup(hass, heating_circuit=1, buffer=2)
    registry = dr.async_get(hass)

    issue = _issue(hass, f"component_unavailable_{entry.entry_id}_{CONF_BUFFER}")

    assert issue is not None

    devices = [
        registry.async_get_device({(DOMAIN, f"{entry.entry_id}_bu{index}")})
        for index in (1, 2)
    ]

    assert all(device is not None for device in devices)
    assert issue.translation_placeholders["devices"] == ", ".join(
        f"[Buffer {index}](/config/devices/device/{device.id})"
        for index, device in enumerate(devices, start=1)
    )


async def test_an_issue_raised_before_the_devices_exist_is_named_once_they_do(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """The first refresh of a new entry is the one that has no devices to name.

    Setting the entry up reads every component once, and that is what raises
    the issue - before the platforms are forwarded, so before the entities
    that register the devices exist. Without a second look the user would be
    left with the option name and no link until the next poll.
    """
    api.update_heating.return_value = False

    entry = await _setup(hass, heating_circuit=1, boiler=1)

    issue = _issue(
        hass, f"component_unavailable_{entry.entry_id}_{CONF_HEATING_CIRCUIT}"
    )
    device = dr.async_get(hass).async_get_device({(DOMAIN, f"{entry.entry_id}_hc1")})

    assert issue is not None
    assert device is not None
    # No refresh has run since the one setting the entry up
    assert issue.translation_placeholders["devices"] == (
        f"[Heating circuit 1](/config/devices/device/{device.id})"
    )


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


async def test_an_outage_takes_the_component_issues_down_with_it(
    hass: HomeAssistant, enable_custom_integrations, mock_api, api
) -> None:
    """The issue says every other component reads fine, so it has to go.

    While nothing answers at all the entities are unavailable and Home
    Assistant is retrying, which is not a component the user should be asked
    to check their configuration for. It comes back with the system.
    """
    api.update_boiler.return_value = False

    entry = await _setup(hass, heating_circuit=1, boiler=1)
    issue_id = f"component_unavailable_{entry.entry_id}_{CONF_BOILER}"

    assert _issue(hass, issue_id) is not None

    api.update_heating.return_value = False
    await entry.runtime_data.async_refresh()

    assert _issue(hass, issue_id) is None

    api.update_heating.return_value = True
    await entry.runtime_data.async_refresh()

    assert _issue(hass, issue_id) is not None


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
