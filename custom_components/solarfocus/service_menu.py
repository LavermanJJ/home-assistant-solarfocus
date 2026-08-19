"""The codes the service menu of the eco manager-touch asks for.

Neither of them is a register. The controller asks for a code before it opens
its service menu, and the code is arithmetic on the date - which is why this is
the one corner of the integration that computes rather than reads, and why the
entities of it sit on the controller rather than on any component.
"""

from collections.abc import Callable
from datetime import datetime

from homeassistant.core import CALLBACK_TYPE


def weekday(when: datetime) -> int:
    """Return the day of the week the way Solarfocus counts it: Sunday is 1.

    Home Assistant counts from Monday, as Python does, so Sunday is the day the
    two disagree about - and the one day in seven a code comes out wrong if the
    shift is left out.
    """
    return 1 if when.weekday() == 6 else when.weekday() + 2


def service_code(when: datetime) -> int:
    """Return the code the service menu asks for on that date.

    The day of the month and the month, each weighted with the day of the week.
    """
    day = weekday(when)

    return when.day * (day + 1) + when.month * day


def installer_code(displayed: float, when: datetime) -> int:
    """Return the installer code for the number the display is showing.

    The installer menu goes one step further than the service menu: it shows a
    number of its own and takes back that number times the day of the week. So
    unlike the service code this one cannot be computed from the date alone -
    it needs what is on the display, which is what the number entity takes.
    """
    return int(displayed) * weekday(when)


class DisplayedNumber:
    """The number the installer menu shows, shared by the two entities of it.

    The user types it into a number entity and a sensor multiplies it. Both are
    on the controller and neither is a register, so the value lives here, on the
    coordinator - the one thing per config entry that every platform is handed.

    Nothing is stored here: the number entity restores what was typed before a
    restart and writes it back, which is what makes the sensor report again.
    """

    def __init__(self) -> None:
        """Start out with nothing entered."""
        self._value: float | None = None
        self._listeners: list[CALLBACK_TYPE] = []

    @property
    def value(self) -> float | None:
        """Return the number last entered, or None while there is none."""
        return self._value

    def set(self, value: float | None) -> None:
        """Take a new number, and tell whoever reports what it comes to."""
        self._value = value

        for listener in list(self._listeners):
            listener()

    def subscribe(self, listener: CALLBACK_TYPE) -> Callable[[], None]:
        """Call `listener` on every change; the return removes it again."""
        self._listeners.append(listener)

        def unsubscribe() -> None:
            self._listeners.remove(listener)

        return unsubscribe
