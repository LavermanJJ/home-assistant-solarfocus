"""Validate the icon translations.

`icons.json` gives every entity its icon, keyed by the translation key
`create_description` builds. Two things break that silently: an entity that sets
an icon itself, because the icon of the entity is part of its state and wins over
the translation, and a key that no entity uses, because renaming an entity leaves
the old key behind and the entity falls back to the icon of its device class.

An icon for a state that the entity never reports is just as invisible, and the
rules hassfest applies to the file only fail in CI, so they are checked here too.

None of it shows up in a test of the platforms, only in the frontend, which is
what these tests are for.
"""

import itertools
import json
import pathlib
import re

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
from custom_components.solarfocus.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.icon import async_get_icons

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


def _icons() -> dict:
    with (COMPONENT_DIR / "icons.json").open(encoding="utf-8") as fh:
        return json.load(fh)


def _sections(data: dict):
    """Yield every ((domain, key, attribute), section) of an entity structure.

    A section is what holds a `default` and a `state`. Entities have one and so do
    their attributes, which is where the preset modes of the thermostat live.
    """
    for domain, entities in data.get("entity", {}).items():
        for key, section in entities.items():
            yield (domain, key, None), section
            for name, attribute in section.get("state_attributes", {}).items():
                yield (domain, key, name), attribute


def _icon_sections():
    """Yield every ((domain, key, attribute), section) of the icon translations."""
    yield from _sections(_icons())


def _icon_ranges():
    """Yield every ((domain, key, attribute), range) of the icon translations.

    A `range` is what a numeric entity has where an enum has a `state`: the icon
    shown is the one of the highest key the value does not fall below.
    """
    for path, section in _icon_sections():
        if "range" in section:
            yield path, section["range"]


def _translated_icons():
    """Yield every (domain, translation key, icon) of the icon translations."""
    for (domain, key, _), section in _icon_sections():
        if "default" in section:
            yield domain, key, section["default"]
        for icon in section.get("state", {}).values():
            yield domain, key, icon
        for icon in section.get("range", {}).values():
            yield domain, key, icon


def _translated_states() -> dict[tuple[str, str, str | None], set[str]]:
    """Return the states `strings.json` translates, per entity and attribute."""
    with (COMPONENT_DIR / "strings.json").open(encoding="utf-8") as fh:
        strings = json.load(fh)

    return {
        path: set(section.get("state", {})) for path, section in _sections(strings)
    }


async def _entities(hass: HomeAssistant, module) -> list:
    """Return every entity a platform can create, over all systems."""
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

    return created


async def _translation_keys(hass: HomeAssistant) -> dict[str, set[str]]:
    """Return the translation keys of every entity, per domain."""
    return {
        domain: {
            entity.entity_description.translation_key
            for entity in await _entities(hass, module)
        }
        for domain, module in PLATFORMS.items()
    }


def test_icons_are_valid_json() -> None:
    """A broken file leaves every entity of the integration without an icon."""
    assert _icons()


async def test_home_assistant_serves_the_icons(
    hass: HomeAssistant, enable_custom_integrations
) -> None:
    """Only a file named `icons.json` next to the platforms is picked up at all."""
    icons = await async_get_icons(hass, "entity", integrations=[DOMAIN])

    assert icons[DOMAIN] == _icons()["entity"]


def test_state_icons_belong_to_a_state_of_the_entity() -> None:
    """An icon for a state that is never reported is never shown.

    The states of a sensor and of a select are the ones `strings.json` translates,
    the states of a switch and of a binary sensor are `on` and `off`.
    """
    translated = _translated_states()

    unknown = [
        (*path, state)
        for path, section in _icon_sections()
        for state in section.get("state", {})
        if state not in translated.get(path, {"on", "off"})
    ]

    assert not unknown


def test_no_state_icon_repeats_the_default() -> None:
    """A state that shows the default icon does not need an icon of its own."""
    repeated = [
        (*path, state)
        for path, section in _icon_sections()
        for state, icon in section.get("state", {}).items()
        if icon == section.get("default")
    ]

    assert not repeated


def test_range_keys_are_numbers() -> None:
    """A range is looked up by value, so a key that is not one matches nothing.

    The rule for translation keys does not apply here: these are not keys of a
    translation, they are the bottom of a band of the scale.
    """
    invalid = [
        (*path, key)
        for path, steps in _icon_ranges()
        for key in steps
        if not re.fullmatch(r"-?\d+(\.\d+)?", key)
    ]

    assert not invalid


def test_a_range_starts_at_the_bottom_of_the_scale() -> None:
    """Below the lowest step there is nothing to find but the default icon.

    Every entity with a range reports a percentage, so the scale starts at 0. A
    range that starts higher leaves its own first band showing the default and
    the step is dead, which is invisible in the file itself.
    """
    starting_late = [
        path for path, steps in _icon_ranges() if min(float(key) for key in steps) > 0
    ]

    assert not starting_late


def test_no_range_icon_repeats_the_step_below_it() -> None:
    """Two steps showing one icon is a step that changes nothing.

    Unlike a state, the lowest step is allowed to repeat the default: naming it
    is what keeps the step above it from swallowing the bottom of the scale.
    """
    repeated = [
        (*path, key)
        for path, steps in _icon_ranges()
        for (_, below), (key, icon) in itertools.pairwise(
            sorted(steps.items(), key=lambda step: float(step[0]))
        )
        if icon == below
    ]

    assert not repeated


def test_keys_are_valid_translation_keys() -> None:
    """The rule for translation keys applies to the states as well.

    Which is why "Locked" has no icon of its own: `bo_circulation` and
    `bo_single_charge` report it as -1, and a key cannot start with a hyphen.
    """
    invalid = [
        (*path, name)
        for path, section in _icon_sections()
        for name in (path[1], *section.get("state", {}))
        if not re.fullmatch(r"(?![_-])[a-z0-9-_]+(?<![_-])", name)
    ]

    assert not invalid


def test_icons_use_the_material_design_prefix() -> None:
    """Home Assistant only resolves `mdi:` icons, anything else stays empty."""
    wrong = [
        (domain, key, icon)
        for domain, key, icon in _translated_icons()
        if not icon.startswith("mdi:")
    ]

    assert not wrong


async def test_every_icon_belongs_to_an_entity(hass: HomeAssistant) -> None:
    """A key no entity uses is a leftover of a rename and translates nothing."""
    keys = await _translation_keys(hass)

    unused = [
        (domain, key)
        for domain, key, _ in _translated_icons()
        if key not in keys.get(domain, set())
    ]

    assert not unused


@pytest.mark.parametrize("domain", PLATFORMS, ids=list(PLATFORMS))
async def test_no_entity_brings_its_own_icon(hass: HomeAssistant, domain: str) -> None:
    """An icon on the entity is part of its state and beats the translation."""
    entities = await _entities(hass, PLATFORMS[domain])

    with_icon = [
        entity.entity_description.key for entity in entities if entity.icon is not None
    ]

    assert not with_icon
