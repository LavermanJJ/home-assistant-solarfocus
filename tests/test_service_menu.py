"""Test the two codes the service menu of the controller asks for.

They are the only values this integration reports without reading a register:
the service code is arithmetic on the date, the installer code multiplies the
cross sum of the number the display shows by the day of the week. Both belong
to the controller, both change at midnight rather than with a poll, and the
number behind the second one is shared between the entity that takes it and
the one that uses it.
"""

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

from custom_components.solarfocus.const import CONF_BOILER, CONF_HEATPUMP, DOMAIN
from custom_components.solarfocus.number import (
    DISPLAYED_NUMBER_TYPE,
    SolarfocusDisplayedNumberEntity,
)
from custom_components.solarfocus.sensor import (
    INSTALLER_CODE_SENSOR_TYPE,
    SERVICE_CODE_SENSOR_TYPE,
    SolarfocusInstallerCodeSensor,
    SolarfocusServiceCodeSensor,
)
from custom_components.solarfocus.service_menu import (
    DisplayedNumber,
    installer_code,
    service_code,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import build_config_entry, build_coordinator

SERVICE_CODE = "sensor.eco_manager_touch_service_code"
INSTALLER_CODE = "sensor.eco_manager_touch_installer_code"
INSTALLER_INPUT = "number.eco_manager_touch_installer_code_input"


def _at(date: str):
    """Return noon of that date, which is when nothing is about to turn over."""
    return dt_util.parse_datetime(f"{date} 12:00:00")


def _enable_on_the_controller(entity_registry, entry) -> None:
    """Switch the two entities of the installer menu on, as a user would.

    Both are created disabled, so a test that wants their states has to be a
    user who enabled them - which is a registry entry that says so, written
    before the entry is set up.
    """
    for domain, key, object_id in (
        ("number", "installer_code_input", "eco manager touch installer code input"),
        ("sensor", "installer_code", "eco manager touch installer code"),
    ):
        entity_registry.async_get_or_create(
            domain,
            DOMAIN,
            f"{entry.entry_id}_{key}",
            suggested_object_id=object_id,
            disabled_by=None,
        )


def _entity(entity_class, description, entry=None):
    """Return one entity of the controller, on a mocked coordinator."""
    entry = entry if entry is not None else build_config_entry()
    return entity_class(build_coordinator(entry), description)


# --- the arithmetic ---------------------------------------------------------


@pytest.mark.parametrize(
    ("date", "expected"),
    [
        # Wednesday: the fourth day of a week that starts on Sunday
        ("2026-08-19", 19 * 5 + 8 * 4),
        # Saturday, the last one
        ("2026-08-22", 22 * 8 + 8 * 7),
        # Sunday, the first - not the last, which is what the mapping is for
        ("2026-08-23", 23 * 2 + 8 * 1),
        ("2026-08-24", 24 * 3 + 8 * 2),
        ("2026-01-01", 1 * 6 + 1 * 5),
    ],
)
def test_the_service_code_is_the_date_weighted_by_the_weekday(
    date: str, expected: int
) -> None:
    """Day and month, each weighted with the day of the week."""
    assert service_code(_at(date)) == expected


@pytest.mark.parametrize(
    ("date", "factor"),
    [
        ("2026-08-19", 4),
        ("2026-08-22", 7),
        ("2026-08-23", 1),
        ("2026-08-24", 2),
    ],
)
def test_the_installer_code_multiplies_the_cross_sum_of_the_displayed_number(
    date: str, factor: int
) -> None:
    """The cross sum of the number on the display, times the day of the week."""
    # cross sum of 1234 is 1 + 2 + 3 + 4 = 10
    assert installer_code(1234, _at(date)) == 10 * factor


def test_sunday_ends_the_week_for_python_and_starts_it_here() -> None:
    """The mapping is the whole difference between the two counts.

    Reading Sunday as the seventh day of the week rather than the first is the
    one way these calculations go wrong without looking wrong, and it is wrong
    on one day in seven.
    """
    assert service_code(_at("2026-08-23")) < service_code(_at("2026-08-22"))
    assert installer_code(10, _at("2026-08-23")) == 1
    assert installer_code(10, _at("2026-08-22")) == 7


# --- the number the display shows -------------------------------------------


def test_the_number_is_shared_with_whoever_reports_the_code(
    freezer: FrozenDateTimeFactory,
) -> None:
    """Setting it on the number entity is what the sensor reads."""
    freezer.move_to("2026-08-19 12:00:00+00:00")
    coordinator = build_coordinator(build_config_entry())
    number = SolarfocusDisplayedNumberEntity(coordinator, DISPLAYED_NUMBER_TYPE)
    sensor = SolarfocusInstallerCodeSensor(coordinator, INSTALLER_CODE_SENSOR_TYPE)

    coordinator.displayed_number.set(20)

    assert number.native_value == 20
    # cross sum of 20 is 2 + 0 = 2
    assert sensor.native_value == 2 * 4


def test_a_change_of_the_number_is_reported_to_its_subscribers() -> None:
    """The sensor is written on every change, it does not wait for a poll."""
    displayed = DisplayedNumber()
    seen = []
    unsubscribe = displayed.subscribe(lambda: seen.append(displayed.value))

    displayed.set(12)
    displayed.set(13)
    unsubscribe()
    displayed.set(14)

    assert seen == [12, 13]


def test_the_installer_code_is_unknown_until_the_number_is_entered() -> None:
    """Nothing has been typed in, so there is no code - and 0 is not one."""
    assert _entity(
        SolarfocusInstallerCodeSensor, INSTALLER_CODE_SENSOR_TYPE
    ).native_value is None


async def test_the_number_writes_nothing_to_the_heating_system(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The display is asking for the number, not reporting one."""
    freezer.move_to("2026-08-19 12:00:00+00:00")
    coordinator = build_coordinator(build_config_entry())
    number = SolarfocusDisplayedNumberEntity(coordinator, DISPLAYED_NUMBER_TYPE)
    number.async_write_ha_state = lambda: None
    sensor = SolarfocusInstallerCodeSensor(coordinator, INSTALLER_CODE_SENSOR_TYPE)

    await number.async_set_native_value(47)

    # Nothing of the library was touched - no register was read, committed or
    # written on the way through
    assert not coordinator.api.method_calls
    assert number.native_value == 47
    # cross sum of 47 is 4 + 7 = 11
    assert sensor.native_value == 11 * 4


async def test_the_number_survives_a_restart(
    hass: HomeAssistant, enable_custom_integrations, mock_api, entity_registry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The display keeps showing the number, so Home Assistant keeps it too.

    A restart in the middle of the installer menu is not a reason to type the
    number in again, and restoring it is what lets the sensor report a code
    before anything is entered at all.
    """
    freezer.move_to("2026-08-19 12:00:00+02:00")
    entry = build_config_entry()
    entry.add_to_hass(hass)
    _enable_on_the_controller(entity_registry, entry)

    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(INSTALLER_INPUT, "47"),
                {
                    "native_max_value": 9999,
                    "native_min_value": 0,
                    "native_step": 1,
                    "native_unit_of_measurement": None,
                    "native_value": 47,
                },
            ),
        ),
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(INSTALLER_INPUT).state == "47"
    # cross sum of 47 is 4 + 7 = 11
    assert hass.states.get(INSTALLER_CODE).state == str(11 * 4)


async def test_the_number_takes_the_four_digits_the_display_shows(
    hass: HomeAssistant, enable_custom_integrations, mock_api, entity_registry,
) -> None:
    """The installer menu shows up to four digits, so 9999 is the highest there is."""
    entry = build_config_entry()
    entry.add_to_hass(hass)
    _enable_on_the_controller(entity_registry, entry)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "number", "set_value", {"entity_id": INSTALLER_INPUT, "value": 9999},
        blocking=True,
    )
    assert float(hass.states.get(INSTALLER_INPUT).state) == 9999

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "number", "set_value", {"entity_id": INSTALLER_INPUT, "value": 10000},
            blocking=True,
        )


# --- the entities on the controller -----------------------------------------


async def test_the_service_code_sensor_reports_the_code_of_today(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The state is the code, computed when it is asked for."""
    freezer.move_to("2026-08-19 12:00:00+00:00")

    assert _entity(
        SolarfocusServiceCodeSensor, SERVICE_CODE_SENSOR_TYPE
    ).native_value == 127


@pytest.mark.parametrize(
    ("entity_class", "description"),
    [
        (SolarfocusServiceCodeSensor, SERVICE_CODE_SENSOR_TYPE),
        (SolarfocusInstallerCodeSensor, INSTALLER_CODE_SENSOR_TYPE),
        (SolarfocusDisplayedNumberEntity, DISPLAYED_NUMBER_TYPE),
    ],
)
def test_they_sit_on_the_controller(entity_class, description) -> None:
    """These are properties of the controller, not of any component."""
    entry = build_config_entry()

    assert _entity(entity_class, description, entry).device_info["identifiers"] == {
        (DOMAIN, entry.entry_id)
    }


@pytest.mark.parametrize(
    ("entity_class", "description"),
    [
        (SolarfocusServiceCodeSensor, SERVICE_CODE_SENSOR_TYPE),
        (SolarfocusInstallerCodeSensor, INSTALLER_CODE_SENSOR_TYPE),
        (SolarfocusDisplayedNumberEntity, DISPLAYED_NUMBER_TYPE),
    ],
)
def test_they_stay_available_when_the_heating_cannot_be_read(
    entity_class, description
) -> None:
    """A heating system that does not answer is when the service menu is wanted."""
    entity = _entity(entity_class, description)
    entity.coordinator.last_update_success = False

    assert entity.available


@pytest.mark.parametrize(
    ("entity_class", "description"),
    [
        (SolarfocusServiceCodeSensor, SERVICE_CODE_SENSOR_TYPE),
        (SolarfocusInstallerCodeSensor, INSTALLER_CODE_SENSOR_TYPE),
        (SolarfocusDisplayedNumberEntity, DISPLAYED_NUMBER_TYPE),
    ],
)
def test_they_stay_available_when_a_component_cannot_be_read(
    entity_class, description
) -> None:
    """A failing component greys out its own entities and nothing else.

    These are not on a component at all - they are arithmetic on the controller
    - so the set of components that failed says nothing about them.
    """
    entity = _entity(entity_class, description)
    entity.coordinator.failed_components = {CONF_HEATPUMP, CONF_BOILER}

    assert entity.available


async def test_the_registry_agrees_where_they_belong(
    hass: HomeAssistant, enable_custom_integrations, mock_api, device_registry,
    entity_registry,
) -> None:
    """The registry is what puts them on the page of the controller.

    The two the installer needs are created disabled, so they are only there to
    be found with the disabled ones included.
    """
    entry = build_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    controller = device_registry.async_get_device({(DOMAIN, entry.entry_id)})
    registered = {
        entity.entity_id: entity
        for entity in er.async_entries_for_device(
            entity_registry, controller.id, include_disabled_entities=True
        )
    }

    assert set(registered) == {SERVICE_CODE, INSTALLER_CODE, INSTALLER_INPUT}
    assert all(entity.device_id == controller.id for entity in registered.values())
    # The two that only report are diagnostic; the one that is typed into is
    # configuration, which is the category Home Assistant has for a control.
    assert registered[SERVICE_CODE].entity_category is er.EntityCategory.DIAGNOSTIC
    assert registered[INSTALLER_CODE].entity_category is er.EntityCategory.DIAGNOSTIC
    assert registered[INSTALLER_INPUT].entity_category is er.EntityCategory.CONFIG
    assert registered[SERVICE_CODE].disabled_by is None
    assert registered[INSTALLER_CODE].disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert registered[INSTALLER_INPUT].disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_the_codes_change_at_midnight(
    hass: HomeAssistant, enable_custom_integrations, mock_api, entity_registry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A code a day old opens nothing, and nothing polls these entities."""
    await hass.config.async_set_time_zone("Europe/Vienna")
    freezer.move_to("2026-08-19 23:59:00+02:00")

    entry = build_config_entry()
    entry.add_to_hass(hass)
    _enable_on_the_controller(entity_registry, entry)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": INSTALLER_INPUT, "value": 47},
        blocking=True,
    )

    # cross sum of 47 is 4 + 7 = 11
    assert hass.states.get(SERVICE_CODE).state == "127"
    assert hass.states.get(INSTALLER_CODE).state == str(11 * 4)

    freezer.move_to("2026-08-20 00:00:01+02:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(SERVICE_CODE).state == "160"
    # Thursday, the fifth day of a week that starts on Sunday
    assert hass.states.get(INSTALLER_CODE).state == str(11 * 5)
