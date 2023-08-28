import asyncio
import logging
import serial_asyncio
from mk2 import RAMVar, VEBusConnection, VEBusSession


def parse_args():
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("--tty", "-t", required=True)

    parser.add_argument("--log-level", "-l", default="WARNING")

    return parser.parse_args()


def fmt_var(var, value):
    value_str = f"{value:.3g}".ljust(8)
    return f"{var.name.lower()}: {value_str}"


async def main(args):
    logging.basicConfig(level=args.log_level)

    reader, writer = await serial_asyncio.open_serial_connection(
        url=args.tty, baudrate=2400
    )
    interface = VEBusConnection(reader, writer)
    session = VEBusSession(interface)
    async with interface.run(), session.run():
        ram_vars = [
            RAMVar.INVERTER_POWER,
            RAMVar.INPUT_POWER,
            RAMVar.OUTPUT_POWER,
            RAMVar.U_MAINS_RMS,
            RAMVar.U_BAT,
            RAMVar.I_BAT,
        ]

        while True:
            values = await session.read_ram_vars(ram_vars)

            line = " ".join(fmt_var(var, value) for var, value in zip(ram_vars, values))
            print(line)  # noqa

            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
