from dataclasses import dataclass
from enum import Enum
from typing import Optional
from ..framing import MK2Frame
from .types import Command, Reply, register_reply_type


class LEDState(Enum):
    """state of one LED"""

    OFF = 0
    ON = 1
    BLINK = 2
    BLINK_ANTIPHASE = 3


class LED(Enum):
    """identifies one LED"""

    MAINS = 0
    ABSORPTION = 1
    BULK = 2
    FLOAT = 3
    INVERTER = 4
    OVERLOAD = 5
    LOW_BATTERY = 6
    TEMPERATURE = 7


@dataclass
class LEDStates:
    """the state of all LEDs"""

    led_on: int
    led_blink: int

    def state(self, led: LED) -> LEDState:
        state_on = (self.led_on >> led.value) & 1
        state_blink = (self.led_blink >> led.value) & 1
        state_num = state_on | (state_blink << 1)
        return LEDState(state_num)

    @property
    def states(self) -> dict[LED, LEDState]:
        return {led: self.state(led) for led in LED}


@register_reply_type
@dataclass
class LEDStatusReply(Reply):
    states: Optional[LEDStates]

    frame_type = MK2Frame
    command = b"L"

    @classmethod
    def parse(cls, frame):
        # docs say this is 2 or 3 (and 3rd byte zero), but actually 6 (possibly
        # the official tools configure this to include extra data)
        if len(frame.data) not in (2, 3, 6):
            raise ValueError(f"wrong length: expected 2, 3 or 6, got {len(frame.data)}")
        led_on, led_blink = frame.data[:2]
        if led_on == 0x1F and led_blink == 0x1F:
            return cls(None)
        else:
            return cls(LEDStates(led_on, led_blink))


@dataclass
class LEDStatusCommand(Command):
    def as_frame(self):
        return MK2Frame(b"L", b"")
