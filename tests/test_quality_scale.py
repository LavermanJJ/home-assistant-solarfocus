"""The status this integration claims against the quality scale.

Nothing validates `quality_scale.yaml` for a custom integration, so the file is
only worth having if it cannot quietly go out of date. These tests hold it to
the rule list of the scale, and hold the handful of claims that can be read out
of the source to what the source actually does.

The rules are listed here rather than fetched: the scale gaining a rule should
fail this file and be answered for, which is exactly what a list that has to be
updated by hand does.
"""

import json
import pathlib

import pytest
import yaml

from custom_components.solarfocus import sensor

COMPONENT_DIR = pathlib.Path(sensor.__file__).parent

# `strings.json` is the source of the translations; the files under
# `translations` are what Home Assistant actually loads for a custom
# integration, so a description that only reaches the first of them reaches no
# user.
STRING_FILES = (
    "strings.json",
    "translations/en.json",
    "translations/de.json",
)

PLATFORMS = (
    "binary_sensor",
    "button",
    "climate",
    "number",
    "select",
    "sensor",
    "switch",
    "water_heater",
)

# https://developers.home-assistant.io/docs/core/integration-quality-scale/checklist
BRONZE = {
    "action-setup",
    "appropriate-polling",
    "brands",
    "common-modules",
    "config-flow-test-coverage",
    "config-flow",
    "dependency-transparency",
    "docs-actions",
    "docs-conditions",
    "docs-high-level-description",
    "docs-installation-instructions",
    "docs-removal-instructions",
    "docs-triggers",
    "entity-event-setup",
    "entity-unique-id",
    "has-entity-name",
    "runtime-data",
    "test-before-configure",
    "test-before-setup",
    "unique-config-entry",
}

SILVER = {
    "action-exceptions",
    "config-entry-unloading",
    "docs-configuration-parameters",
    "docs-installation-parameters",
    "entity-unavailable",
    "integration-owner",
    "log-when-unavailable",
    "parallel-updates",
    "reauthentication-flow",
    "test-coverage",
}

GOLD = {
    "devices",
    "diagnostics",
    "discovery-update-info",
    "discovery",
    "docs-data-update",
    "docs-examples",
    "docs-known-limitations",
    "docs-supported-devices",
    "docs-supported-functions",
    "docs-troubleshooting",
    "docs-use-cases",
    "dynamic-devices",
    "entity-category",
    "entity-device-class",
    "entity-disabled-by-default",
    "entity-translations",
    "exception-translations",
    "icon-translations",
    "reconfiguration-flow",
    "repair-issues",
    "stale-devices",
}

PLATINUM = {"async-dependency", "inject-websession", "strict-typing"}

RULES = BRONZE | SILVER | GOLD | PLATINUM


def _quality_scale() -> dict:
    """Return the rules of `quality_scale.yaml`, status and comment separated."""
    with (COMPONENT_DIR / "quality_scale.yaml").open(encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh)

    return {
        rule: entry if isinstance(entry, dict) else {"status": entry}
        for rule, entry in loaded["rules"].items()
    }


SCALE = _quality_scale()


def _status(rule: str) -> str:
    return SCALE[rule]["status"]


def _source(module: str) -> str:
    return (COMPONENT_DIR / f"{module}.py").read_text(encoding="utf-8")


def test_every_rule_of_the_scale_is_answered() -> None:
    """A rule left out is a rule nobody decided about."""
    assert set(SCALE) == RULES


def test_every_status_is_one_the_scale_knows() -> None:
    """`done`, `todo` or `exempt`; anything else means nothing to a reader."""
    wrong = {rule: _status(rule) for rule in SCALE if _status(rule) not in
             ("done", "todo", "exempt")}

    assert not wrong


@pytest.mark.parametrize("status", ["todo", "exempt"])
def test_anything_not_done_says_why(status: str) -> None:
    """`done` speaks for itself. The other two are claims about this integration.

    An exemption without a reason cannot be checked by anyone, and a `todo`
    without one is a note to nobody.
    """
    silent = [
        rule
        for rule in SCALE
        if _status(rule) == status and not SCALE[rule].get("comment", "").strip()
    ]

    assert not silent


def test_the_service_action_exemptions_hold() -> None:
    """Three rules are exempt because the integration registers no actions."""
    for rule in ("action-setup", "docs-actions", "action-exceptions"):
        assert _status(rule) == "exempt"

    registering = [
        path.name
        for path in sorted(COMPONENT_DIR.glob("*.py"))
        if "async_register" in path.read_text(encoding="utf-8")
    ]

    assert not registering
    assert not (COMPONENT_DIR / "services.yaml").exists()


def test_parallel_updates_is_set_where_it_is_claimed() -> None:
    """The rule is about every platform, so one that forgets it fails it."""
    assert _status("parallel-updates") == "done"

    missing = [
        platform
        for platform in PLATFORMS
        if "PARALLEL_UPDATES" not in _source(platform)
    ]

    assert not missing


def test_the_gold_rules_that_are_a_file_or_a_function_exist() -> None:
    """Claims that are true or false by looking, so they are looked at."""
    assert _status("diagnostics") == "done"
    assert "async_get_config_entry_diagnostics" in _source("diagnostics")

    assert _status("reconfiguration-flow") == "done"
    assert "async_step_reconfigure" in _source("config_flow")

    assert _status("repair-issues") == "done"
    assert "async_create_issue" in _source("coordinator")

    assert _status("icon-translations") == "done"
    assert (COMPONENT_DIR / "icons.json").stat().st_size > 0


@pytest.mark.parametrize("strings_file", STRING_FILES)
def test_every_field_of_every_step_is_described(strings_file: str) -> None:
    """Half of the config flow rule, and the half that rots.

    A field added to a form without a `data_description` is one the user is
    asked about with nothing but its label to go on. The other half of the
    rule - the connection in `ConfigEntry.data` and the rest in `.options` -
    is what the config flow and migration tests are about.
    """
    assert _status("config-flow") == "done"

    strings = json.loads((COMPONENT_DIR / strings_file).read_text("utf-8"))
    steps = {**strings["config"]["step"], **strings["options"]["step"]}

    undescribed = {
        step: sorted(set(block.get("data", {})) - set(block.get("data_description", {})))
        for step, block in steps.items()
        if set(block.get("data", {})) - set(block.get("data_description", {}))
    }

    assert not undescribed


@pytest.mark.parametrize("strings_file", STRING_FILES)
def test_every_error_a_form_shows_is_a_string(strings_file: str) -> None:
    """An error with no string reaches the user as its own key.

    The two flows do not share an error block: what the options form returns is
    looked up under `options`, what the config and reconfigure steps return
    under `config`. The options form rejects one thing, a polling interval
    below the minimum; a key left behind on either side is one that no longer
    matches what the flow can say.
    """
    strings = json.loads((COMPONENT_DIR / strings_file).read_text("utf-8"))
    source = _source("config_flow")

    assert set(strings["options"]["error"]) == {"invalid_scan_interval"}

    unused = [key for key in strings["config"]["error"] if f'"{key}"' not in source]

    assert not unused


def test_the_platinum_rules_are_still_open() -> None:
    """Typing and the library, the two that need work outside the checklist."""
    assert _status("strict-typing") == "todo"
    assert not (COMPONENT_DIR / "py.typed").exists()

    assert _status("async-dependency") == "todo"
    # The library is synchronous, which is what the executor calls are for
    assert "async_add_executor_job" in _source("coordinator")
