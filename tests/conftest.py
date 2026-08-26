"""Fixtures for the Solarfocus tests."""

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

from aiosolarfocus import (
    ApiVersion,
    ComponentId,
    RegisterKind,
    SolarfocusClient,
    SolarfocusConfig,
    SolarfocusConnectionError,
    Systems,
)
from aiosolarfocus.codec import words_to_raw
from aiosolarfocus.testing import FakeController
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solarfocus.const import (
    CONF_BIOMASS_BOILER,
    CONF_BOILER,
    CONF_BUFFER,
    CONF_CIRCULATION,
    CONF_DIFFERENTIAL_MODULE,
    CONF_DOOR_CONTACT_INVERTED,
    CONF_FRESH_WATER_MODULE,
    CONF_HEATING_CIRCUIT,
    CONF_HEATPUMP,
    CONF_PHOTOVOLTAIC,
    CONF_SOLAR,
    CONF_SOLARFOCUS_SYSTEM,
    DEFAULT_NAME,
    DOMAIN,
    build_unique_id,
    component_count,
    solar_count,
)
from custom_components.solarfocus.service_menu import DisplayedNumber
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
)

# The config entry version the integration currently migrates to.
CURRENT_VERSION = 12


def build_data(system: Systems = Systems.VAMPAIR) -> dict:
    """Return the entry data: what it takes to read the heating system at all."""
    return {
        CONF_NAME: DEFAULT_NAME,
        CONF_SOLARFOCUS_SYSTEM: system,
        CONF_HOST: "solarfocus.local",
        CONF_PORT: 502,
        # `label`, not `value`: an entry stores the version as the controller
        # prints it, and an `ApiVersion` is numbered for ordering.
        CONF_API_VERSION: ApiVersion.V_23_020.label,
    }


def build_options(**overrides) -> dict:
    """Return config entry options with all components off unless overridden."""
    options = {
        CONF_SCAN_INTERVAL: 10,
        CONF_HEATING_CIRCUIT: 0,
        CONF_BUFFER: 0,
        CONF_BOILER: 0,
        CONF_FRESH_WATER_MODULE: 0,
        CONF_CIRCULATION: 0,
        CONF_DIFFERENTIAL_MODULE: 0,
        CONF_SOLAR: 0,
        CONF_HEATPUMP: False,
        CONF_BIOMASS_BOILER: False,
        CONF_PHOTOVOLTAIC: False,
        CONF_DOOR_CONTACT_INVERTED: False,
    }
    options.update(overrides)
    return options


def build_config_entry(
    system: Systems = Systems.VAMPAIR, **overrides
) -> MockConfigEntry:
    """Return a config entry in the layout the current version stores.

    An override goes to whichever half of the entry holds that setting, so a
    test says what its entry is rather than where the integration keeps it.
    """
    data = build_data(system)
    options = build_options()

    for setting, value in overrides.items():
        if setting in data:
            data[setting] = value
        elif setting in options:
            options[setting] = value
        else:
            raise KeyError(f"{setting} is in neither the data nor the options")

    return MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        version=CURRENT_VERSION,
        unique_id=build_unique_id(data[CONF_HOST], data[CONF_PORT]),
        data=data,
        options=options,
    )


def every_component(system: Systems = Systems.VAMPAIR, **overrides) -> dict:
    """Return options asking for everything this system can have at once.

    The heat source is the one part of the layout the system decides rather
    than the user, and the library refuses the combination the config flow has
    never offered - a Vampair has the heat pump, everything else has the
    biomass boiler - so which of the two is asked for follows the system.
    """
    options = {
        CONF_HEATING_CIRCUIT: 1,
        CONF_BUFFER: 1,
        CONF_BOILER: 1,
        CONF_FRESH_WATER_MODULE: 1,
        CONF_CIRCULATION: 1,
        CONF_DIFFERENTIAL_MODULE: 1,
        CONF_SOLAR: 1,
        CONF_PHOTOVOLTAIC: True,
        CONF_HEATPUMP: system is Systems.VAMPAIR,
        CONF_BIOMASS_BOILER: system is not Systems.VAMPAIR,
    }
    options.update(overrides)

    return options


class OfflineController(FakeController):
    """A controller that is not there at all, on every attempt.

    `FakeController.fail_with` raises once and clears, which is a socket that
    drops and comes back. This is the other outage: nothing at the address.
    """

    async def connect(self) -> None:
        """Refuse the connection, as an address with nothing on it does."""
        raise SolarfocusConnectionError("no route to host", context="connecting")


def build_config(entry: MockConfigEntry) -> SolarfocusConfig:
    """Return the library configuration this entry describes.

    The same translation `async_setup_entry` makes, so a test that drives the
    client directly is driving the one the integration would have built.
    """
    return SolarfocusConfig(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        system=Systems(entry.data[CONF_SOLARFOCUS_SYSTEM]),
        api_version=ApiVersion.parse(entry.data[CONF_API_VERSION]),
        heating_circuits=entry.options[CONF_HEATING_CIRCUIT],
        buffers=entry.options[CONF_BUFFER],
        boilers=entry.options[CONF_BOILER],
        fresh_water_modules=entry.options[CONF_FRESH_WATER_MODULE],
        circulations=component_count(entry, CONF_CIRCULATION),
        differential_modules=component_count(entry, CONF_DIFFERENTIAL_MODULE),
        solar=solar_count(entry),
        heat_pump=entry.options[CONF_HEATPUMP],
        biomass_boiler=entry.options[CONF_BIOMASS_BOILER],
        photovoltaic=entry.options[CONF_PHOTOVOLTAIC],
    )


def build_client(
    entry: MockConfigEntry | None = None,
    *,
    controller: FakeController | None = None,
    **config_overrides: Any,
) -> SolarfocusClient:
    """Return a real client, reading a controller that is not real.

    The library ships `FakeController` for exactly this: it refuses an address
    the firmware does not map, hands out a 32-bit register only whole, and
    compacts a read that spans a gap - the three behaviours that have caused
    every register bug this integration has had. A mock of the client would
    agree with whatever the test expected instead.
    """
    if entry is None:
        entry = build_config_entry(
            heating_circuit=1, buffer=1, boiler=1, heatpump=True
        )

    config = build_config(entry)
    if config_overrides:
        config = replace_config(config, **config_overrides)

    return SolarfocusClient(
        config, transport=controller or FakeController.for_config(config)
    )


def replace_config(config: SolarfocusConfig, **overrides: Any) -> SolarfocusConfig:
    """Return the configuration with some fields changed.

    `SolarfocusConfig` is frozen, and validates in `__post_init__`, so this is
    a new one rather than an edit.
    """
    fields = {
        name: getattr(config, name)
        for name in SolarfocusConfig.__dataclass_fields__
    }

    return SolarfocusConfig(**{**fields, **overrides})


def controller_of(client: SolarfocusClient) -> FakeController:
    """Return the fake controller a client built by `build_client` reads."""
    controller = client._transport  # noqa: SLF001
    assert isinstance(controller, FakeController)

    return controller


@pytest.fixture(name="config_entry")
def config_entry_fixture() -> MockConfigEntry:
    """Return a vampair config entry with one of every multi-instance component."""
    return build_config_entry(
        heating_circuit=1,
        buffer=1,
        boiler=1,
        heatpump=True,
    )


@pytest.fixture(name="client")
def client_fixture(config_entry: MockConfigEntry) -> SolarfocusClient:
    """Return the client the entry of the `config_entry` fixture describes."""
    return build_client(config_entry)


class ClientFactory:
    """Stands in for the `SolarfocusClient` constructor during a test.

    It builds a real client every time, over a controller that is not real, so
    the client under test is always the one the entry actually describes - a
    fixture built ahead of time would be the client of whatever entry the
    fixture happened to use, and half these tests set up their own.

    `offline()` before the entry is set up is an address with nothing on it;
    `controller` afterwards is what the client just read, for a test that wants
    to put a value somewhere or take a register away.
    """

    def __init__(self) -> None:
        """Start with no clients built and a controller that answers."""
        self.instances: list[SolarfocusClient] = []
        self.controller_type: type[FakeController] = FakeController
        self._silenced: list[tuple[ComponentId | str, int]] = []
        self._readings: list[tuple[ComponentId | str, str, float, int]] = []

    def __call__(self, config: SolarfocusConfig, **kwargs: Any) -> SolarfocusClient:
        """Build the client the integration asked for."""
        client = SolarfocusClient(
            config, transport=self.controller_type.for_config(config)
        )
        self.instances.append(client)

        for component, register, value, index in self._readings:
            set_reading(client, component, register, value, index=index)
        for component, index in self._silenced:
            silence(client, component, index=index)

        return client

    def offline(self) -> None:
        """Have every client built after this find nothing at the address."""
        self.controller_type = OfflineController

    def online(self) -> None:
        """Have every client built after this reach the controller again."""
        self.controller_type = FakeController

    def reads(
        self,
        component: ComponentId | str,
        register: str,
        value: float,
        *,
        index: int = 1,
    ) -> None:
        """Have one register already hold a value when the entry loads.

        The entry builds its own client, so a test that wants a reading in
        place before the first refresh cannot reach it beforehand - the
        instruction is kept and applied to every client built afterwards.
        """
        self._readings.append((component, register, value, index))
        for client in self.instances:
            set_reading(client, component, register, value, index=index)

    def silence(self, component: ComponentId | str, *, index: int = 1) -> None:
        """Have one component answer nothing, before or after the entry loads.

        Before is the common case - a test wants the entry to set up with the
        component already failing - and the client does not exist yet then, so
        the instruction is kept and applied to every client built afterwards.
        """
        self._silenced.append((component, index))
        for client in self.instances:
            silence(client, component, index=index)

    @property
    def instance(self) -> SolarfocusClient:
        """The client built last, which is the one the entry is using."""
        return self.instances[-1]

    @property
    def controller(self) -> FakeController:
        """The controller that client is reading."""
        return controller_of(self.instance)


@pytest.fixture(name="mock_client")
def mock_client_fixture() -> Iterator[ClientFactory]:
    """Patch SolarfocusClient everywhere the integration constructs one.

    Both patch targets are import-site names, so this holds only as long as
    both modules go on importing the class by name.
    """
    factory = ClientFactory()

    with (
        patch(
            "custom_components.solarfocus.SolarfocusClient", side_effect=factory
        ) as constructor,
        patch(
            "custom_components.solarfocus.config_flow.SolarfocusClient",
            side_effect=factory,
        ),
    ):
        factory.constructor = constructor  # type: ignore[attr-defined]
        yield factory


def build_coordinator(entry, client: SolarfocusClient | None = None) -> MagicMock:
    """Return a coordinator stub that entities can read from."""
    coordinator = MagicMock()
    coordinator._entry = entry
    coordinator.client = client if client is not None else build_client(entry)
    coordinator.last_update_success = True
    # Every component reads, so the entities on them are available. A stub of it
    # rather than whatever a MagicMock makes of `in`, which is what availability
    # asks of this.
    coordinator.failed_components = frozenset()
    # The real one, not a mock: the number the installer menu shows is shared
    # between two entities, and what a test of either is about is that sharing.
    coordinator.displayed_number = DisplayedNumber()
    return coordinator


def set_value(
    client: SolarfocusClient,
    component: ComponentId | str,
    register: str,
    raw: int,
    *,
    index: int = 1,
) -> None:
    """Put a raw word where one register of one component is read from.

    Named by the register rather than by an address, because an address is a
    fact about a firmware and a system and the layout already knows it.

    The word goes to the controller and into the component's own readings, so
    it is both what the next poll would find and what the entity reads now -
    the component holds the last reading, and a test that only put a word on
    the wire would be reading whatever the component last decoded, which is
    nothing.
    """
    instance = client.of(ComponentId(component))[index - 1]
    resolved = instance.layout.by_name[register]
    controller = controller_of(client)

    width = len(resolved.addresses)
    words = {}
    for offset, address in enumerate(resolved.addresses):
        word = (raw >> (16 * (width - 1 - offset))) & 0xFFFF
        controller.set(resolved.kind, address, word)
        words[(resolved.kind, address)] = word

    instance.decode_readings(words)


def set_reading(
    client: SolarfocusClient,
    component: ComponentId | str,
    register: str,
    value: float,
    *,
    index: int = 1,
) -> None:
    """Have one register read as a value, in the unit the entity reports.

    The scale is the register's own, so a test says "the boiler is at 55
    degrees" rather than "word 550 sits at address 501" - and the word that
    ends up at the address is the one a real controller would have sent.
    """
    instance = client.of(ComponentId(component))[index - 1]
    resolved = instance.layout.by_name[register]

    set_value(
        client,
        component,
        register,
        round(value / resolved.register.scale),
        index=index,
    )


def written_by_name(
    client: SolarfocusClient,
    component: ComponentId | str,
    *,
    index: int = 1,
) -> dict[str, float]:
    """Return what was written to one component, keyed by register name.

    A write used to be one call of the entity's own setter per register, so a
    test could watch the setter. They go out as one group now - the register
    document requires it - so what a test can watch is the wire, and this puts
    the names back on it.
    """
    instance = client.of(ComponentId(component))[index - 1]
    at_address = {
        (resolved.kind, resolved.address): resolved
        for resolved in instance.layout.registers
    }

    values: dict[str, float] = {}
    for kind, address, words in controller_of(client).writes:
        resolved = at_address.get((kind, address))
        if resolved is None:
            continue
        raw = words_to_raw(words, signed=resolved.register.signed)
        # A register that scales a write differently from a read says so;
        # otherwise the two are the same.
        scale = resolved.register.write_scale or resolved.register.scale
        values[resolved.name] = raw * scale

    return values


def written(client: SolarfocusClient) -> list[tuple[RegisterKind, int, tuple[int, ...]]]:
    """Return every write the controller has been asked for, in order."""
    return list(controller_of(client).writes)


def silence(
    client: SolarfocusClient, component: ComponentId | str, *, index: int = 1
) -> None:
    """Have one component instance answer nothing, as a real one does.

    A firmware that does not have a register range refuses a read that starts
    in it, and the library attributes that to the components whose registers
    were in the read. Taking the addresses away is how a fake controller says
    the same thing - which is a good deal closer to the real failure than the
    predecessor's tests got, where a component that could not be read was a
    mock returning `False`.
    """
    instance = client.of(ComponentId(component))[index - 1]
    controller = controller_of(client)

    for resolved in instance.layout.registers:
        controller.unmap(resolved.kind, *resolved.addresses)


def revive(
    client: SolarfocusClient, component: ComponentId | str, *, index: int = 1
) -> None:
    """Give one component instance its registers back, as a firmware never does.

    The counterpart of `silence`, for the tests about a component coming back:
    a real controller answering again is a register range that starts working,
    which from here is the address being mapped once more.
    """
    instance = client.of(ComponentId(component))[index - 1]
    controller = controller_of(client)

    for resolved in instance.layout.registers:
        for address in resolved.addresses:
            controller.set(resolved.kind, address, 0)
