"""Validate the icon translations.

`icons.json` gives every entity its icon, keyed by the translation key
`create_description` builds. Two things break that silently: an entity that sets
an icon itself, because the icon of the entity is part of its state and wins over
the translation, and a key that no entity uses, because renaming an entity leaves
the old key behind and the entity falls back to the icon of its device class.

Neither shows up in a test of the platforms, only in the frontend, which is what
these tests are for.
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


def _translated_icons():
    """Yield every (domain, translation key, icon) of the icon translations."""
    for domain, entities in _icons().get("entity", {}).items():
        for key, sections in entities.items():
            for icon in sections.values():
                yield domain, key, icon


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
