import enum
from dataclasses import dataclass
from enum import Enum, Flag
from typing import Optional


class Setting(Enum):
    # don't write and read settings directly, use read_setting_flags and
    # write_setting_flags
    FLAGS0 = 0
    FLAGS1 = 1

    I_BAT_BULK = 4
    VS_USAGE = 15
    VS2_OFF_U_BAT_HIGH = 58

    VS_OFF_I_INV_LOW = 28
    VS_T_OFF_I_INV_LOW = 31

    # lower ignore AC limits with dedicated ignore AC input
    VS2_OFF_I_LOAD_LOW = 56
    VS2_T_OFF_I_LOAD_LOW = 57  # docs missing _T

    BAT_CAPACITY = 64
    BAT_SOC_BULK_END = 65

    # undocumented, set by VE Configure
    VS_SOC_LIMIT_PERCENT = 70


class SettingFlags(Flag, boundary=enum.KEEP):
    DISABLE_WAVE_CHECK = 1 << 3
    DISABLE_CHARGE = 1 << 6
    DISABLE_WAVE_CHECK_INVERTED = 1 << 7

    # to make flag inversion work
    _ALL_FLAGS = 0xFFFFFFFF


@dataclass
class SettingInfo:
    scale: float
    offset: int
    # note: these are unscaled/raw, as some info is lost when converting
    default: int
    minimum: int
    maximum: int
    access_level: Optional[int]

    def from_raw_value(self, raw_value: int) -> float:
        return self.scale * (raw_value + self.offset)

    def to_raw_value(self, value: float) -> int:
        raw_value = int(round((value / self.scale) - self.offset))
        # rounding means this should never happen if the scaled value is in range
        assert self.minimum <= raw_value <= self.maximum
        return raw_value
