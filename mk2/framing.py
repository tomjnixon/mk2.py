import logging
import struct
from dataclasses import dataclass
from typing import Optional


def calc_checksum(message_without_checksum: bytes):
    if message_without_checksum[1] in (0x21, 0x3F, 0x38, 0x3D):
        # we don't use frames like this, but it's useful to be able to parse
        # them for monitoring/re.
        s = sum(message_without_checksum) + sum(
            message_without_checksum[i] >> 4 | message_without_checksum[i] << 4
            for i in range(1, min(7, len(message_without_checksum)), 2)
        )
        return -s & 0xFF
    else:
        return -sum(message_without_checksum) & 0xFF


class RawFrame:
    def as_bytes(self) -> bytes:
        """get the data specific to this frame type, without length or checksum"""
        raise NotImplementedError()


@dataclass
class MK2Frame(RawFrame):
    command: bytes  # one byte
    data: bytes

    def as_bytes(self):
        return struct.pack("Bc", 0xFF, self.command) + self.data


@dataclass
class VEBusFrame(RawFrame):
    frame_type: int
    data: bytes

    def as_bytes(self):
        return bytes([self.frame_type]) + self.data


def format_frame(frame: RawFrame) -> bytes:
    data = frame.as_bytes()
    without_checksum = bytes([len(data)]) + data
    return without_checksum + struct.pack("<B", calc_checksum(without_checksum))


class Unpacker:
    """turn a stream of bytes (in arbitrary chunks) into a stream of frames

    this uses the frame types as a sync word, so known types must be passed to
    the constructor
    """

    def __init__(
        self,
        on_frame,
        frame_types=(0xFF, 0x20, 0x21, 0x41, 0x3C, 0x3F),
        logger: Optional[logging.Logger] = None,
    ):
        self.buffer = bytearray()
        self.on_frame = on_frame
        self.frame_types = frame_types

        self.logger = logger if logger is not None else logging.getLogger(__name__)

    def on_recv(self, recvd: bytes):
        self.buffer.extend(recvd)

        # valid frames have:
        # - byte 0: length (excluding length and checksum), must be >= 2
        # - byte 1: frame type (used as sync word)
        # - byte 2: command
        # - byte 3-n-1: data
        # - byte n: checksum

        # break: not enough data
        # continue: try again after advancing
        while True:
            if len(self.buffer) < 2:
                break
            frame_type = self.buffer[1]
            if frame_type not in self.frame_types:
                self.to_next_sync()
                continue

            length = self.buffer[0]

            has_led_state = bool(length & 0x80)
            length = length & 0x7F

            if length < 2:
                self.to_next_sync()
                continue

            if len(self.buffer) < length + 2:
                break

            checksum_recv = self.buffer[length + 1]
            checksum_calc = calc_checksum(self.buffer[: length + 1])
            if checksum_calc != checksum_recv:
                self.to_next_sync()
                continue

            data = bytes(self.buffer[2 : length + 1])
            if has_led_state:
                data, led_data = data[:-2], data[-2:]

            frame: RawFrame
            if frame_type == 0xFF:
                frame = MK2Frame(bytes([data[0]]), bytes(data[1:]))
            else:
                frame = VEBusFrame(frame_type, bytes(data))
            self.on_frame(frame)

            if has_led_state:
                self.on_frame(MK2Frame(b"L", led_data))

            self.buffer = self.buffer[length + 2 :]
            continue

    def to_next_sync(self):
        # TODO: warn dropped properly
        pos = len(self.buffer)
        for i in range(2, len(self.buffer)):
            if self.buffer[i] in self.frame_types:
                pos = i
                break

        self.logger.warning("dropped bytes: %s", self.buffer[: pos - 1].hex(" "))
        self.buffer = self.buffer[pos - 1 :]
