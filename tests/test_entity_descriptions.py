"""Verify entity descriptions against the values the library actually carries.

Every entity description names an `item` that is read off a component at
runtime. The integration used to decide for itself which systems and firmware
versions had it, carrying a `min_required_version` and an `unsupported_systems`
list on every description - a second copy of the register document, which
drifted from it: see #163, where the buffer `external_*` sensors were declared
for all systems although a Therminator buffer has none of them, and #217, where
four registers the document gives to one system were read on all of them.

The library owns that now, so `supports` decides what is built. What is left to
check here is the half it cannot: that every description names something the
library has heard of, that no two descriptions of one key survive together, and
that the register-document facts these regressions were about still hold.
"""

from aiosolarfocus import ApiVersion, ComponentId, Systems
import pytest

from custom_components.solarfocus import (
    binary_sensor,
    button,
    number,
    select,
    sensor,
    switch,
)
from custom_components.solarfocus.const import (
    BIOMASS_BOILER_COMPONENT,
    BOILER_COMPONENT,
    BUFFER_COMPONENT,
    CIRCULATION_COMPONENT,
    DIFFERENTIAL_MODULE_COMPONENT,
    FRESH_WATER_MODULE_COMPONENT,
    HEAT_PUMP_COMPONENT,
    HEAT_PUMP_COMPONENT_PREFIX,
    HEATING_CIRCUIT_COMPONENT,
    PHOTOVOLTAIC_COMPONENT,
    SOLAR_COMPONENT,
)
from custom_components.solarfocus.entity import create_description

from .conftest import build_client, build_config_entry

# Entity description list -> the component it is read from.
# Mirrors the wiring in each platform's async_setup_entry.
DESCRIPTION_LISTS = [
    (sensor.HEATING_CIRCUIT_SENSOR_TYPES, HEATING_CIRCUIT_COMPONENT),
    (sensor.BUFFER_SENSOR_TYPES, BUFFER_COMPONENT),
    (sensor.BOILER_SENSOR_TYPES, BOILER_COMPONENT),
    (sensor.HEATPUMP_SENSOR_TYPES, HEAT_PUMP_COMPONENT),
    (sensor.PHOTOVOLTAIC_SENSOR_TYPES, PHOTOVOLTAIC_COMPONENT),
    (sensor.BIOMASS_BOILER_SENSOR_TYPES, BIOMASS_BOILER_COMPONENT),
    (sensor.SOLAR_SENSOR_TYPES, SOLAR_COMPONENT),
    (sensor.FRESH_WATER_MODULE_SENSOR_TYPES, FRESH_WATER_MODULE_COMPONENT),
    (sensor.CIRCULATION_SENSOR_TYPES, CIRCULATION_COMPONENT),
    (sensor.DIFFERENTIAL_MODULE_SENSOR_TYPES, DIFFERENTIAL_MODULE_COMPONENT),
    (number.HEATING_CIRCUIT_NUMBER_TYPES, HEATING_CIRCUIT_COMPONENT),
    (number.BOILER_NUMBER_TYPES, BOILER_COMPONENT),
    (select.HEATPUMP_SELECT_TYPES, HEAT_PUMP_COMPONENT),
    (select.HEATING_CIRCUIT_SELECT_TYPES, HEATING_CIRCUIT_COMPONENT),
    (select.BOILER_SELECT_TYPES, BOILER_COMPONENT),
    (switch.HEATPUMP_SWITCH_TYPES, HEAT_PUMP_COMPONENT),
    (button.BOILER_BUTTON_TYPES, BOILER_COMPONENT),
    (binary_sensor.HEATING_CIRCUIT_BINARY_SENSOR_TYPES, HEATING_CIRCUIT_COMPONENT),
    (binary_sensor.BUFFER_BINARY_SENSOR_TYPES, BUFFER_COMPONENT),
    (binary_sensor.HEATPUMP_BINARY_SENSOR_TYPES, HEAT_PUMP_COMPONENT),
    (binary_sensor.BIOMASS_BOILER_BINARY_SENSOR_TYPES, BIOMASS_BOILER_COMPONENT),
    (binary_sensor.PHOTOVOLTAIC_BINARY_SENSOR_TYPES, PHOTOVOLTAIC_COMPONENT),
    (binary_sensor.FRESH_WATER_MODULE_BINARY_SENSOR_TYPES, FRESH_WATER_MODULE_COMPONENT),
    (binary_sensor.CIRCULATION_BINARY_SENSOR_TYPES, CIRCULATION_COMPONENT),
    (
        binary_sensor.DIFFERENTIAL_MODULE_BINARY_SENSOR_TYPES,
        DIFFERENTIAL_MODULE_COMPONENT,
    ),
]

# water_heater and climate are composite entities: their description key is only a
# label ("domestic_hot_water", "thermostat") and the registers they touch are named
# inline in the property implementations. Those names are listed here so they get the
# same coverage as the key-based platforms.
COMPOSITE_ITEMS = [
    (
        BOILER_COMPONENT,
        ["temperature", "target_temperature", "mode", "holding_mode"],
    ),
    (
        HEATING_CIRCUIT_COMPONENT,
        ["cooling", "target_supply_temperature", "supply_temperature", "state", "mode"],
    ),
]

# The newest firmware the library knows, so that nothing is hidden behind a
# version gate while checking what exists at all.
LATEST_API_VERSION = list(ApiVersion)[-1]

# The heat source each system has, since the library refuses a configuration
# with the other one.
BIOMASS_SYSTEMS = [system for system in Systems if system is not Systems.VAMPAIR]


# The component -> the entry option that configures one of it. A component the
# entry does not ask for is not built, and one the firmware predates is
# refused, so an entry is built asking for exactly the component under test.
OPTION_OF = {
    HEATING_CIRCUIT_COMPONENT: ("heating_circuit", 1),
    BUFFER_COMPONENT: ("buffer", 1),
    BOILER_COMPONENT: ("boiler", 1),
    SOLAR_COMPONENT: ("solar", 1),
    FRESH_WATER_MODULE_COMPONENT: ("fresh_water_module", 1),
    CIRCULATION_COMPONENT: ("circulation", 1),
    DIFFERENTIAL_MODULE_COMPONENT: ("differential_module", 1),
    PHOTOVOLTAIC_COMPONENT: ("photovoltaic", True),
    HEAT_PUMP_COMPONENT: ("heatpump", True),
    BIOMASS_BOILER_COMPONENT: ("biomassboiler", True),
}


def _component(system: Systems, component: str, api_version: ApiVersion | None = None):
    """Return the library's component instance for a system and firmware."""
    option, value = OPTION_OF[component]
    entry = build_config_entry(
        system,
        api_version=(api_version or LATEST_API_VERSION).label,
        **{option: value},
    )

    return build_client(entry).of(ComponentId(component))[0]


def _values(system: Systems, component: str) -> set[str]:
    """Every value the library offers on that component for that system."""
    return set(_component(system, component).available_values())


def test_every_description_names_a_value_the_library_carries() -> None:
    """A key the library has never heard of would simply never become an entity.

    Which is a quiet way to lose a sensor: nothing raises, nothing is logged,
    and the entity is just not there. So each key has to be a value the library
    offers on at least one system - the systems it is *not* offered on are the
    library gating it, which is the point.
    """
    orphaned: list[str] = []

    for descriptions, component in DESCRIPTION_LISTS:
        everywhere: set[str] = set()
        for system in Systems:
            if component == HEAT_PUMP_COMPONENT and system is not Systems.VAMPAIR:
                continue
            if component == BIOMASS_BOILER_COMPONENT and system is Systems.VAMPAIR:
                continue
            everywhere |= _values(system, component)

        orphaned += [
            f"{component}.{description.item or description.key}"
            for description in descriptions
            if (description.item or description.key) not in everywhere
        ]

    assert not orphaned, (
        f"{sorted(orphaned)} are described but named by no value of that "
        f"component on any system."
    )


@pytest.mark.parametrize(("component", "items"), COMPOSITE_ITEMS)
def test_composite_entity_items_exist_on_every_system(
    component: str, items: list[str]
) -> None:
    """Registers read inline by water_heater/climate must exist too.

    These two are passed through the gating filter rather than asked about -
    their key is a label - so nothing else would notice if one of the registers
    they name inline went away.
    """
    for system in Systems:
        available = _values(system, component)
        missing = [item for item in items if item not in available]

        assert not missing, f"{system.name} has no {missing} on its {component}"


@pytest.mark.parametrize("system", list(Systems), ids=lambda s: s.name)
def test_no_key_is_described_twice_for_one_system(system: Systems) -> None:
    """One system may only ever reach one description per key.

    A description list is allowed to carry the same key more than once - the
    biomass boiler door was described twice while register 2405 was believed to
    read the other way round on a therminator than on an EcoTop. What the
    duplicates must not do is survive the filter together: the key is half of
    the `unique_id`, so Home Assistant would create the first entity and drop
    the second, with nothing to say which of the two it kept.
    """
    for descriptions, component in DESCRIPTION_LISTS:
        if component == HEAT_PUMP_COMPONENT and system is not Systems.VAMPAIR:
            continue
        if component == BIOMASS_BOILER_COMPONENT and system is Systems.VAMPAIR:
            continue

        available = _values(system, component)
        reached = [
            description.key
            for description in descriptions
            if (description.item or description.key) in available
            and system not in (description.unverified_systems or [])
        ]
        duplicates = {key for key in reached if reached.count(key) > 1}

        assert not duplicates, (
            f"{component} describes {sorted(duplicates)} more than once for "
            f"system {system.name}; only one of them can become an entity."
        )


def test_buffer_external_sensors_are_not_offered_to_therminator_or_ecotop() -> None:
    """Regression test for #163.

    A Therminator and an EcoTop buffer never read the external X44/X36/X35
    holding registers. Neither the register document nor the predecessor
    explains why, and no hardware was available to check - two sources agreeing
    was enough to carry the behaviour over rather than "fix" it against
    hardware nobody has.
    """
    external = [
        description
        for description in sensor.BUFFER_SENSOR_TYPES
        if description.key.startswith("external_")
    ]
    assert external, "expected external_* buffer sensors to exist"

    for system in (Systems.THERMINATOR, Systems.ECOTOP):
        available = _values(system, BUFFER_COMPONENT)
        for description in external:
            assert description.key not in available


def test_buffer_x35_reaches_the_therminator_alone() -> None:
    """Regression test for #217, and a change of behaviour in version 7.

    Buffer 1902 is "Puffertemperatur X35" and the register document gives it to
    the therminator. The integration offered it to the EcoTop as well, which is
    one of the four registers #217 was about: a read spanning an address the
    firmware does not map comes back compacted, not padded. An EcoTop loses
    this sensor in version 7.
    """
    assert any(
        description.key == "x35_temperature"
        for description in sensor.BUFFER_SENSOR_TYPES
    )

    for system in Systems:
        available = _values(system, BUFFER_COMPONENT)
        assert ("x35_temperature" in available) is (system is Systems.THERMINATOR)


# Register -> the one system the register document grants it to. The document
# names each of these after a single system: "Kesselbetriebsart therminator",
# "Speichertemperatur Oben octoplus", "Stueckholz therminator". Register 2410 is
# the octoplus buffer bottom, and on the other Sigmatek boilers the return flow
# temperature - a different measurement that wants its own entity, not this one.
SINGLE_SYSTEM_BIOMASS_REGISTERS = [
    ("boiler_operating_mode", Systems.THERMINATOR),
    ("log_wood", Systems.THERMINATOR),
    ("octoplus_buffer_temperature_top", Systems.OCTOPLUS),
    ("octoplus_buffer_temperature_bottom", Systems.OCTOPLUS),
]


@pytest.mark.parametrize(("key", "supported"), SINGLE_SYSTEM_BIOMASS_REGISTERS)
def test_single_system_biomass_registers_reach_only_that_system(
    key: str, supported: Systems
) -> None:
    """Regression test for #217.

    These four were excluded from the vampair and the EcoTop and given to
    everything else, which handed a pellet boiler a log wood register and a
    therminator two buffer temperatures its controller does not have.
    """
    assert any(
        description.key == key for description in sensor.BIOMASS_BOILER_SENSOR_TYPES
    )

    for system in BIOMASS_SYSTEMS:
        available = _values(system, BIOMASS_BOILER_COMPONENT)
        assert (key in available) is (system is supported), (
            f"{key} is documented for {supported.name} only, but "
            f"{'reaches' if key in available else 'does not reach'} "
            f"{system.name}."
        )


def test_log_wood_arrives_with_22_090() -> None:
    """A change of behaviour in version 7.

    2412 arrived in 22.090. The integration offered it to a therminator on any
    firmware, so a 21.140 controller was read at an address it does not map -
    and a read that spans an unmapped address is compacted rather than padded,
    which shifts every value after it into the wrong name.
    """
    older = _component(
        Systems.THERMINATOR, BIOMASS_BOILER_COMPONENT, ApiVersion.V_21_140
    )
    newer = _component(
        Systems.THERMINATOR, BIOMASS_BOILER_COMPONENT, ApiVersion.V_22_090
    )

    assert not older.supports("log_wood")
    assert newer.supports("log_wood")


# What register 2405 was measured to hold, and on which boiler. A door contact
# is worth pinning down: get the polarity backwards and the entity still works,
# it just says the opposite of the truth, which is how #91 and #101 stayed open
# for two years - this integration had the EcoTop backwards from #79/#80 until
# #91 measured a real one directly: register 2405 on QModMaster, the
# controller's own display, and the library all agreed on 0 closed / 1 open,
# the same as the specification and every other system below.
MEASURED_DOOR_POLARITIES = [
    (Systems.THERMINATOR, "1"),
    # 25.100, measured directly for #91 after #79/#80 had this backwards.
    (Systems.ECOTOP, "1"),
    # 15 kW on v25.110, read at the door for #217: 1 open, 0 closed.
    (Systems.PELLETELEGANCE, "1"),
]


@pytest.mark.parametrize(("system", "on_state"), MEASURED_DOOR_POLARITIES)
def test_the_door_contact_reads_the_way_it_was_measured(
    system: Systems, on_state: str
) -> None:
    """Exactly one door description reaches a system, with the measured polarity.

    `CONF_DOOR_CONTACT_INVERTED` is a per-installation escape hatch layered on
    top of this in `binary_sensor.async_setup_entry`, for a door contact wired
    the other way round at its terminal - it does not change what the
    description itself says here.
    """
    available = _values(system, BIOMASS_BOILER_COMPONENT)
    reaching = [
        description
        for description in binary_sensor.BIOMASS_BOILER_BINARY_SENSOR_TYPES
        if description.key == "door_contact"
        and description.key in available
        and system not in (description.unverified_systems or [])
    ]

    assert len(reaching) == 1, (
        f"{system.name} reaches {len(reaching)} door descriptions; they share a "
        f"key, so only one can ever become an entity."
    )
    assert reaching[0].on_state == on_state


def test_the_octoplus_has_no_door_contact() -> None:
    """Nobody has read 2405 on an octoplus.

    The library maps the register on every biomass boiler and is right to: it
    is there and it answers. What is unmeasured is which way round. The two
    polarities are both attested on real boilers, so picking one for an
    unmeasured system is a coin toss that produces a door sensor which is
    confidently wrong half the time. Better to have no entity until someone
    reads the register with the door open and with it closed.

    This is the only thing `unverified_systems` is for, and it is deliberately
    not `supports`: the question it answers is not whether the controller has
    the register.
    """
    assert "door_contact" in _values(Systems.OCTOPLUS, BIOMASS_BOILER_COMPONENT)

    reaching = [
        description
        for description in binary_sensor.BIOMASS_BOILER_BINARY_SENSOR_TYPES
        if description.key == "door_contact"
        and Systems.OCTOPLUS not in (description.unverified_systems or [])
    ]

    assert not reaching


# The three the library renamed on the way from `pysolarfocus`: a "performance
# overall" that is a seasonal figure reads better as one.
RENAMED = [
    ("performance_overall", "seasonal_performance"),
    ("performance_overall_heating", "seasonal_performance_heating"),
    ("performance_overall_drinking_water", "seasonal_performance_drinking_water"),
]


@pytest.mark.parametrize(("key", "item"), RENAMED)
def test_a_renamed_register_keeps_the_entity_id_it_had(key: str, item: str) -> None:
    """The key is what an entity id, its history and its name are built from.

    So the rename stays inside the library: the description goes on naming the
    entity `performance_overall` and names the register it reads separately.
    An installation upgrading to version 7 keeps `sensor.heat_pump_performance
    _overall`, everything recorded against it, and anything the user set on it.
    """
    description = next(
        description
        for description in sensor.HEATPUMP_SENSOR_TYPES
        if description.key == key
    )

    assert description.item == item
    assert _component(Systems.VAMPAIR, HEAT_PUMP_COMPONENT).supports(item)

    bound = create_description(
        HEAT_PUMP_COMPONENT, HEAT_PUMP_COMPONENT_PREFIX, "", description
    )

    assert bound.key == f"hp_{key}"
    assert bound.translation_key == f"hp_{key}"
    assert bound.object_id_name == key.replace("_", " ")
    assert bound.item == item


def test_only_the_renamed_registers_have_an_item_of_their_own() -> None:
    """`item` differing from `key` is the exception, not a second naming scheme.

    Every other description reads the register its key names, so a stray `item`
    would be an entity id nobody can trace back to what it reports.
    """
    overridden = {
        description.key
        for descriptions, _ in DESCRIPTION_LISTS
        for description in descriptions
        if description.item and description.item != description.key
    }

    assert overridden == {key for key, _ in RENAMED}
