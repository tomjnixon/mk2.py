from .framing import MK2Frame, VEBusFrame, format_frame
import pytest


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
    return [bytes.fromhex(l) for l in messages.strip().split("\n")]


@pytest.mark.parametrize("message", get_odd_messages())
def test_format_odd_frame(message):
    assert format_frame(VEBusFrame(message[1], message[2:-1])) == message
