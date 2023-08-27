from typing import Optional
from ..framing import MK2Frame, RawFrame, VEBusFrame


class Command:
    def as_frame(self) -> RawFrame:
        raise NotImplementedError()


class Reply:
    """replies should subclass this, and use the register_reply_type decorator

    frames are parsed by ReplyParser, which calls .parse(frame) on all Reply
    subclasses which could match, and returns the first non-None result. a
    subclass might match if its `frame_type` attribute matched the frame type,
    and `command` for `MK2Frame` or `vebus_frame_type` (for `VEBusFrame`)
    matches the corresponding attribute in the frame.
    """

    @classmethod
    def parse(cls, frame: RawFrame) -> Optional["Reply"]:
        raise NotImplementedError()


all_reply_types = []


def register_reply_type(cls):
    all_reply_types.append(cls)
    return cls


class ReplyParser:
    """parse reply frames; see Reply for requirements"""

    def __init__(self, reply_types=all_reply_types):
        self.reply_types = reply_types

    def parse_frame(self, frame: RawFrame) -> Optional[Reply]:
        # TODO: this could be a lot more efficient, but it also doesn't need to be...

        for t in self.reply_types:
            if not isinstance(frame, t.frame_type):
                continue

            if issubclass(t.frame_type, MK2Frame):
                if t.command != frame.command:
                    continue
            elif issubclass(t.frame_type, VEBusFrame):
                if t.vebus_frame_type != frame.frame_type:
                    continue

            parsed = t.parse(frame)
            if parsed is not None:
                return parsed

        return None
