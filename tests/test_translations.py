"""Validate the translation files.

hassfest validates `strings.json` and `translations/en.json` against the rules for
integrations in Home Assistant core. One of those rules does not fit this
integration: translation keys have to match `[a-z0-9-_]+`, which no negative
number can, while `bo_circulation` and `bo_single_charge` report -1 for "Locked".
Home Assistant resolves that key at runtime and shows the translated state, so the
value is kept and the hassfest plugin is skipped in the workflow.

These tests take over the part of that plugin that does matter, under rules that
fit a custom component: numeric state keys are allowed, sloppy values are not.
"""

import json
import pathlib

from pysolarfocus import ApiVersions, Systems
import pytest

from custom_components.solarfocus import (
    binary_sensor,
    button,
    climate,
    number,
    select,
    sensor,
    switch,
    water_heater,
)
from homeassistant.core import HomeAssistant

from .conftest import build_config_entry, build_coordinator

COMPONENT_DIR = pathlib.Path(sensor.__file__).parent

PLATFORMS = {
    "binary_sensor": binary_sensor,
    "button": button,
    "climate": climate,
    "number": number,
    "select": select,
    "sensor": sensor,
    "switch": switch,
    "water_heater": water_heater,
}

FILENAMES = ["strings.json", "translations/en.json", "translations/de.json"]


def _load(filename: str) -> dict:
    with (COMPONENT_DIR / filename).open(encoding="utf-8") as fh:
        return json.load(fh)


def _strings(value, path=()):
    """Yield every (path, string) of a nested translation structure."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(item, (*path, key))
    elif isinstance(value, str):
        yield ".".join(path), value


def _entity_states(data: dict):
    """Yield every (path, state, text) of the entity state translations."""
    for domain, entities in data.get("entity", {}).items():
        for entity, sections in entities.items():
            for state, text in sections.get("state", {}).items():
                yield f"entity.{domain}.{entity}", state, text


@pytest.mark.parametrize("filename", FILENAMES)
def test_translations_are_valid_json(filename: str) -> None:
    """A broken file makes every entity of the integration untranslated."""
    assert _load(filename)


@pytest.mark.parametrize("filename", FILENAMES)
def test_no_value_has_surrounding_whitespace(filename: str) -> None:
    """Leading or trailing spaces show up in the state of the entity."""
    sloppy = [
        (path, text)
        for path, text in _strings(_load(filename))
        if text != text.strip()
    ]

    assert not sloppy, f"{filename}: {sloppy}"


@pytest.mark.parametrize("filename", FILENAMES)
def test_states_have_no_placeholders(filename: str) -> None:
    """Home Assistant does not substitute placeholders in a state.

    A `{name}` in a state is rendered literally, so the user reads the name of a
    Solarfocus parameter in curly braces instead of a value.
    """
    placeholders = [
        (path, state, text)
        for path, state, text in _entity_states(_load(filename))
        if "{" in text or "}" in text
    ]

    assert not placeholders, f"{filename}: {placeholders}"


@pytest.mark.parametrize("filename", FILENAMES)
def test_sensor_state_keys_are_numbers(filename: str) -> None:
    """The sensor states of this integration are the raw values of the device.

    Negative values are part of that (-1 is "Locked"), which is why hassfest's
    translation key rule cannot be followed, see the module docstring. Other
    domains use the state names of Home Assistant itself and are not numeric.
    """
    not_numeric = [
        (path, state)
        for path, state, _ in _entity_states(_load(filename))
        if path.startswith("entity.sensor.") and not state.lstrip("-").isdigit()
    ]

    assert not not_numeric, f"{filename}: {not_numeric}"


def test_english_translations_match_the_strings_file() -> None:
    """`translations/en.json` is the English copy of `strings.json`."""
    strings = dict(_strings(_load("strings.json").get("entity", {})))
    english = dict(_strings(_load("translations/en.json").get("entity", {})))

    assert english == strings


async def _translation_keys(hass: HomeAssistant) -> dict[str, set[str]]:
    """Return the translation keys of every entity, per domain."""
    keys: dict[str, set[str]] = {}
    for domain, module in PLATFORMS.items():
        created = []
        for system in Systems:
            entry = build_config_entry(
                system,
                api_version=ApiVersions.V_26_020.value,
                heating_circuit=1,
                buffer=1,
                boiler=1,
                fresh_water_module=1,
                solar=1,
                heatpump=True,
                biomassboiler=True,
                photovoltaic=True,
            )
            entry.add_to_hass(hass)
            entry.runtime_data = build_coordinator(entry)

            await module.async_setup_entry(hass, entry, created.extend)

        keys[domain] = {e.entity_description.translation_key for e in created}

    return keys


async def test_every_translated_entity_exists(hass: HomeAssistant) -> None:
    """A key no entity uses translates nothing.

    Home Assistant looks the states up under the translation key of the entity,
    so a key that belongs to no entity leaves that entity showing the raw value
    of the register - which is what `bb_mode` did to the operating mode of the
    biomass boiler, whose key is `bb_boiler_operating_mode`.
    """
    entities = await _translation_keys(hass)

    unused = [
        (domain, key)
        for domain, keys in _load("strings.json")["entity"].items()
        for key in keys
        if key not in entities.get(domain, set())
    ]

    assert not unused


def _comparable(text: str) -> str:
    """Return a state text without the differences that are only spelling."""
    return text.lower().replace("–", "-").replace(" ", "")


@pytest.mark.parametrize("filename", FILENAMES)
def test_the_two_boiler_release_modes_agree(filename: str) -> None:
    """The boiler reports and takes the release mode as the same enumeration.

    Register 502 ("Boiler Freigabeart - Ist", the `bo_mode` sensor) and register
    32002 ("Boiler - Freigabeart", the `bo_holding_mode` select) are documented
    with one list of values: 0 is "Immer Aus", 1 is "Immer Ein". The English
    select had the two the wrong way round, so picking "Always on" wrote a 0 and
    switched the boiler off.
    """
    entity = _load(filename)["entity"]
    reported = entity["sensor"]["bo_mode"]["state"]
    settable = entity["select"]["bo_holding_mode"]["state"]

    assert {state: _comparable(text) for state, text in settable.items()} == {
        state: _comparable(text) for state, text in reported.items()
    }


def test_the_locked_state_is_still_translated() -> None:
    """The state hassfest rejects has to keep working, that is the whole point."""
    for filename in FILENAMES:
        sensors = _load(filename)["entity"]["sensor"]
        for key in ("bo_circulation", "bo_single_charge"):
            assert sensors[key]["state"]["-1"]
