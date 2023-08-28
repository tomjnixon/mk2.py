import struct
from dataclasses import dataclass
from enum import Enum, Flag
from typing import Optional
from ..framing import MK2Frame
from .types import Command


class SwitchState(Enum):
    CHARGER_ONLY = 1
    INVERTER_ONLY = 2
    ON = 3
    OFF = 4


class StateFlags(Flag):
    AUTO_SEND_STATE = 1 << 0
    AUTO_APPEND_LED_STATE = 1 << 1
    NO_SEND_PANEL_STATE = 1 << 4
    AUTO_FORWARD_PANEL_FRAMES = 1 << 6
    CURRENT_LIMIT_IN_AMPS = 1 << 7


class StateFlagsExt0(Flag):
    SHORT_WINMON_FRAMES = 1 << 0
    FORWARD_CONFIG_RESPONSES = 1 << 2
    IGNORE_BLOCK_MODE = 1 << 3


class StateEEPROMFlags(Flag):
    FORCE_VEBUS_MODE = 1 << 0
    BLOCK_XMT = 1 << 1


@dataclass
class StateCommand2(Command):
    """switch command variant 2"""

    switch_state: SwitchState
    limit: Optional[int]  # None -> ignore this
    flags: StateFlags
    flags_ext_0: Optional[StateFlagsExt0] = None
    eeprom_flags: Optional[StateEEPROMFlags] = None

    def as_frame(self):
        assert (self.flags_ext_0 is None) == (
            self.eeprom_flags is None
        ), "flags_ext_0 and eeprom_flags must be used together"
        flags = self.flags | StateFlags.CURRENT_LIMIT_IN_AMPS
        limit = self.limit if self.limit is not None else 0x8000

        base_fmt = "<BHBB"
        base_args = self.switch_state.value, limit, 0x1, flags.value

        if self.flags_ext_0 is not None and self.eeprom_flags is not None:
            return MK2Frame(
                b"S",
                struct.pack(
                    base_fmt + "xBB",
                    *base_args,
                    self.flags_ext_0.value,
                    self.eeprom_flags.value,
                ),
            )
        else:
            return MK2Frame(b"S", struct.pack(base_fmt, *base_args))
