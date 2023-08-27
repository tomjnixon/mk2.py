import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from .connection import VEBusConnection
from .frames.f_commands import ACInfo, DCInfo, FCommandType
from .ram_var import AnyRAMVar, RAMVar, RAMVarInfo
from .setting import Setting, SettingFlags, SettingInfo


class VEBusSession:
    """communication session with a VE.Bus device

    compared to connection, this initialised the connection, scales ram vars
    and settings, and prevents concurrent access

    this must be used inside the run context manager; with connection, this
    looks like:

        connection = VEBusConnection(...)
        session = VEBusSession(connection, ...)
        with connection.run(), session.run():
            # use session here
    """

    def __init__(self, connection: VEBusConnection, address: int = 0):
        self.connection_lock = asyncio.Semaphore(0)  # released after initialisation

        self.connection = connection
        self.address = address

        self.ram_var_info: dict[AnyRAMVar, Optional[RAMVarInfo]] = {}

        self.setting_info: dict[Setting, SettingInfo] = {}

    async def _task(self):
        from .frames.switch import (
            StateCommand2,
            StateEEPROMFlags,
            StateFlags,
            StateFlagsExt0,
            SwitchState,
        )

        # connection lock already acquired
        await self.connection.write_address(self.address)

        # switch to long winmon frames (required, see comment in w_commands.py)
        # TODO: get (and store) mode, limit etc. so that we don't change the
        # state when we don't mean to
        await self.connection.send_command(
            StateCommand2(
                switch_state=SwitchState.ON,
                limit=None,
                flags=StateFlags.NO_SEND_PANEL_STATE,
                flags_ext_0=StateFlagsExt0(0),
                eeprom_flags=StateEEPROMFlags(0),
            )
        )

        self.connection_lock.release()

    @asynccontextmanager
    async def run(self):
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._task())
            yield

    async def _get_optional_ram_var_info_with_lock(
        self, ram_var: AnyRAMVar
    ) -> Optional[RAMVarInfo]:
        if ram_var not in self.ram_var_info:
            info = await self.connection.get_ram_var_info(ram_var)
            self.ram_var_info[ram_var] = info

        return self.ram_var_info[ram_var]

    async def _get_ram_var_info_with_lock(self, ram_var: AnyRAMVar) -> RAMVarInfo:
        info = await self._get_optional_ram_var_info_with_lock(ram_var)
        if info is None:
            raise ValueError("trying to access unsupported ram var")
        return info

    async def get_ram_var_info(self, ram_var: AnyRAMVar) -> Optional[RAMVarInfo]:
        # avoid locking in common case
        if ram_var in self.ram_var_info:
            return self.ram_var_info[ram_var]

        async with self.connection_lock:
            return await self._get_optional_ram_var_info_with_lock(ram_var)

    async def read_ram_vars_unscaled(self, ram_vars: list[AnyRAMVar]) -> list[int]:
        async with self.connection_lock:
            return await self.connection.read_ram_vars_unscaled(ram_vars)

    async def read_ram_vars(self, ram_vars: list[AnyRAMVar]) -> list[float | bool]:
        async with self.connection_lock:
            infos = [await self._get_ram_var_info_with_lock(var) for var in ram_vars]

            unscaled = await self.connection.read_ram_vars_unscaled(ram_vars)

            assert len(infos) == len(unscaled)
            return [i.from_raw_value(v) for i, v in zip(infos, unscaled)]

    async def write_ram_var_unscaled(self, ram_var: AnyRAMVar, raw_value: int):
        async with self.connection_lock:
            await self.connection.write_ram_var_unscaled(ram_var, raw_value)

    async def write_ram_var(self, ram_var: AnyRAMVar, value: float):
        async with self.connection_lock:
            info = await self._get_ram_var_info_with_lock(ram_var)
            scaled = info.to_raw_value(value)
            await self.connection.write_ram_var_unscaled(ram_var, scaled)

    async def _scale_with_lock(self, var: RAMVar, raw_value: int) -> float:
        info = await self._get_ram_var_info_with_lock(var)
        return info.from_raw_value(raw_value)

    async def get_dc_info(self):
        async with self.connection_lock:
            unscaled = await self.connection.get_dc_info_unscaled()

            scale = self._scale_with_lock
            return DCInfo(
                voltage=await scale(RAMVar.U_BAT, unscaled.voltage),
                inverter_current=await scale(RAMVar.I_BAT, unscaled.inverter_current),
                charger_current=await scale(RAMVar.I_BAT, unscaled.charger_current),
                inverter_period=await scale(
                    RAMVar.INVERTER_PERIOD, unscaled.inverter_period
                ),
            )

    async def get_ac_info(self, command: FCommandType = FCommandType.L1_INFO):
        async with self.connection_lock:
            unscaled = await self.connection.get_ac_info_unscaled(command=command)

            scale = self._scale_with_lock
            return ACInfo(
                phase=unscaled.phase,
                num_phases=unscaled.num_phases,
                state=unscaled.state,
                mains_voltage=await scale(RAMVar.U_MAINS_RMS, unscaled.mains_voltage),
                mains_current=await scale(RAMVar.I_MAINS_RMS, unscaled.mains_current),
                inverter_voltage=await scale(
                    RAMVar.U_INVERTER_RMS, unscaled.inverter_voltage
                ),
                inverter_current=await scale(
                    RAMVar.I_INVERTER_RMS, unscaled.inverter_current
                ),
                mains_period=await scale(RAMVar.MAINS_PERIOD, unscaled.mains_period),
            )

    async def get_setting_info(self, setting: Setting):
        if setting not in self.setting_info:
            async with self.connection_lock:
                info = await self.connection.get_setting_info(setting)
            self.setting_info[setting] = info

        return self.setting_info[setting]

    async def read_setting_unscaled(self, setting: Setting):
        async with self.connection_lock:
            return await self.connection.read_setting_unscaled(setting)

    async def read_setting(self, setting: Setting):
        info = await self.get_setting_info(setting)
        raw = await self.read_setting_unscaled(setting)
        return info.from_raw_value(raw)

    async def write_setting_unscaled(
        self, setting: Setting, value: int, write_ram_only=False
    ):
        async with self.connection_lock:
            await self.connection.write_setting_unscaled(
                setting, value, write_ram_only=write_ram_only
            )

    async def write_setting(self, setting: Setting, value: int, write_ram_only=False):
        info = await self.get_setting_info(setting)
        raw = info.to_raw_value(value)
        await self.write_setting_unscaled(setting, raw, write_ram_only=write_ram_only)

    async def read_setting_flags(self):
        async with self.connection_lock:
            return await self.connection.read_setting_flags()

    async def write_setting_flags(self, flags: SettingFlags, write_ram_only=False):
        async with self.connection_lock:
            return await self.connection.write_setting_flags(
                flags, write_ram_only=write_ram_only
            )
