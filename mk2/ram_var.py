from dataclasses import dataclass
from enum import Enum


class RAMVar(Enum):
    U_MAINS_RMS = 0
    I_MAINS_RMS = 1
    U_INVERTER_RMS = 2
    I_INVERTER_RMS = 3
    U_BAT = 4
    I_BAT = 5
    U_BAT_RMS = 6
    INVERTER_PERIOD = 7
    MAINS_PERIOD = 8
    SIGNED_AC_LOAD_CURRENT = 9
    VIRTUALSWITCH_POSITION = 10
    IGNORE_AC_INPUT = 11
    MULTI_FUNCTIONAL_RELAY_STATE = 12
    CHARGE_STATE = 13

    # power through inverter, towards battery (+ve charging, -ve inverting)
    #
    # this seems to include inefficiencies in pass-through mode, which makes
    # sense but means it doesn't always correspond with the charge current
    INVERTER_POWER = 14
    # power through AC input, towards input (-ve consuming)
    # NOTE: the spec is wrong, repeating the description for INVERTER_POWER
    INPUT_POWER = 15
    # power through AC output, towards output (+ve load)
    OUTPUT_POWER = 16

    # unfiltered versions of the above
    INVERTER_POWER_UNFILTERED = 17
    INPUT_POWER_UNFILTERED = 18
    OUTPUT_POWER_UNFILTERED = 19

    # undocumented, not sure what unit
    BAT_TEMPERATURE = 21


@dataclass(frozen=True, eq=True)
class OtherRAMVar:
    """for accessing RAM locations not defined in RAMVar"""

    value: int


AnyRAMVar = RAMVar | OtherRAMVar


class RAMVarInfo:
    """type and scaling info for a RAM variable"""

    def from_raw_value(self, raw_value: int) -> float | bool:
        raise NotImplementedError()

    def to_raw_value(self, value: float | int | bool) -> int:
        raise NotImplementedError()


@dataclass
class FloatRAMVarInfo(RAMVarInfo):
    scale: float
    offset: int

    def from_raw_value(self, raw_value: int) -> float:
        return self.scale * (raw_value + self.offset)

    def to_raw_value(self, value: float | int | bool) -> int:
        assert isinstance(value, (float, int))
        scaled = (value / self.scale) - self.offset
        return int(round(scaled))


class SignedRAMVarInfo(FloatRAMVarInfo):
    def from_raw_value(self, raw_value: int) -> float:
        raw_signed = (raw_value & 0x7FFF) - (raw_value & 0x8000)  # sign extend
        return FloatRAMVarInfo.from_raw_value(self, raw_signed)

    def to_raw_value(self, value: float | int | bool) -> int:
        assert isinstance(value, (float, int))
        raw_signed = FloatRAMVarInfo.to_raw_value(self, value)
        assert -0x8000 <= raw_signed <= 0x7FFF
        return raw_signed & 0xFFFF


class UnsignedRAMVarInfo(FloatRAMVarInfo):
    pass


@dataclass
class BitRamVarInfo(RAMVarInfo):
    bit: int

    def from_raw_value(self, raw_value: int) -> bool:
        return bool((raw_value >> self.bit) & 1)

    def to_raw_value(self, value: float | int | bool) -> int:
        assert isinstance(value, bool)
        return bool(value) << self.bit
