import asyncio
import logging
from textwrap import dedent
import serial_asyncio
from mk2 import (
    AnyRAMVar,
    OtherRAMVar,
    RAMVar,
    Setting,
    SettingFlags,
    VEBusConnection,
    VEBusSession,
)
from mk2.ram_var import BitRamVarInfo, SignedRAMVarInfo, UnsignedRAMVarInfo
from mk2.setting import SettingInfo

# parse vars/settings/flags and their values


def parse_ram_var(var: str) -> AnyRAMVar:
    if var.upper() in RAMVar.__members__:
        return RAMVar.__members__[var.upper()]
    else:
        try:
            var_num = int(var)
        except ValueError:
            raise ValueError("ramvar should be a RAM var name or int")
        return OtherRAMVar(var_num)


def parse_ram_var_value(value: str) -> bool | float:
    if value.lower() == "true":
        return True
    elif value.lower() == "false":
        return True
    else:
        return float(value)


def parse_setting(setting: str) -> Setting:
    if setting.upper() in Setting.__members__:
        return Setting.__members__[setting.upper()]
    else:
        raise ValueError("setting should be a setting name")


def parse_setting_value(value: str) -> float:
    return float(value)


def parse_setting_flag(flag: str) -> SettingFlags:
    if flag.upper() in SettingFlags.__members__:
        return SettingFlags.__members__[flag.upper()]
    else:
        raise ValueError("flag should be a flag name")


# list vars/settings/flags


async def list_all(session: VEBusSession):
    await list_ram_vars(session)
    await list_settings(session)
    await list_flags(session)


async def list_ram_vars(session: VEBusSession):
    print("RAM vars:")
    for var in RAMVar:
        info = await session.get_ram_var_info(var)
        if info is None:
            value = None
        else:
            [value] = await session.read_ram_vars([var])

        match info:
            case None:
                info_str = "unsupported"
            case SignedRAMVarInfo(scale=scale, offset=offset):
                info_str = f"signed value={value:.3g} scale={scale:.3g} offset={offset}"
            case UnsignedRAMVarInfo(scale=scale, offset=offset):
                info_str = (
                    f"unsigned value={value:.3g} scale={scale:.3g} offset={offset}"
                )
            case BitRamVarInfo(bit=bit):
                info_str = f"bit value={value} bit={bit}"
            case _:
                assert False
        print(f"    {var.name}: {info_str}")


async def list_settings(session: VEBusSession):
    print("settings (note that RAM-only changes will not be reflected here):")
    for setting in Setting:
        if setting in (Setting.FLAGS0, Setting.FLAGS1):
            continue
        info = await session.get_setting_info(setting)
        value = (await session.read_setting(setting)) if info is not None else None

        match info:
            case None:
                info_str = "unsupported"
            case SettingInfo(
                scale=scale,
                offset=offset,
                default=default_unscaled,
                minimum=minimum_unscaled,
                maximum=maximum_unscaled,
            ):
                minimum = info.from_raw_value(minimum_unscaled)
                maximum = info.from_raw_value(maximum_unscaled)
                default = info.from_raw_value(default_unscaled)
                info_str = (
                    f"value={value:.3g} default={default:.3g} "
                    f"min={minimum:.3g} max={maximum:.3g} "
                    f"scale={scale:.3g} offset={offset:.3g}"
                )
            case _:
                assert False
        print(f"    {setting.name}: {info_str}")


async def list_flags(session: VEBusSession):
    print("flags:")
    flags = await session.read_setting_flags()

    for flag in SettingFlags:
        print(f"    {flag.name}: value={bool(flags & flag)}")


def build_ArgumentParser():
    import argparse

    parser = argparse.ArgumentParser(
        description="write to RAM vars, settings and flags"
    )

    parser.add_argument("--tty", "-t", required=True, help="serial port to use")

    parser.add_argument(
        "--list",
        action="store_true",
        help="list all RAM vars, settings and flags with their values and other information",
    )

    parser.add_argument("--log-level", "-l", default="WARNING")

    parser.add_argument(
        "--accept-disclaimer", "-a", action="store_true", help=argparse.SUPPRESS
    )

    parser.add_argument(
        "--write-ram-var",
        nargs=2,
        action="append",
        default=[],
        metavar=("ram_var", "value"),
        help="write a RAM var with a given name and value (either a number or true/false)",
    )
    parser.add_argument(
        "--write-setting",
        nargs=2,
        action="append",
        default=[],
        metavar=("setting", "value"),
        help="write a setting with a given name and value (a number)",
    )
    parser.add_argument(
        "--write-setting-ram-only",
        nargs=2,
        action="append",
        default=[],
        metavar=("setting", "value"),
        help="""write a setting to RAM with a given name and value (a number).
                settings written with this will take effect, but will not appear
                when read (e.g. with --list), and are not saved""",
    )
    parser.add_argument(
        "--set-flag",
        action="append",
        default=[],
        metavar="flag",
        help="set/enable a flag with a given name",
    )
    parser.add_argument(
        "--clear-flag",
        action="append",
        default=[],
        metavar="flag",
        help="clear/disable a flag with a given name",
    )
    parser.add_argument(
        "--set-flag-ram-only",
        action="append",
        default=[],
        metavar="flag",
        help="set/enable a flag in RAM only with a given name (see --write-setting-ram-only)",
    )
    parser.add_argument(
        "--clear-flag-ram-only",
        action="append",
        default=[],
        metavar="flag",
        help="clear/disable a flag in RAM only with a given name (see --write-setting-ram-only)",
    )

    return parser


async def main(parser, args):
    would_write = (
        args.write_ram_var
        or args.write_setting
        or args.write_setting_ram_only
        or args.set_flag
        or args.clear_flag
        or args.set_flag_ram_only
        or args.clear_flag_ram_only
    )
    if would_write and not args.accept_disclaimer:
        disclaimer = dedent(
            """
            mk2.py write example

            This program allows writing to ram variables and settings; the official
            documentation is not always clear, and does not document some known
            settings and variables.

            Like any use of this program, this is used entirely at your own risk, see
            LICENSE and README for details.

            Pass --accept-disclaimer to acknowledge this.
            """
        ).lstrip()
        parser.exit(status=1, message=disclaimer)

    logging.basicConfig(level=args.log_level)

    reader, writer = await serial_asyncio.open_serial_connection(
        url=args.tty, baudrate=2400
    )
    interface = VEBusConnection(reader, writer)
    session = VEBusSession(interface)
    async with interface.run(), session.run():
        if args.list:
            await list_all(session)

        for ram_var, value in args.write_ram_var:
            await session.write_ram_var(
                parse_ram_var(ram_var), parse_ram_var_value(value)
            )

        for setting, value in args.write_setting:
            await session.write_setting(
                parse_setting(setting), parse_setting_value(value)
            )

        for setting, value in args.write_setting_ram_only:
            await session.write_setting(
                parse_setting(setting), parse_setting_value(value), write_ram_only=True
            )

        if (
            args.set_flag
            or args.clear_flag
            or args.set_flag_ram_only
            or args.clear_flag_ram_only
        ):
            flags = await session.read_setting_flags()

            if args.set_flag or args.clear_flag:
                for flag in args.set_flag:
                    flags |= parse_setting_flag(flag)
                for flag in args.clear_flag:
                    flags &= ~parse_setting_flag(flag)
                await session.write_setting_flags(flags)

            if args.set_flag_ram_only or args.clear_flag_ram_only:
                for flag in args.set_flag_ram_only:
                    flags |= parse_setting_flag(flag)
                for flag in args.clear_flag_ram_only:
                    flags &= ~parse_setting_flag(flag)
                await session.write_setting_flags(flags, write_ram_only=True)


if __name__ == "__main__":
    parser = build_ArgumentParser()
    asyncio.run(main(parser, parser.parse_args()))
