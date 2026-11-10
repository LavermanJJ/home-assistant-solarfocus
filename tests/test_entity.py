"""Test the Solarfocus base entity.

What both of these are about is the wire: register 33409 is signed, and a
negative setpoint has to leave as a two's complement word or the controller
reads it as 65036 watts of export. The arithmetic used to be here, reaching
into the library's value objects to do it; it is the library's now, and these
hold it to the same words.
"""

from unittest.mock import MagicMock

from aiosolarfocus import ApiVersion, RegisterKind, SolarfocusConnectionError
import pytest

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.solarfocus.const import (
    PHOTOVOLTAIC_COMPONENT,
    PHOTOVOLTAIC_COMPONENT_PREFIX,
)
from custom_components.solarfocus.entity import (
    SolarfocusEntity,
    SolarfocusEntityDescription,
    create_description,
)

from .conftest import (
    build_client,
    build_config_entry,
    build_coordinator,
    controller_of,
    written,
)


def _entity() -> SolarfocusEntity:
    """Create an entity writing to the photovoltaic component."""
    entry = build_config_entry(
        api_version=ApiVersion.V_26_020.label, photovoltaic=True
    )
    coordinator = build_coordinator(entry, build_client(entry))

    entity = SolarfocusEntity(
        coordinator,
        create_description(
            PHOTOVOLTAIC_COMPONENT,
            PHOTOVOLTAIC_COMPONENT_PREFIX,
            "",
            SolarfocusEntityDescription(key="grid_im_export"),
        ),
    )
    # Not added to Home Assistant, so there is no state machine to write to.
    entity.async_write_ha_state = MagicMock()

    return entity


async def test_a_negative_value_goes_out_as_twos_complement() -> None:
    """Negative values have to be written as unsigned words."""
    entity = _entity()

    await entity._async_set_native_value("grid_im_export", -500)

    assert written(entity.coordinator.client) == [
        (RegisterKind.HOLDING, 33409, (65036,))
    ]
    # The entity keeps reporting the signed value, without re-reading anything:
    # a write the controller took updates the component's own cache.
    assert entity._get_native_value("grid_im_export") == -500


async def test_a_value_the_register_cannot_take_is_the_users_to_correct() -> None:
    """A validation error with a sentence, not "Unknown error" and a traceback."""
    entity = _entity()

    with pytest.raises(ServiceValidationError) as failure:
        await entity._async_set_native_value("grid_im_export", 10**9)

    assert failure.value.translation_key == "value_not_accepted"
    assert "10" in failure.value.translation_placeholders["reason"]
    assert written(entity.coordinator.client) == []
    entity.async_write_ha_state.assert_not_called()


async def test_a_controller_that_cannot_be_written_to_says_so() -> None:
    entity = _entity()
    controller_of(entity.coordinator.client).fail_with = SolarfocusConnectionError(
        "the connection dropped"
    )

    with pytest.raises(HomeAssistantError) as failure:
        await entity._async_set_native_value("grid_im_export", 500)

    assert not isinstance(failure.value, ServiceValidationError)
    assert failure.value.translation_key == "write_failed"
    assert failure.value.translation_placeholders["reason"] == "the connection dropped"
    entity.async_write_ha_state.assert_not_called()


async def test_a_positive_value_goes_out_unchanged() -> None:
    """Positive values are written as they are."""
    entity = _entity()

    await entity._async_set_native_value("grid_im_export", 500)

    assert written(entity.coordinator.client) == [
        (RegisterKind.HOLDING, 33409, (500,))
    ]
    assert entity._get_native_value("grid_im_export") == 500


async def test_a_write_does_not_re_read_the_component() -> None:
    """The re-read after every write is gone.

    It used to be a blocking `component.update()` on the event loop, per write -
    so a climate service call was four writes and four whole-component reads.
    """
    entity = _entity()

    await entity._async_set_native_value("grid_im_export", 500)

    assert not controller_of(entity.coordinator.client).reads
