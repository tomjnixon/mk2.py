# mk2.py

A python and asyncio implementation of the Victron VE.Bus / MK2 protocol, for
interacting with MultiPlus inverter/chargers (and other products such as
Quattro and Phoenix) using the MK2/MK3 USB-VE.Bus converter.

## Disclaimer

This is (obviously) not an official Victron product -- it's not endorsed by
them in any way, and if you use it, it's at your own risk (see the license).

In fact, I don't even endorse it. You should probably use the official
software, either through something like the Cerbo GX, the Venus OS raspberry pi
image, or using the `mk2-dbus` program directly (see
https://github.com/iuriaranda/venus-docker).

## Overview

This software implements a sizable chunk of the MK2 protocol as described in
[the specification], primarily allowing reading and writing of RAM variables
and settings with correct scaling, as well as some of the special frames.

[the specification]: https://www.victronenergy.com/upload/documents/Technical-Information-Interfacing-with-VE-Bus-products-MK2-Protocol-3-14.pdf

The parts that are implemented should be relatively complete, conforming to the
specification where possible, with some documented divergences to make it work
in the real world.

In addition to the spec, some undocumented settings and behaviours are based on
analysis of traces from VE.Configure.

While it will probably work with other devices, it has only been tested with a
MultiPlus 12/500. Please open issues if you have them.

## Structure

The components are as follows:

- [framing.py](mk2/framing.py) turns raw frames into streams of bytes, and the
  other way around

- [frames/](mk2/frames/) has a dataclass for each known frame type, with
  serialisation for commands, and parsing for replies

- [ram_var.py](mk2/ram_var.py) and [setting.py](mk2/setting.py) have enums of
  known RAM variables and settings, and classes containing 'info' about them,
  which encode their data types and scale factors

- [connection.py](mk2/connection.py) contains the `VEBusConnection` class
  for sending and receiving frames over a connection, along with wrapper
  methods which send commands and receive the appropriate replies to access
  various functionality

- [session.py](mk2/session.py) contains the `VEBusSession` class which has
  high-level methods to get/set variables and settings, with automatic scaling,
  connection setup, and locking to prevent concurrent access. This is what most
  users should interact with

## Examples

Examples can be found in [mk2/examples](mk2/examples).

### Monitor

A simple monitor can be ran with:

```sh
python -m mk2.examples.monitor -t /dev/ttyUSB0
```
### Write

A tool for writing RAM vars, settings and flags:

```
python -m mk2.examples.write --help
usage: write.py [-h] --tty TTY [--list] [--log-level LOG_LEVEL] [--write-ram-var ram_var value]
                [--write-setting setting value] [--write-setting-ram-only setting value] [--set-flag flag]
                [--clear-flag flag] [--set-flag-ram-only flag] [--clear-flag-ram-only flag]

write to RAM vars, settings and flags

options:
  -h, --help            show this help message and exit
  --tty TTY, -t TTY     serial port to use
  --list                list all RAM vars, settings and flags with their values and other information
  --log-level LOG_LEVEL, -l LOG_LEVEL
  --write-ram-var ram_var value
                        write a RAM var with a given name and value (either a number or true/false)
  --write-setting setting value
                        write a setting with a given name and value (a number)
  --write-setting-ram-only setting value
                        write a setting to RAM with a given name and value (a number). settings written with
                        this will take effect, but will not appear when read (e.g. with --list), and are not
                        saved
  --set-flag flag       set/enable a flag with a given name
  --clear-flag flag     clear/disable a flag with a given name
  --set-flag-ram-only flag
                        set/enable a flag in RAM only with a given name (see --write-setting-ram-only)
  --clear-flag-ram-only flag
                        clear/disable a flag in RAM only with a given name (see --write-setting-ram-only)

```

Use `--list` to show available RAM vars, settings and flags (output truncated):

```
python -m mk2.examples.write -t /dev/ttyUSB0 --list
RAM vars:
    CHARGE_STATE: unsigned value=0.49 scale=0.005 offset=0
    ...
settings (note that RAM-only changes will not be reflected here):
    VS_USAGE: value=3 default=1 min=0 max=6 scale=1 offset=0
    ...
flags:
    DISABLE_CHARGE: value=False
    ...
```

For example, I use the 'dedicated ignore AC input' virtual switch setting
(which must be configured using the official tools first!) to store energy
without using ESS mode, and can put this into different modes with these
commands:

Prefer to run from battery:

```sh
python -m mk2.examples.write -t /dev/ttyUSB0 --write-setting-ram-only VS_USAGE 3 --set-flag-ram-only DISABLE_CHARGE
```

Prefer to run from AC:

```sh
python -m mk2.examples.write -t /dev/ttyUSB0 --write-setting-ram-only VS_USAGE 0 --set-flag-ram-only DISABLE_CHARGE
```

Charge:

```sh
python -m mk2.examples.write -t /dev/ttyUSB0 --write-setting-ram-only VS_USAGE 0 --clear-flag-ram-only DISABLE_CHARGE
```

## Install

Python 3.11 is required; install it with:

```sh
python -m pip install git+https://github.com/tomjnixon/mk2.py.git
```

Alternatively there is a nix build:

For development:
```sh
nix develop .
python -m mk2.examples.monitor
```

Or to run scripts, build a python environment with this package installed:

```sh
nix build .#env
./result/bin/python mk2/examples/monitor.py
```

## License

    Copyright (C) 2023 Thomas Nixon

    This program is free software: you can redistribute it and/or modify
    it under the terms of version 3  of the GNU General Public License as
    published by the Free Software Foundation.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    See LICENSE.

I am open to granting license exceptions if you cannot use GPL3 code in your
project -- either for free as part of other open source projects, or under
commercial terms. My email can be found in commit headers.
