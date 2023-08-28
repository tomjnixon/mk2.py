import struct
import warnings
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from ..framing import MK2Frame
from ..ram_var import (
    AnyRAMVar,
    BitRamVarInfo,
    RAMVarInfo,
    SignedRAMVarInfo,
    UnsignedRAMVarInfo,
)
from ..setting import Setting, SettingInfo
from .types import Command, Reply, register_reply_type

# winmon commands (whatever those are)

# originally these were sent with a "W" followed by two bytes, but were
# extended to "mode 2", in two ways:
#
# - to support up to 6 bytes, and
# - can be sent and received with X, Y and Z commands, to allow pipelining
#   commands
#
# the spec isn't clear on this, but the only way to get more than 2 bytes in a
# command to work is to enable mode 2 using the "S" command, and use X, Y and Z
# commands, otherwise any bytes after the second are ignored
#
# originally i wasn't going to implement X/Y/Z commands, but WriteViaID is
# useful and is more than two bytes, so this just always uses X instead of W
# and ignores pipelining, for now. mode 2 needs to be enabled to use these;
# this is done in VEBusSession


@register_reply_type
@dataclass
class UnknownCommandReply(Reply):
    # in theory zero means the W command was not recognised, and otherwise bits
    # set indicate the byte after that was not recognised
    info: int

    frame_type = MK2Frame
    command = b"X"

    @classmethod
    def parse(cls, frame):
        if len(frame.data) > 1 and frame.data[0] == 0x80:
            return cls(frame.data[1])


@dataclass
class GetRAMVarInfoCommand(Command):
    ram_var: AnyRAMVar

    def as_frame(self):
        return MK2Frame(b"X", struct.pack("<BH", 0x36, self.ram_var.value))


@register_reply_type
@dataclass
class GetRAMVarInfoReply(Reply):
    info: Optional[RAMVarInfo]

    frame_type = MK2Frame
    command = b"X"

    @classmethod
    def parse(cls, frame):
        if len(frame.data) > 0 and frame.data[0] == 0x8E:
            if len(frame.data) == 1:
                scale = 0
                warnings.warn(
                    "empty CommandGetRAMVarInfo reply, assuming scale=0 (unsupported)"
                )
            elif len(frame.data) == 3:
                (scale,) = struct.unpack("<h", frame.data[1:])
                if scale != 0:
                    raise ValueError("short reply has non-zero scale")
            elif len(frame.data) == 5:
                scale, offset = struct.unpack("<hh", frame.data[1:])
            elif len(frame.data) == 6:
                scale, cmd2, offset = struct.unpack("<hBh", frame.data[1:])
                if cmd2 != 0x8F:
                    raise ValueError("second part has unexpected command")
            else:
                raise ValueError(
                    f"wrong length: expected 1, 3, 5 or 6, got {len(frame.data)}"
                )

            if scale == 0:
                return cls(None)
            elif offset & 0xFFFF == 0x8000:
                if not (1 <= scale <= 16):
                    raise ValueError("bad scale value for bit")
                return cls(BitRamVarInfo(bit=scale - 1))
            else:
                info_type = SignedRAMVarInfo if scale < 0 else UnsignedRAMVarInfo
                scale_float = float(abs(scale))
                if scale_float >= 0x4000:
                    scale_float = 1 / (0x8000 - scale_float)

                return cls(info_type(scale=scale_float, offset=offset))


@dataclass
class ReadRAMVarCommand(Command):
    ram_vars: list[AnyRAMVar]

    def as_frame(self):
        return MK2Frame(
            b"X",
            bytes([0x30])
            + b"".join(struct.pack("<B", var.value) for var in self.ram_vars),
        )


@register_reply_type
@dataclass
class ReadRAMVarReply(Reply):
    values: list[int]

    frame_type = MK2Frame
    command = b"X"

    @classmethod
    def parse(cls, frame):
        if len(frame.data) > 0 and frame.data[0] in (0x85, 0x90):
            # TODO: parse this as another message so it can be handled in read_ram_vars
            # also, this seems to some with one byte indicating the byte in the
            # message that caused the error (so 1 -> first ram var)
            if frame.data[0] == 0x90:
                raise ValueError("read of unsupported value")

            if len(frame.data) % 2 != 1:
                warnings.warn("odd CommandReadRAMVar reply length")

            values = [
                struct.unpack("<H", frame.data[start : start + 2])[0]
                for start in range(1, len(frame.data), 2)
            ]

            return cls(values)


@dataclass
class GetSettingInfoCommand(Command):
    setting: Setting

    def as_frame(self):
        return MK2Frame(b"X", struct.pack("<BH", 0x35, self.setting.value))


@register_reply_type
@dataclass
class GetSettingInfoReply(Reply):
    info: Optional[SettingInfo]

    frame_type = MK2Frame
    command = b"X"

    @classmethod
    def parse(cls, frame):
        # TODO: or 0x86 without data for not supported?
        if len(frame.data) > 0 and frame.data[0] == 0x89:
            # only support long winmon mode,as otherwise it gets turned into
            # two packets:
            if len(frame.data) >= 12:
                # we can't really tell here which mode we are in, so bail if
                # the data looks sus. this will be static anyway, so if it
                # doesn't cause a problem once it never will
                if frame.data[3:12:3] == b"\x8a\x8b\x8c":
                    raise RuntimeError(
                        "suspected short winmon frames, stopping before "
                        "something bad happens"
                    )

                scale, offset, default, minimum, maximum, access_level = struct.unpack(
                    "<hhHHHB", frame.data[1:12]
                )

                assert scale != 0

                scale = float(scale)
                if scale < 0:
                    scale = 1 / (-scale)
                info = SettingInfo(
                    scale, offset, default, minimum, maximum, access_level=access_level
                )
                return cls(info=info)


@dataclass
class ReadSettingCommand(Command):
    setting: Setting

    def as_frame(self):
        return MK2Frame(b"X", struct.pack("<BH", 0x31, self.setting.value))


@register_reply_type
@dataclass
class ReadSettingReply(Reply):
    raw_value: Optional[int]  # None -> not supported

    frame_type = MK2Frame
    command = b"X"

    @classmethod
    def parse(cls, frame):
        if len(frame.data) > 0 and frame.data[0] == 0x86:
            if len(frame.data) >= 3:
                (raw_value,) = struct.unpack("<H", frame.data[1:3])

                return cls(raw_value)
        elif len(frame.data) > 0 and frame.data[0] == 0x91:
            return cls(None)


@dataclass
class WriteViaID(Command):
    var_or_setting: AnyRAMVar | Setting
    write_ram_only: bool
    value: int

    def __post_init__(self):
        if (
            isinstance(self.var_or_setting, AnyRAMVar)  # type: ignore
            and self.write_ram_only
        ):
            raise ValueError("write_ram_only with RAM var doesn't make sense")

    def as_frame(self):
        if isinstance(self.var_or_setting, AnyRAMVar):  # type: ignore
            is_setting_flag = 0
        elif isinstance(self.var_or_setting, Setting):
            is_setting_flag = 1
        else:
            assert False

        write_ram_flag = 0b10 if self.write_ram_only else 0
        flags = write_ram_flag | is_setting_flag

        data = struct.pack("<BBBH", 0x37, flags, self.var_or_setting.value, self.value)
        return MK2Frame(b"X", data)


class WriteStatus(Enum):
    WRITE_RAM_VAR_OK = 0x87
    WRITE_SETTING_OK = 0x88
    ACCESS_LEVEL_REQUIRED = 0x9B


@register_reply_type
@dataclass
class WriteReply(Reply):
    status: WriteStatus

    frame_type = MK2Frame
    command = b"X"

    @classmethod
    def parse(cls, frame):
        if len(frame.data) > 0 and frame.data[0] in (s.value for s in WriteStatus):
            return cls(WriteStatus(frame.data[0]))
