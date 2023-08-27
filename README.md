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

A simple monitor can be ran with:

```sh
python -m mk2.examples.monitor -t /dev/ttyUSB0
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
