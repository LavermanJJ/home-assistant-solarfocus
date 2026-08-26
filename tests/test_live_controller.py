"""Set the integration up against a real eco manager-touch.

Skipped unless `SOLARFOCUS_HOST` names one, so CI and everyone without hardware
go straight past it:

    SOLARFOCUS_HOST=10.0.0.5 uv run pytest tests/test_live_controller.py -s

Only the vampair has ever been available to this project, and #217 is what
happens when the other four systems are reasoned from a specification alone.
`tests/test_recorded_controllers.py` is one answer to that - the register dumps
their owners contributed. This is the other: the one system that *can* be held
against real hardware, held against it, through the whole chain rather than at
the library's edge.

**Reads only.** Nothing here writes to the heating system, and nothing here
should: a write can damage a heating system or the building it heats.
"""

import os

from aiosolarfocus import Detection, detect
import pytest
import pytest_socket

from custom_components.solarfocus.diagnostics import async_get_config_entry_diagnostics
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import build_config_entry

HOST = os.environ.get("SOLARFOCUS_HOST")

pytestmark = pytest.mark.skipif(
    not HOST, reason="set SOLARFOCUS_HOST to a real controller to run this"
)


@pytest.fixture(name="reachable")
def reachable_fixture(socket_enabled):
    """Let this one test out of the sandbox the rest of the suite runs in.

    Home Assistant's plugin re-pins the allowed hosts to localhost before every
    test, which is what keeps the rest of this suite honest. A fixture runs
    after that hook, so this is the one place the real controller is reachable.
    """
    pytest_socket.socket_allow_hosts([HOST, "127.0.0.1"], allow_unix_socket=True)


@pytest.fixture(name="detected")
async def detected_fixture(reachable) -> Detection:
    """Ask the controller what it is, rather than being told."""
    found = await detect(HOST)
    print(f"\n{HOST}: {found.system.value} on {found.api_version.label}")

    return found


def _entry(detected: Detection, **overrides):
    """Return the entry this controller describes for itself."""
    counts = detected.counts
    options = {
        "heating_circuit": counts.heating_circuits,
        "buffer": counts.buffers,
        "boiler": counts.boilers,
        "fresh_water_module": counts.fresh_water_modules,
        "circulation": counts.circulations,
        "differential_module": counts.differential_modules,
        "solar": counts.solar,
        "heatpump": detected.has_heat_pump,
        "biomassboiler": detected.has_biomass_boiler,
        "photovoltaic": detected.has_photovoltaic,
        **overrides,
    }

    return build_config_entry(
        detected.system,
        host=HOST,
        api_version=detected.api_version.label,
        **options,
    )


async def test_the_entry_sets_up_and_every_entity_reads(
    hass: HomeAssistant,
    enable_custom_integrations,
    reachable,
    detected: Detection,
) -> None:
    """The whole chain against real registers: setup, poll, entities, values.

    An entity that is `unavailable` here is one this integration built for a
    register the controller does not answer - which is the failure the recorded
    dumps cannot catch, because they only contain what a controller *did*
    answer.
    """
    entry = _entry(detected)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert not entry.runtime_data.failed_components, (
        f"answered nothing: {sorted(entry.runtime_data.failed_components)}"
    )

    states = sorted(
        (hass.states.get(entity_id) for entity_id in hass.states.async_entity_ids()),
        key=lambda state: state.entity_id,
    )
    assert states

    print(f"\n{len(states)} entities\n")
    for state in states:
        unit = state.attributes.get("unit_of_measurement", "")
        print(f"  {state.entity_id:62} {state.state} {unit}")

    unavailable = [state.entity_id for state in states if state.state == STATE_UNAVAILABLE]
    assert not unavailable, f"built but unreadable: {unavailable}"


async def test_every_entity_it_registers_is_one_it_can_read(
    hass: HomeAssistant,
    enable_custom_integrations,
    reachable,
    detected: Detection,
) -> None:
    """An entity in the registry with no state is one nothing will ever fill.

    Disabled by default is a decision; enabled and stateless is a bug, and it
    is invisible on a dashboard because the entity simply is not there.
    """
    entry = _entry(detected)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entries = sorted(
        er.async_entries_for_config_entry(registry, entry.entry_id),
        key=lambda registered: registered.entity_id,
    )
    disabled = [one.entity_id for one in entries if one.disabled_by is not None]

    print(f"\n{len(entries)} registered, {len(disabled)} disabled by default")
    for entity_id in disabled:
        print(f"  disabled  {entity_id}")

    live = set(hass.states.async_entity_ids())
    stateless = [
        one.entity_id
        for one in entries
        if one.disabled_by is None and one.entity_id not in live
    ]

    assert not stateless, f"registered, enabled and never filled: {stateless}"


async def test_the_diagnostics_download_is_what_a_report_needs(
    hass: HomeAssistant,
    enable_custom_integrations,
    reachable,
    detected: Detection,
) -> None:
    """Every register the controller answered, as an issue report carries it."""
    entry = _entry(detected)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["data"][CONF_HOST] == "**REDACTED**"
    assert HOST not in str(diagnostics), "the address of the controller leaked"

    for name, readings in diagnostics["components"].items():
        print(f"\n{name}")
        for register, reading in readings.items():
            unit = reading["unit"] or ""
            address = reading["address"] or ""
            print(
                f"  {register:38} {address:>6}  "
                f"raw={str(reading['raw']):>10}  {reading['value']} {unit}"
            )
