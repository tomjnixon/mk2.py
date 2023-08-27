import asyncio
from contextlib import asynccontextmanager, contextmanager
from dataclasses import replace
from typing import Callable
from .frames.f_commands import FCommandType
from .frames.types import Command, ReplyParser
from .framing import RawFrame, Unpacker, format_frame
from .ram_var import AnyRAMVar, RAMVar
from .setting import Setting, SettingFlags


class VEBusConnection:
    """medium-level interface which sending/receiving commands/replies, but
    doesn't hold any state, prevent concurrent access, or initialise the
    connection

    you probably want VEBusSession instead

    this must be used inside the run context manager:

        conn = VEBusConnection(...)
        with conn.run():
            # use conn here
    """

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer

        self.unpacker = Unpacker(self._on_frame)
        self.reply_parser = ReplyParser()

        self.reply_callbacks: list[Callable[[RawFrame], None]] = []

    @asynccontextmanager
    async def run(self):
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._read_task())
            yield

    async def _read_task(self):
        while True:
            buf = await self.reader.read(128)
            if not buf:
                break
            self.unpacker.on_recv(buf)

    def _on_frame(self, frame):
        try:
            reply = self.reply_parser.parse_frame(frame)
        except Exception as e:
            raise RuntimeError(f"error while parsing frame {frame!r}") from e
        if reply is not None:
            print("reply", reply)
            for cb in self.reply_callbacks:
                cb(reply)
        else:
            print("unhandled frame", frame)

    async def send_frame(self, frame: RawFrame):
        print("send frame", frame)
        self.writer.write(format_frame(frame))
        await self.writer.drain()

    async def send_command(self, command: Command):
        await self.send_frame(command.as_frame())

    @contextmanager
    def with_reply_cb(self, reply_cb):
        """register reply_cb to recieve replies inside a context manager"""
        self.reply_callbacks.append(reply_cb)

        yield

        for i, cb in enumerate(self.reply_callbacks):
            if cb is reply_cb:
                break
        else:
            assert False, "could not find cb"

        self.reply_callbacks.pop(i)

    async def wait_for_reply(self, match_reply, timeout=0.5):
        """wait for a reply matching match_reply, or raise TimeoutError after
        timeout seconds
        """
        f = asyncio.Future()

        def reply_cb(reply):
            if match_reply(reply):
                f.set_result(reply)

        with self.with_reply_cb(reply_cb):
            async with asyncio.timeout(timeout):
                return await f

    async def write_address(self, address):
        from .frames.management import WriteAddressCommand, WriteAddressReply

        await self.send_command(WriteAddressCommand(address))
        reply = await self.wait_for_reply(
            lambda r: isinstance(r, WriteAddressReply), timeout=2
        )
        if reply.address != address:
            raise ValueError("WriteAddressCommand returned wrong address")

    async def send_reset(self):
        from .frames.management import ResetCommand

        await self.send_command(ResetCommand())

    async def get_dc_info_unscaled(self):
        from .frames.f_commands import DCInfoReply, FCommand

        await self.send_command(FCommand(FCommandType.DC_INFO))
        return await self.wait_for_reply(lambda r: isinstance(r, DCInfoReply))

    async def get_ac_info_unscaled(self, command: FCommandType = FCommandType.L1_INFO):
        from .frames.f_commands import ACInfoReply, FCommand

        await self.send_command(FCommand(command))
        return await self.wait_for_reply(lambda r: isinstance(r, ACInfoReply))

    async def get_ram_var_info(self, ram_var: AnyRAMVar):
        from .frames.w_commands import GetRAMVarInfoCommand, GetRAMVarInfoReply

        await self.send_command(GetRAMVarInfoCommand(ram_var))
        reply = await self.wait_for_reply(lambda r: isinstance(r, GetRAMVarInfoReply))
        info = reply.info

        # fix up variables with extra scales
        if ram_var in (RAMVar.INVERTER_PERIOD, RAMVar.MAINS_PERIOD):
            info = replace(info, scale=info.scale / 10.0)

        return info

    async def read_ram_vars_unscaled(self, ram_vars: list[AnyRAMVar]):
        from .frames.w_commands import ReadRAMVarCommand, ReadRAMVarReply

        values = []
        batch_size = 6
        for start in range(0, len(ram_vars), batch_size):
            ram_vars_slice = ram_vars[start : start + batch_size]
            await self.send_command(ReadRAMVarCommand(ram_vars_slice))
            reply = await self.wait_for_reply(lambda r: isinstance(r, ReadRAMVarReply))

            if len(reply.values) < len(ram_vars_slice):
                raise RuntimeError("too few vars returned")
            values.extend(reply.values[: len(ram_vars_slice)])

        return values

    async def write_ram_var_unscaled(self, var: AnyRAMVar, raw_value: int):
        from .frames.w_commands import (
            UnknownCommandReply,
            WriteReply,
            WriteStatus,
            WriteViaID,
        )

        await self.send_command(
            WriteViaID(var_or_setting=var, value=raw_value, write_ram_only=False)
        )
        reply = await self.wait_for_reply(
            lambda r: isinstance(r, (WriteReply, UnknownCommandReply))
        )
        match reply:
            case WriteReply(status=WriteStatus.WRITE_RAM_VAR_OK):
                return
            case WriteReply(status=WriteStatus.ACCESS_LEVEL_REQUIRED):
                raise RuntimeError("access level required")
            case WriteReply(status=WriteStatus.WRITE_SETTING_OK):
                raise RuntimeError("sent RAM var write, got setting write reply")
            case UnknownCommandReply():
                raise ValueError(f"can't write to {var} (probably)")
            case _:
                assert False

    async def get_setting_info(self, setting: Setting):
        from .frames.w_commands import GetSettingInfoCommand, GetSettingInfoReply

        await self.send_command(GetSettingInfoCommand(setting))
        reply = await self.wait_for_reply(lambda r: isinstance(r, GetSettingInfoReply))
        return reply.info

    async def read_setting_unscaled(self, setting: Setting):
        from .frames.w_commands import ReadSettingCommand, ReadSettingReply

        await self.send_command(ReadSettingCommand(setting))
        reply = await self.wait_for_reply(lambda r: isinstance(r, ReadSettingReply))
        return reply.raw_value

    async def write_setting_unscaled(
        self, setting: Setting, raw_value: int, write_ram_only=False
    ):
        from .frames.w_commands import (
            UnknownCommandReply,
            WriteReply,
            WriteStatus,
            WriteViaID,
        )

        await self.send_command(
            WriteViaID(
                var_or_setting=setting, write_ram_only=write_ram_only, value=raw_value
            )
        )
        reply = await self.wait_for_reply(
            lambda r: isinstance(r, (WriteReply, UnknownCommandReply))
        )
        match reply:
            case WriteReply(status=WriteStatus.WRITE_SETTING_OK):
                return
            case WriteReply(status=WriteStatus.ACCESS_LEVEL_REQUIRED):
                raise RuntimeError("access level required")
            case WriteReply(status=WriteStatus.WRITE_RAM_VAR_OK):
                raise RuntimeError("sent setting write, got RAM var write reply")
            case UnknownCommandReply():
                raise ValueError(f"can't write to {setting} (probably)")
            case _:
                assert False

    async def read_setting_flags(self):
        flags0 = await self.read_setting_unscaled(Setting.FLAGS0)
        flags1 = await self.read_setting_unscaled(Setting.FLAGS1)
        return SettingFlags((flags1 << 16) | flags0)

    async def write_setting_flags(self, flags: SettingFlags, write_ram_only=False):
        if SettingFlags.DISABLE_WAVE_CHECK in flags:
            flags &= ~SettingFlags.DISABLE_WAVE_CHECK_INVERTED
        else:
            flags |= SettingFlags.DISABLE_WAVE_CHECK_INVERTED
        assert (SettingFlags.DISABLE_WAVE_CHECK in flags) != (
            SettingFlags.DISABLE_WAVE_CHECK_INVERTED in flags
        )

        flags0 = flags.value & 0xFFFF
        flags1 = (flags.value >> 16) & 0xFFFF

        await self.write_setting_unscaled(
            Setting.FLAGS0, flags0, write_ram_only=write_ram_only
        )
        await self.write_setting_unscaled(
            Setting.FLAGS1, flags1, write_ram_only=write_ram_only
        )
