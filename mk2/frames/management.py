import struct
from dataclasses import dataclass
from typing import Optional
from ..framing import MK2Frame
from .types import Command, Reply, register_reply_type


@dataclass
class WriteAddressCommand(Command):
    address: int

    def as_frame(self):
        return MK2Frame(b"A", bytes([1, self.address]))


@register_reply_type
@dataclass
class WriteAddressReply(Reply):
    address: int

    frame_type = MK2Frame
    command = b"A"

    @classmethod
    def parse(cls, frame):
        if len(frame.data) not in (2, 3):
            raise ValueError("unexpected length")
        if len(frame.data) == 3 and frame.data[2] != 0:
            raise ValueError("unexpected padding")
        if frame.data[0] == 1:
            return cls(frame.data[1])


@register_reply_type
@dataclass
class VersionReply(Reply):
    """not really a reply, sent every 1.5 seconds"""

    version: int
    mode: bytes
    address: Optional[int] = None

    frame_type = MK2Frame
    command = b"V"

    @classmethod
    def parse(cls, frame):
        if len(frame.data) == 5:
            version, mode = struct.unpack("<Ic", frame.data)
            if mode == b"W" or mode == b"B":
                return cls(version, mode)
            else:
                return cls(version, b"B", ord(mode))
