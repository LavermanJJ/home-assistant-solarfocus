"""Set the integration up against four controllers that really exist.

Only the vampair has ever been tested against hardware. The other four systems
are reasoned from the register specification, which is exactly how #217
happened: four registers the document grants to one system were read on all of
them, a Pellet Elegance maps neither 2409 nor 2413, and the read that spanned
them came back compacted - the return flow temperature reported 270.0 °C where
the sensor said 22.1 °C.

`aiosolarfocus` fixed that, but the fix is only as good as the evidence, and the
evidence is these four dumps: real register readings filed on #237 by the owners
of an EcoTop, two Pellet Elegances and a Therminator. Feeding them to a fake
controller and setting an entry up on top is the only coverage those four
systems will ever get without hardware.

Refresh them with `python -m aiosolarfocus dump --host <controller> --json`.
"""

import json
import pathlib

from aiosolarfocus import ApiVersion, Systems
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import build_config_entry, controller_of

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

# The dump, the system it was taken from, and what the entry has to be
# configured with to read it. The Therminator dump is filed with `"system":
# "Ecotop"` in its own metadata - the contributor ran `dump` without correcting
# the system - so the file name is the only record of what the boiler is, and
# the registers were read as an EcoTop's either way. It is listed as what it was
# read as.
RECORDED = [
    ("ecotop.json", Systems.ECOTOP, {"heating_circuit": 2, "buffer": 1, "boiler": 1}),
    (
        "pellet_elegance_21_110.json",
        Systems.PELLETELEGANCE,
        {"heating_circuit": 1, "buffer": 1, "boiler": 1},
    ),
    (
        "pellet_elegance_25_110.json",
        Systems.PELLETELEGANCE,
        {"heating_circuit": 1, "buffer": 1, "boiler": 1},
    ),
    ("therminator.json", Systems.ECOTOP, {"heating_circuit": 1, "buffer": 1, "boiler": 1}),
]


def _dump(name: str) -> dict:
    """Return one recorded controller."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _replay(client, dump: dict) -> None:
    """Put every word the controller answered back where it answered it.

    A dump records a register as one number, so how many words that was is a
    fact about the register rather than about the number: 54186 is one word as
    a heating circuit's setpoint and two as a pellet counter, and guessing from
    the magnitude puts a 32-bit counter's whole value in its high word.
    """
    controller = controller_of(client)

    for key, readings in dump["components"].items():
        component = _component_of(client, key)
        if component is None:
            # The dump records more than this entry is configured for - the
            # EcoTop has two heating circuits and some tests want one.
            continue
        for register, reading in readings.items():
            resolved = component.layout.by_name.get(register)
            if resolved is None or reading["raw"] is None:
                continue

            raw = reading["raw"]
            width = len(resolved.addresses)
            for offset, address in enumerate(resolved.addresses):
                word = (raw >> (16 * (width - 1 - offset))) & 0xFFFF
                controller.set(resolved.kind, address, word)


def _component_of(client, name: str):
    """Return the component a dump names as a string, if this entry has it."""
    key = next((key for key in client.components if str(key) == name), None)

    return None if key is None else client.components[key]


@pytest.mark.parametrize(("name", "system", "options"), RECORDED, ids=lambda v: str(v))
async def test_a_recorded_controller_sets_up_and_reports_its_readings(
    hass: HomeAssistant,
    enable_custom_integrations,
    mock_client,
    name: str,
    system: Systems,
    options: dict,
) -> None:
    """The whole chain, on registers a real controller really answered with."""
    dump = _dump(name)
    entry = build_config_entry(
        system,
        api_version=ApiVersion.parse(dump["meta"]["api_version"]).label,
        biomassboiler=True,
        **options,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    _replay(mock_client.instance, dump)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert not entry.runtime_data.failed_components

    states = [
        hass.states.get(entity_id)
        for entity_id in hass.states.async_entity_ids()
        if entity_id.split(".", 1)[1].startswith(("heating_circuit", "boiler", "buffer", "biomass_boiler"))
    ]

    assert states, "the entry built no entities at all"
    assert not [state for state in states if state.state == STATE_UNAVAILABLE]


@pytest.mark.parametrize(("name", "system", "options"), RECORDED, ids=lambda v: str(v))
async def test_a_recorded_controller_reports_what_the_dump_recorded(
    hass: HomeAssistant,
    enable_custom_integrations,
    mock_client,
    name: str,
    system: Systems,
    options: dict,
) -> None:
    """Every value the dump decoded reaches the entity that reports it.

    This is the assertion #217 would have failed: a Pellet Elegance read its
    return flow temperature as 270.0 °C where the sensor said 22.1, because the
    read spanned an address the firmware does not map. Holding the entity
    against the value the library decoded from the same words is what says the
    register map and the entity agree.
    """
    dump = _dump(name)
    entry = build_config_entry(
        system,
        api_version=ApiVersion.parse(dump["meta"]["api_version"]).label,
        biomassboiler=True,
        **options,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    client = mock_client.instance
    _replay(client, dump)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    mismatched = []
    compared = 0
    for key, readings in dump["components"].items():
        component = _component_of(client, key)
        if component is None:
            continue
        for register, reading in readings.items():
            if reading["value"] is None or not component.supports(register):
                continue

            now = component.value_of(getattr(type(component), register))
            if now == reading["value"]:
                compared += 1
                continue
            # A reading the library has since learned to recognise as a
            # sentinel decodes to None: these dumps were taken with 0.1.0, and
            # they are what taught it. -1% cleaning, -0.1% humidity, -999.9 °C
            # outdoor and a flag register of 0xFFFF are all in here.
            if now is None and component.raw(getattr(type(component), register)) is not None:
                continue
            mismatched.append((key, register, reading["value"], now))

    assert not mismatched, (
        f"{name} decodes differently now than when it was recorded: {mismatched}"
    )
    # The sentinel exemption above must not be the whole of it: if every value
    # were exempt this test would assert nothing at all.
    assert compared >= 20, f"only {compared} readings were actually compared"


@pytest.mark.parametrize(
    ("name", "system", "expected"),
    [
        ("pellet_elegance_21_110.json", Systems.PELLETELEGANCE, 25.7),
        ("pellet_elegance_25_110.json", Systems.PELLETELEGANCE, 21.1),
        ("ecotop.json", Systems.ECOTOP, 30.4),
    ],
)
async def test_the_return_flow_temperature_is_the_one_the_sensor_read(
    hass: HomeAssistant,
    enable_custom_integrations,
    mock_client,
    name: str,
    system: Systems,
    expected: float,
) -> None:
    """Regression test for #217, on the controllers it was reported from.

    Register 2410 is the boiler's return flow temperature on a Pellet Elegance
    and an EcoTop. A Pellet Elegance maps neither 2409 nor 2413, so the read
    that spanned them came back compacted and the sensor reported 270.0 °C
    where the thermometer said 22.1. These are the words those controllers
    really answered with.
    """
    dump = _dump(name)
    entry = build_config_entry(
        system,
        api_version=ApiVersion.parse(dump["meta"]["api_version"]).label,
        biomassboiler=True,
        heating_circuit=1,
        buffer=1,
        boiler=1,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    _replay(mock_client.instance, dump)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.biomass_boiler_return_temperature")

    assert state is not None
    assert state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
    assert float(state.state) == expected


def test_the_recordings_are_all_used() -> None:
    """A dump nobody reads is a file, not a test."""
    assert {name for name, _, _ in RECORDED} == {
        path.name for path in FIXTURES.glob("*.json")
    }
