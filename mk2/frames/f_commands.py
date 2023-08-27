import struct
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from ..framing import MK2Frame, VEBusFrame
from .types import Command, Reply, register_reply_type


class FCommandType(Enum):
    DC_INFO = 0
    L1_INFO = 1


@dataclass
class FCommand(Command):
    frame_type: FCommandType

    def as_frame(self):
        return MK2Frame(b"F", bytes([self.frame_type.value]))


@dataclass
class ResetCommand(Command):
    address: int = 0

    def as_frame(self):
        return MK2Frame(
            b"F",
            struct.pack(
                "<BHH", 8, (self.address >> 16) & 0xFFFF, self.address & 0xFFFF
            ),
        )


def parse_uint24(s):
    a, b, c = s
    return a + (b << 8) + (c << 16)


@dataclass
class DCInfo:
    voltage: float
    inverter_current: float
    charger_current: float
    inverter_period: float


@register_reply_type
@dataclass
class DCInfoReply(Reply):
    voltage: int
    inverter_current: int
    charger_current: int
    inverter_period: int

    frame_type = VEBusFrame
    vebus_frame_type = 0x20

    @classmethod
    def parse(cls, frame):
        if len(frame.data) < 14:
            raise ValueError("frame shorter than expected")

        phase_info = frame.data[4]
        if phase_info != 0x0C:
            return

        voltage, inverter_current, charger_current, inverter_period = struct.unpack(
            "<xxxxxH3s3sB", frame.data[:14]
        )

        inverter_current = parse_uint24(inverter_current)
        charger_current = parse_uint24(charger_current)

        return cls(voltage, inverter_current, charger_current, inverter_period)


class MainState(Enum):
    DOWN = 0x0
    STARTUP = 0x1
    OFF = 0x2
    SLAVE = 0x3
    INVERT_FULL = 0x4
    INVERT_HALF = 0x5
    INVERT_AES = 0x6
    POWER_ASSIST = 0x7
    BYPASS = 0x8
    STATE_CHARGE = 0x9


@dataclass
class ACInfo:
    phase: int
    num_phases: Optional[int]

    state: MainState
    mains_voltage: float
    mains_current: float
    inverter_voltage: float
    inverter_current: float
    mains_period: float


@register_reply_type
@dataclass
class ACInfoReply(Reply):
    phase: int
    num_phases: Optional[int]

    state: MainState
    mains_voltage: int
    mains_current: int
    inverter_voltage: int
    inverter_current: int
    mains_period: int

    frame_type = VEBusFrame
    vebus_frame_type = 0x20

    @classmethod
    def parse(cls, frame):
        phase_info = frame.data[4]
        if not (0x05 <= phase_info <= 0x0B):
            return

        phase_map = {
            0x05: (4, None),
            0x06: (3, None),
            0x07: (2, None),
            0x08: (1, 1),
            0x09: (1, 2),
            0x0A: (1, 3),
            0x0B: (1, 4),
        }
        phase, num_phases = phase_map[phase_info]

        (
            bf_factor,
            inverter_factor,
            state,
            mains_voltage,
            mains_current,
            inverter_voltage,
            inverter_current,
            mains_period,
        ) = struct.unpack("<BBxBxHHHHB", frame.data[:14])

        state = MainState(state)

        mains_current *= bf_factor
        inverter_current *= inverter_factor

        return cls(
            phase,
            num_phases,
            state,
            mains_voltage,
            mains_current,
            inverter_voltage,
            inverter_current,
            mains_period,
        )
