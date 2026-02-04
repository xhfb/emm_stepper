"""Emm固件步进电机命令类.

基于ZDT_X42S第二代闭环步进电机用户手册V1.0.3_251224。
"""

import logging
from abc import ABC, abstractmethod
from time import sleep, time
from typing import Optional, TypeVar, Generic, Any

from .configs import (
    Code,
    Protocol,
    StatusCode,
    ChecksumMode,
    Address,
    SyncFlag,
    StoreFlag,
    Direction,
    EnableFlag,
    HomingMode,
    MotionMode,
    add_checksum,
    calculate_checksum,
    SystemConstants,
)
from .parameters import (
    DeviceParams,
    JogParams,
    PositionParams,
    HomingParams,
    VersionParams,
    MotorRHParams,
    PIDParams,
    HomingStatus,
    MotorStatus,
    SystemStatusParams,
    ConfigParams,
    ProtectionThreshold,
    AutoRunParams,
    to_int,
    to_signed_int,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CommandError(Exception):
    """命令执行错误."""
    pass


class Command(ABC, Generic[T]):
    """命令基类."""

    _code: Code
    _protocol: Optional[Protocol] = None
    _response_length: int = 4  # 默认: 地址 + 功能码 + 状态 + 校验

    def __init__(self, device: DeviceParams):
        """初始化命令.
        
        Args:
            device: 设备参数
        """
        self._timestamp = time()
        self._response: Optional[bytes] = None
        self._data: Optional[T] = None
        self._status: StatusCode = StatusCode.FORMAT_ERROR

        self.device = device
        self.address = device.address
        self.checksum_mode = device.checksum_mode
        self.delay = device.delay
        self.serial = device.serial_connection

        # 构建并执行命令
        self._command = self._build_command()
        self._execute()

    @abstractmethod
    def _build_command_body(self) -> bytes:
        """构建命令体(不含校验码)."""
        pass

    @abstractmethod
    def _parse_response(self, data: bytes) -> T:
        """解析响应数据."""
        pass

    def _build_command(self) -> bytes:
        """构建完整命令(含校验码)."""
        body = self._build_command_body()
        return add_checksum(body, self.checksum_mode)

    def _execute(self) -> None:
        """执行命令."""
        tries = 0
        while tries < SystemConstants.MAX_RETRIES:
            try:
                # 清空缓冲区
                self.serial.reset_input_buffer()
                self.serial.reset_output_buffer()

                # 发送命令
                logger.debug(f"发送命令: {self._command.hex()}")
                self.serial.write(self._command)

                # 读取响应
                response = self._read_response()
                if response:
                    self._response = response
                    self._status = StatusCode.SUCCESS
                    break

            except Exception as e:
                logger.warning(f"命令执行失败 (尝试 {tries + 1}): {e}")
                tries += 1

            if self.delay:
                sleep(self.delay)

        if tries >= SystemConstants.MAX_RETRIES:
            logger.error("命令执行失败: 超过最大重试次数")

    def _read_response(self) -> Optional[bytes]:
        """读取响应."""
        # 读取地址
        addr = self.serial.read(1)
        if not addr:
            raise CommandError("未收到响应")

        # 验证地址
        expected_addr = 1 if self.address == Address.BROADCAST else self.address
        if addr[0] != expected_addr:
            raise CommandError(f"地址不匹配: 期望 {expected_addr}, 收到 {addr[0]}")

        # 读取功能码
        code = self.serial.read(1)
        if not code:
            raise CommandError("未收到功能码")

        logger.debug(f"收到功能码: 0x{code[0]:02X}")

        # 读取数据
        data_length = self._response_length - 3  # 减去地址、功能码、校验码
        data = self.serial.read(data_length) if data_length > 0 else b''

        # 读取校验码
        checksum = self.serial.read(1)
        if not checksum:
            raise CommandError("未收到校验码")

        # 验证校验码
        response_body = addr + code + data
        expected_checksum = calculate_checksum(response_body, self.checksum_mode)
        if checksum[0] != expected_checksum:
            raise CommandError(f"校验码不匹配: 期望 0x{expected_checksum:02X}, 收到 0x{checksum[0]:02X}")

        # 解析数据
        if data:
            self._data = self._parse_response(data)

        return response_body + checksum

    @property
    def response(self) -> Optional[bytes]:
        """返回原始响应."""
        return self._response

    @property
    def data(self) -> Optional[T]:
        """返回解析后的数据."""
        return self._data

    @property
    def is_success(self) -> bool:
        """命令是否成功."""
        return self._status == StatusCode.SUCCESS

    @property
    def status(self) -> str:
        """返回状态字符串."""
        return self._status.name


class SimpleCommand(Command[bool]):
    """简单命令(只返回成功/失败)."""

    def _parse_response(self, data: bytes) -> bool:
        """解析响应."""
        if data[0] == StatusCode.SUCCESS:
            return True
        elif data[0] == StatusCode.PARAM_ERROR:
            logger.warning("命令参数错误")
            return False
        elif data[0] == StatusCode.FORMAT_ERROR:
            logger.warning("命令格式错误")
            return False
        return False


class ReadCommand(Command[T]):
    """读取命令基类."""

    def _build_command_body(self) -> bytes:
        """构建命令体."""
        return bytes([self.address, self._code])


# ==================== 触发动作命令 ====================

class CalibrateEncoder(SimpleCommand):
    """触发编码器校准.
    
    对应命令: 5.2.1 触发编码器校准
    发送: 01 06 45 6B
    返回: 01 06 02 6B
    """
    _code = Code.CAL_ENCODER
    _protocol = Protocol.CAL_ENCODER

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code, self._protocol])


class Restart(SimpleCommand):
    """重启电机.
    
    对应命令: 5.2.2 重启电机（X42S/Y42）
    发送: 01 08 97 6B
    返回: 01 08 02 6B
    """
    _code = Code.RESTART
    _protocol = Protocol.RESTART

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code, self._protocol])


class ZeroPosition(SimpleCommand):
    """将当前位置角度清零.
    
    对应命令: 5.2.3 将当前位置角度清零
    发送: 01 0A 6D 6B
    返回: 01 0A 02 6B
    """
    _code = Code.ZERO_POSITION
    _protocol = Protocol.ZERO_POSITION

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code, self._protocol])


class ClearProtection(SimpleCommand):
    """解除堵转/过热/过流保护.
    
    对应命令: 5.2.4 解除堵转/过热/过流保护
    发送: 01 0E 52 6B
    返回: 01 0E 02 6B
    """
    _code = Code.CLEAR_PROTECTION
    _protocol = Protocol.CLEAR_PROTECTION

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code, self._protocol])


class FactoryReset(SimpleCommand):
    """恢复出厂设置.
    
    对应命令: 5.2.5 恢复出厂设置
    发送: 01 0F 5F 6B
    返回: 01 0F 02 6B
    """
    _code = Code.FACTORY_RESET
    _protocol = Protocol.FACTORY_RESET

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code, self._protocol])


# ==================== 运动控制命令 ====================

class Enable(SimpleCommand):
    """电机使能控制.
    
    对应命令: 5.3.2 电机使能控制
    发送: 01 F3 AB 01 00 6B (使能)
    返回: 01 F3 02 6B
    """
    _code = Code.ENABLE
    _protocol = Protocol.ENABLE

    def __init__(self, device: DeviceParams, enable: bool = True, 
                 sync_flag: SyncFlag = SyncFlag.IMMEDIATE):
        self.enable = enable
        self.sync_flag = sync_flag
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
            EnableFlag.ENABLE if self.enable else EnableFlag.DISABLE,
            self.sync_flag,
        ])


class Disable(Enable):
    """电机失能(松轴)."""

    def __init__(self, device: DeviceParams, sync_flag: SyncFlag = SyncFlag.IMMEDIATE):
        super().__init__(device, enable=False, sync_flag=sync_flag)


class Jog(SimpleCommand):
    """速度模式控制 (Emm固件).
    
    对应命令: 5.3.7 速度模式控制（Emm）
    发送: 01 F6 01 05DC 0A 00 6B
    返回: 01 F6 02 6B
    """
    _code = Code.JOG

    def __init__(self, device: DeviceParams, params: Optional[JogParams] = None,
                 direction: Direction = Direction.CW, speed: int = 100,
                 acceleration: int = 10, sync_flag: SyncFlag = SyncFlag.IMMEDIATE):
        if params:
            self.params = params
        else:
            self.params = JogParams(
                direction=direction,
                speed=speed,
                acceleration=acceleration,
                sync_flag=sync_flag,
            )
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code]) + self.params.bytes


class Position(SimpleCommand):
    """位置模式控制 (Emm固件).
    
    对应命令: 5.3.12 位置模式控制（Emm）
    发送: 01 FD 01 05DC 00 00007D00 00 00 6B
    返回: 01 FD 02 6B
    """
    _code = Code.POSITION

    def __init__(self, device: DeviceParams, params: Optional[PositionParams] = None,
                 direction: Direction = Direction.CW, speed: int = 100,
                 acceleration: int = 10, pulse_count: int = 3200,
                 motion_mode: MotionMode = MotionMode.RELATIVE_LAST,
                 sync_flag: SyncFlag = SyncFlag.IMMEDIATE):
        if params:
            self.params = params
        else:
            self.params = PositionParams(
                direction=direction,
                speed=speed,
                acceleration=acceleration,
                pulse_count=pulse_count,
                motion_mode=motion_mode,
                sync_flag=sync_flag,
            )
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code]) + self.params.bytes


class EStop(SimpleCommand):
    """立即停止.
    
    对应命令: 5.3.13 立即停止
    发送: 01 FE 98 00 6B
    返回: 01 FE 02 6B
    """
    _code = Code.ESTOP
    _protocol = Protocol.ESTOP

    def __init__(self, device: DeviceParams, sync_flag: SyncFlag = SyncFlag.IMMEDIATE):
        self.sync_flag = sync_flag
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code, self._protocol, self.sync_flag])


class SyncMove(SimpleCommand):
    """触发多机同步运动.
    
    对应命令: 5.3.14 触发多机同步运动
    发送: 00 FF 66 6B
    返回: 01 FF 02 6B
    """
    _code = Code.SYNC_MOVE
    _protocol = Protocol.SYNC_MOVE

    def _build_command_body(self) -> bytes:
        # 使用广播地址
        return bytes([Address.BROADCAST, self._code, self._protocol])


# ==================== 原点回零命令 ====================

class SetHomeZero(SimpleCommand):
    """设置单圈回零的零点位置.
    
    对应命令: 5.4.1 设置单圈回零的零点位置
    发送: 01 93 88 01 6B
    返回: 01 93 02 6B
    """
    _code = Code.SET_HOME_ZERO
    _protocol = Protocol.SET_HOME_ZERO

    def __init__(self, device: DeviceParams, store: bool = True):
        self.store = store
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
            StoreFlag.STORE if self.store else StoreFlag.NO_STORE,
        ])


class Home(SimpleCommand):
    """触发回零.
    
    对应命令: 5.4.2 触发回零
    发送: 01 9A 00 00 6B
    返回: 01 9A 02 6B
    """
    _code = Code.HOME

    def __init__(self, device: DeviceParams, mode: HomingMode = HomingMode.NEAREST,
                 sync_flag: SyncFlag = SyncFlag.IMMEDIATE):
        self.mode = mode
        self.sync_flag = sync_flag
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code, self.mode, self.sync_flag])


class StopHome(SimpleCommand):
    """强制中断并退出回零操作.
    
    对应命令: 5.4.3 强制中断并退出回零操作
    发送: 01 9C 48 6B
    返回: 01 9C 02 6B
    """
    _code = Code.STOP_HOME
    _protocol = Protocol.STOP_HOME

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code, self._protocol])


class GetHomingStatus(Command[HomingStatus]):
    """读取回零状态标志.
    
    对应命令: 5.4.4 读取回零状态标志
    发送: 01 3B 6B
    返回: 01 3B 03 6B
    """
    _code = Code.GET_HOME_STATUS
    _response_length = 4

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> HomingStatus:
        return HomingStatus.from_byte(data[0])


class GetHomingParams(Command[HomingParams]):
    """读取回零参数.
    
    对应命令: 5.4.5 读取回零参数
    发送: 01 22 6B
    返回: 01 22 + 15字节数据 + 6B
    """
    _code = Code.GET_HOME_PARAM
    _response_length = 18  # 地址 + 功能码 + 15字节数据 + 校验

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> HomingParams:
        return HomingParams.from_bytes(data)


class SetHomingParams(SimpleCommand):
    """修改回零参数.
    
    对应命令: 5.4.6 修改回零参数
    """
    _code = Code.SET_HOME_PARAM
    _protocol = Protocol.SET_HOME_PARAM

    def __init__(self, device: DeviceParams, params: HomingParams, store: bool = True):
        self.params = params
        self.store = store
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
            StoreFlag.STORE if self.store else StoreFlag.NO_STORE,
        ]) + self.params.bytes


# ==================== 读取系统参数命令 ====================

class GetVersion(Command[VersionParams]):
    """读取固件版本和硬件版本.
    
    对应命令: 5.5.2 读取固件版本和硬件版本
    发送: 01 1F 6B
    返回: 01 1F + 4字节数据 + 6B
    """
    _code = Code.GET_VERSION
    _response_length = 7

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> VersionParams:
        return VersionParams.from_bytes(data)


class GetMotorRH(Command[MotorRHParams]):
    """读取相电阻和相电感.
    
    对应命令: 5.5.3 读取相电阻和相电感
    发送: 01 20 6B
    返回: 01 20 + 4字节数据 + 6B
    """
    _code = Code.GET_MOTOR_RH
    _response_length = 7

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> MotorRHParams:
        return MotorRHParams.from_bytes(data)


class GetBusVoltage(Command[int]):
    """读取总线电压.
    
    对应命令: 5.5.4 读取总线电压
    发送: 01 24 6B
    返回: 01 24 + 2字节数据 + 6B
    """
    _code = Code.GET_BUS_VOLTAGE
    _response_length = 5

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> int:
        """返回总线电压(mV)."""
        return to_int(data)


class GetBusCurrent(Command[int]):
    """读取总线电流.
    
    对应命令: 5.5.5 读取总线电流（X42S/Y42）
    发送: 01 26 6B
    返回: 01 26 + 2字节数据 + 6B
    """
    _code = Code.GET_BUS_CURRENT
    _response_length = 5

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> int:
        """返回总线电流(mA)."""
        return to_int(data)


class GetPhaseCurrent(Command[int]):
    """读取相电流.
    
    对应命令: 5.5.6 读取相电流
    发送: 01 27 6B
    返回: 01 27 + 2字节数据 + 6B
    """
    _code = Code.GET_PHASE_CURRENT
    _response_length = 5

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> int:
        """返回相电流(mA)."""
        return to_int(data)


class GetEncoder(Command[int]):
    """读取线性化编码器值.
    
    对应命令: 5.5.7 读取经过线性化校准后的编码器值
    发送: 01 31 6B
    返回: 01 31 + 2字节数据 + 6B
    """
    _code = Code.GET_ENCODER
    _response_length = 5

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> int:
        """返回编码器值(0-65535表示0-360度)."""
        return to_int(data)


class GetPulseCount(Command[int]):
    """读取输入脉冲数.
    
    对应命令: 5.5.8 读取输入脉冲数
    发送: 01 32 6B
    返回: 01 32 + 5字节数据 + 6B
    """
    _code = Code.GET_PULSE_COUNT
    _response_length = 8

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> int:
        """返回输入脉冲数(带符号)."""
        return to_signed_int(data)


class GetTargetPosition(Command[float]):
    """读取电机目标位置.
    
    对应命令: 5.5.9 读取电机目标位置
    发送: 01 33 6B
    返回: 01 33 + 5字节数据 + 6B
    """
    _code = Code.GET_TARGET_POSITION
    _response_length = 8

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> float:
        """返回目标位置角度(度).
        
        Emm固件: 0-65535表示一圈0-360°
        """
        value = to_signed_int(data)
        return (value * 360) / 65536


class GetRealtimeSpeed(Command[int]):
    """读取电机实时转速.
    
    对应命令: 5.5.11 读取电机实时转速
    发送: 01 35 6B
    返回: 01 35 + 3字节数据 + 6B
    """
    _code = Code.GET_REALTIME_SPEED
    _response_length = 6

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> int:
        """返回实时转速(RPM, 带符号)."""
        sign = -1 if data[0] == 1 else 1
        return sign * to_int(data[1:3])


class GetRealtimePosition(Command[float]):
    """读取电机实时位置.
    
    对应命令: 5.5.13 读取电机实时位置
    发送: 01 36 6B
    返回: 01 36 + 5字节数据 + 6B
    """
    _code = Code.GET_REALTIME_POSITION
    _response_length = 8

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> float:
        """返回实时位置角度(度).
        
        Emm固件: 0-65535表示一圈0-360°
        """
        value = to_signed_int(data)
        return (value * 360) / 65536


class GetPositionError(Command[float]):
    """读取电机位置误差.
    
    对应命令: 5.5.14 读取电机位置误差
    发送: 01 37 6B
    返回: 01 37 + 5字节数据 + 6B
    """
    _code = Code.GET_POSITION_ERROR
    _response_length = 8

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> float:
        """返回位置误差角度(度).
        
        Emm固件: 0-65535表示一圈0-360°
        """
        value = to_signed_int(data)
        return (value * 360) / 65536


class GetTemperature(Command[int]):
    """读取驱动温度.
    
    对应命令: 5.5.12 读取驱动温度（X42S/Y42）
    发送: 01 39 6B
    返回: 01 39 + 2字节数据 + 6B
    """
    _code = Code.GET_TEMPERATURE
    _response_length = 5

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> int:
        """返回温度(°C, 带符号)."""
        sign = -1 if data[0] == 0 else 1  # 00=负, 01=正
        return sign * data[1]


class GetMotorStatus(Command[MotorStatus]):
    """读取电机状态标志.
    
    对应命令: 5.5.15 读取电机状态标志
    发送: 01 3A 6B
    返回: 01 3A + 1字节数据 + 6B
    """
    _code = Code.GET_MOTOR_STATUS
    _response_length = 4

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> MotorStatus:
        return MotorStatus.from_byte(data[0])


class GetPID(Command[PIDParams]):
    """读取PID参数 (Emm固件).
    
    对应命令: 5.6.16 读取PID参数（Emm）
    发送: 01 21 6B
    返回: 01 21 + 12字节数据 + 6B
    """
    _code = Code.GET_PID
    _response_length = 15

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> PIDParams:
        return PIDParams.from_bytes(data)


class DynamicLengthCommand(Command[T]):
    """动态长度响应命令基类.
    
    用于响应长度在响应数据中指定的命令（如读取配置参数、系统状态等）。
    
    根据说明书 5.8.5 和 5.8.2，Emm固件返回格式:
    - 字节1: 地址
    - 字节2: 功能码 (0x42 或 0x43)
    - 字节3: 字节数 (整个响应的总字节数，包括地址到校验码)
    - 字节4: 参数个数
    - 字节5-N: 数据
    - 字节N+1: 校验码
    
    例如 Emm固件 get_config 返回:
    - 字节数=0x21(33) 表示整个响应共33字节
    - 数据长度 = 字节数 - 4 (减去地址、功能码、字节数、参数个数) - 1 (校验码)
    - 即 33 - 5 = 28 字节数据
    """
    
    def _read_response(self) -> Optional[bytes]:
        """读取动态长度响应."""
        # 读取地址
        addr = self.serial.read(1)
        if not addr:
            raise CommandError("未收到响应")

        # 验证地址
        expected_addr = 1 if self.address == Address.BROADCAST else self.address
        if addr[0] != expected_addr:
            raise CommandError(f"地址不匹配: 期望 {expected_addr}, 收到 {addr[0]}")

        # 读取功能码
        code = self.serial.read(1)
        if not code:
            raise CommandError("未收到功能码")

        logger.debug(f"收到功能码: 0x{code[0]:02X}")

        # 读取字节数（整个响应的总字节数）
        byte_count = self.serial.read(1)
        if not byte_count:
            raise CommandError("未收到字节数")
        
        total_response_length = byte_count[0]
        logger.debug(f"响应总字节数: {total_response_length}")

        # 读取参数个数
        param_count = self.serial.read(1)
        if not param_count:
            raise CommandError("未收到参数个数")
        
        logger.debug(f"参数个数: {param_count[0]}")

        # 计算剩余数据长度
        # 已读取: 地址(1) + 功能码(1) + 字节数(1) + 参数个数(1) = 4 字节
        # 剩余: 数据 + 校验码 = 总长度 - 4
        # 数据长度 = 总长度 - 4 - 1(校验码) = 总长度 - 5
        data_length = total_response_length - 5
        remaining_data = self.serial.read(data_length)
        if len(remaining_data) < data_length:
            raise CommandError(f"数据不完整: 期望 {data_length} 字节, 收到 {len(remaining_data)} 字节")

        # 读取校验码
        checksum = self.serial.read(1)
        if not checksum:
            raise CommandError("未收到校验码")

        # 组合完整数据（包含字节数和参数个数）
        data = byte_count + param_count + remaining_data
        
        # 验证校验码
        response_body = addr + code + data
        expected_checksum = calculate_checksum(response_body, self.checksum_mode)
        if checksum[0] != expected_checksum:
            raise CommandError(f"校验码不匹配: 期望 0x{expected_checksum:02X}, 收到 0x{checksum[0]:02X}")

        # 解析数据
        if data:
            self._data = self._parse_response(data)

        return response_body + checksum


class GetConfig(DynamicLengthCommand[ConfigParams]):
    """读取驱动配置参数 (Emm固件).
    
    对应命令: 5.8.5 读取驱动配置参数（Emm）
    发送: 01 42 6C 6B
    返回: 01 42 21 15 + 数据 + 6B
    
    Emm固件返回: 字节数=0x21(33), 参数个数=0x15(21)
    """
    _code = Code.GET_CONFIG
    _protocol = Protocol.GET_CONFIG

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code, self._protocol])

    def _parse_response(self, data: bytes) -> ConfigParams:
        # data[0] = 字节数, data[1] = 参数个数, data[2:] = 实际数据
        return ConfigParams.from_bytes(data[2:])


class GetSystemStatus(DynamicLengthCommand[SystemStatusParams]):
    """读取系统状态参数 (Emm固件).
    
    对应命令: 5.8.2 读取系统状态参数（Emm）
    发送: 01 43 7A 6B
    返回: 01 43 1F 09 + 数据 + 6B
    
    Emm固件返回: 字节数=0x1F(31), 参数个数=0x09(9)
    """
    _code = Code.GET_SYS_STATUS
    _protocol = Protocol.GET_SYS_STATUS

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code, self._protocol])

    def _parse_response(self, data: bytes) -> SystemStatusParams:
        # data[0] = 字节数, data[1] = 参数个数, data[2:] = 实际数据
        return SystemStatusParams.from_bytes(data[2:])


# ==================== 设置命令 ====================

class SetID(SimpleCommand):
    """修改电机ID/地址.
    
    对应命令: 5.6.1 修改电机ID/地址
    发送: 01 AE 4B 01 02 6B
    返回: 01 AE 02 6B
    """
    _code = Code.SET_ID
    _protocol = Protocol.SET_ID

    def __init__(self, device: DeviceParams, new_id: int, store: bool = True):
        if not 1 <= new_id <= 255:
            raise ValueError("ID必须在 1-255 之间")
        self.new_id = new_id
        self.store = store
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
            StoreFlag.STORE if self.store else StoreFlag.NO_STORE,
            self.new_id,
        ])


class SetMicrostep(SimpleCommand):
    """修改细分值.
    
    对应命令: 5.6.2 修改细分值
    发送: 01 84 8A 01 10 6B
    返回: 01 84 02 6B
    """
    _code = Code.SET_MICROSTEP
    _protocol = Protocol.SET_MICROSTEP

    def __init__(self, device: DeviceParams, microstep: int, store: bool = True):
        if not 1 <= microstep <= 256:
            raise ValueError("细分值必须在 1-256 之间")
        self.microstep = microstep if microstep < 256 else 0  # 256用0表示
        self.store = store
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
            StoreFlag.STORE if self.store else StoreFlag.NO_STORE,
            self.microstep,
        ])


class SetLoopMode(SimpleCommand):
    """修改开环/闭环控制模式.
    
    对应命令: 5.6.7 修改开环/闭环控制模式
    发送: 01 46 A6 01 01 6B
    返回: 01 46 02 6B
    """
    _code = Code.SET_LOOP_MODE
    _protocol = Protocol.SET_LOOP_MODE

    def __init__(self, device: DeviceParams, closed_loop: bool = True, store: bool = True):
        self.closed_loop = closed_loop
        self.store = store
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        from .configs import ControlMode
        return bytes([
            self.address,
            self._code,
            self._protocol,
            StoreFlag.STORE if self.store else StoreFlag.NO_STORE,
            ControlMode.CLOSED_LOOP if self.closed_loop else ControlMode.OPEN_LOOP,
        ])


class SetOpenLoopCurrent(SimpleCommand):
    """修改开环模式工作电流.
    
    对应命令: 5.6.12 修改开环模式工作电流
    发送: 01 44 33 01 04B0 6B
    返回: 01 44 02 6B
    """
    _code = Code.SET_OPEN_LOOP_CURRENT
    _protocol = Protocol.SET_OPEN_LOOP_CURRENT

    def __init__(self, device: DeviceParams, current_ma: int, store: bool = True):
        if not 0 <= current_ma <= 5000:
            raise ValueError("电流必须在 0-5000 mA 之间")
        self.current = current_ma
        self.store = store
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
            StoreFlag.STORE if self.store else StoreFlag.NO_STORE,
            (self.current >> 8) & 0xFF,
            self.current & 0xFF,
        ])


class SetClosedLoopCurrent(SimpleCommand):
    """修改闭环模式最大电流.
    
    对应命令: 5.6.13 修改闭环模式最大电流
    发送: 01 45 66 01 0BB8 6B
    返回: 01 45 02 6B
    """
    _code = Code.SET_CLOSED_LOOP_CURRENT
    _protocol = Protocol.SET_CLOSED_LOOP_CURRENT

    def __init__(self, device: DeviceParams, current_ma: int, store: bool = True):
        if not 0 <= current_ma <= 5000:
            raise ValueError("电流必须在 0-5000 mA 之间")
        self.current = current_ma
        self.store = store
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
            StoreFlag.STORE if self.store else StoreFlag.NO_STORE,
            (self.current >> 8) & 0xFF,
            self.current & 0xFF,
        ])


class SetPID(SimpleCommand):
    """修改PID参数 (Emm固件).
    
    对应命令: 5.6.17 修改PID参数（Emm）
    """
    _code = Code.SET_PID
    _protocol = Protocol.SET_PID

    def __init__(self, device: DeviceParams, params: PIDParams, store: bool = True):
        self.params = params
        self.store = store
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
            StoreFlag.STORE if self.store else StoreFlag.NO_STORE,
        ]) + self.params.bytes


class SetMotorDirection(SimpleCommand):
    """修改电机运动正方向.
    
    对应命令: 5.6.8 修改电机运动正方向
    发送: 01 D4 60 01 00 6B
    返回: 01 D4 02 6B
    """
    _code = Code.SET_MOTOR_DIRECTION
    _protocol = Protocol.SET_MOTOR_DIRECTION

    def __init__(self, device: DeviceParams, direction: Direction = Direction.CW, store: bool = True):
        self.direction = direction
        self.store = store
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
            StoreFlag.STORE if self.store else StoreFlag.NO_STORE,
            self.direction,
        ])


class SetPositionWindow(SimpleCommand):
    """修改位置到达窗口.
    
    对应命令: 5.6.21 修改位置到达窗口（X42S/Y42）
    发送: 01 D1 07 01 0008 6B
    返回: 01 D1 02 6B
    """
    _code = Code.SET_POSITION_WINDOW
    _protocol = Protocol.SET_POSITION_WINDOW

    def __init__(self, device: DeviceParams, window_deg: float = 0.8, store: bool = True):
        """设置位置到达窗口.
        
        Args:
            device: 设备参数
            window_deg: 位置到达窗口(度), 默认0.8度
            store: 是否存储
        """
        self.window = int(window_deg * 10)  # 内部缩小10倍处理
        self.store = store
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
            StoreFlag.STORE if self.store else StoreFlag.NO_STORE,
            (self.window >> 8) & 0xFF,
            self.window & 0xFF,
        ])


class SetHeartbeatTime(SimpleCommand):
    """修改心跳保护功能时间.
    
    对应命令: 5.6.25 修改心跳保护功能时间（X42S/Y42）
    发送: 01 68 38 01 00001388 6B
    返回: 01 68 02 6B
    """
    _code = Code.SET_HEARTBEAT_TIME
    _protocol = Protocol.SET_HEARTBEAT_TIME

    def __init__(self, device: DeviceParams, time_ms: int = 0, store: bool = True):
        """设置心跳保护时间.
        
        Args:
            device: 设备参数
            time_ms: 心跳保护时间(毫秒), 0表示关闭
            store: 是否存储
        """
        self.time_ms = time_ms
        self.store = store
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
            StoreFlag.STORE if self.store else StoreFlag.NO_STORE,
            (self.time_ms >> 24) & 0xFF,
            (self.time_ms >> 16) & 0xFF,
            (self.time_ms >> 8) & 0xFF,
            self.time_ms & 0xFF,
        ])


class SetAutoRun(SimpleCommand):
    """存储一组速度参数，上电自动运行 (Emm固件).
    
    对应命令: 5.7.2 存储一组速度参数，上电自动运行（Emm）
    """
    _code = Code.SET_AUTO_RUN
    _protocol = Protocol.SET_AUTO_RUN

    def __init__(self, device: DeviceParams, params: AutoRunParams):
        self.params = params
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
        ]) + self.params.bytes


class SetConfig(SimpleCommand):
    """修改驱动配置参数 (Emm固件).
    
    对应命令: 5.8.6 修改驱动配置参数（Emm）
    """
    _code = Code.SET_CONFIG
    _protocol = Protocol.SET_CONFIG

    def __init__(self, device: DeviceParams, params: ConfigParams, store: bool = True):
        self.params = params
        self.store = store
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
            StoreFlag.STORE if self.store else StoreFlag.NO_STORE,
        ]) + self.params.bytes


class SetScaleInput(SimpleCommand):
    """修改命令速度值是否缩小10倍输入 (Emm固件).
    
    对应命令: 5.6.11 修改命令速度值是否缩小10倍输入（Emm）
    发送: 01 4F 71 01 01 6B
    返回: 01 4F 02 6B
    """
    _code = Code.SET_SCALE_INPUT
    _protocol = Protocol.SET_SCALE_INPUT

    def __init__(self, device: DeviceParams, enable: bool = False, store: bool = True):
        """设置速度值缩小10倍输入.
        
        Args:
            device: 设备参数
            enable: 是否使能(使能后输入1RPM实际为0.1RPM)
            store: 是否存储
        """
        self.enable = enable
        self.store = store
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
            StoreFlag.STORE if self.store else StoreFlag.NO_STORE,
            1 if self.enable else 0,
        ])


class SetLockButton(SimpleCommand):
    """修改锁定按键功能.
    
    对应命令: 5.6.9 修改锁定按键功能
    发送: 01 D0 B3 01 01 6B
    返回: 01 D0 02 6B
    """
    _code = Code.SET_LOCK_BUTTON
    _protocol = Protocol.SET_LOCK_BUTTON

    def __init__(self, device: DeviceParams, lock: bool = False, store: bool = True):
        self.lock = lock
        self.store = store
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
            StoreFlag.STORE if self.store else StoreFlag.NO_STORE,
            1 if self.lock else 0,
        ])


class BroadcastGetID(Command[int]):
    """广播读取ID地址.
    
    对应命令: 5.6.30 广播读取ID地址（X42S/Y42）
    发送: 00 15 6B
    返回: 01 15 01 6B
    """
    _code = Code.BROADCAST_GET_ID
    _response_length = 4

    def __init__(self, device: DeviceParams):
        # 强制使用广播地址
        device.address = Address(Address.BROADCAST)
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([Address.BROADCAST, self._code])

    def _parse_response(self, data: bytes) -> int:
        """返回电机ID."""
        return data[0]