import struct
import pytest
from .framing import (
    MK2Frame,
    RawFrame,
    Unpacker,
    VEBusFrame,
    calc_checksum,
    format_frame,
)


def test_format_frame():
    assert format_frame(MK2Frame(b"A", bytes([0x01, 0x00]))) == bytes(
        [0x04, 0xFF, ord("A"), 0x01, 0x00, 0xBB]
    )


def get_odd_messages():
    """some messages that use the non-standard checksum"""
    messages = """
    05 38 04 6C 00 00 0A
    05 38 04 6E 00 00 E8
    05 38 05 00 00 00 3B
    05 3F 00 11 00 00 A7
    05 3F C0 72 00 00 70
    06 21 00 00 00 00 00 C7
    06 21 FF FF FF FF 80 4D
    06 21 FF FF FF FF 83 4A
    07 21 00 00 00 00 01 00 C5
    """
    return [bytes.fromhex(line) for line in messages.strip().split("\n")]


@pytest.mark.parametrize("message", get_odd_messages())
def test_format_odd_frame(message):
    assert format_frame(VEBusFrame(message[1], message[2:-1])) == message


def format_frame_with_led(frame: RawFrame, led_frame: MK2Frame) -> bytes:
    """format a frame with appended LED data"""
    data = frame.as_bytes()
    led_data = led_frame.data
    len_byte = 0x80 | (len(data) + len(led_data))
    without_checksum = bytes([len_byte]) + data + led_data
    return without_checksum + struct.pack("<B", calc_checksum(without_checksum))


def test_unpacker():
    frames = [
        MK2Frame(b"A", bytes([0x01, 0x00])),
        MK2Frame(b"B", bytes([0x03, 0x02])),
        VEBusFrame(0x20, bytes([0x05, 0x04])),
        VEBusFrame(0x21, bytes([0xFF, 0xFF, 0xFF, 0xFF, 0x80])),
    ]
    messags_bytes = b"".join(map(format_frame, frames))

    # add a frame with extra LED state appended
    with_led_frame = MK2Frame(b"C", bytes([0x05, 0x04]))
    led_frame = MK2Frame(b"L", bytes([0x7, 0x06]))
    frames += [with_led_frame, led_frame]
    messags_bytes += format_frame_with_led(with_led_frame, led_frame)

    unpacked: list[RawFrame] = []
    unpacker = Unpacker(unpacked.append)

    for b in messags_bytes:
        unpacker.on_recv(bytes([b]))

    assert unpacked == frames
