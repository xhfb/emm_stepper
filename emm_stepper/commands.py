"""Emm固件步进电机命令类.

基于ZDT_X42S第二代闭环步进电机用户手册V1.0.3_251224。
"""

import logging
from abc import ABC, abstractmethod
from time import sleep, time
from typing import Optional, TypeVar, Generic, Any, List

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
    MotorType,
    FirmwareType,
    LockParamLevel,
    add_checksum,
    calculate_checksum,
    SystemConstants,
)
from .parameters import (
    DeviceParams,
    JogParams,
    PositionParams,
    FastPositionParams,
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
    IOStatus,
    HomeMotorStatus,
    OptionStatus,
    DMX512Params,
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
                # 等待串口稳定，确保上一个命令的响应已完全接收
                #sleep(0.002)

                # 清空缓冲区
                in_waiting = self.serial.in_waiting
                if in_waiting > 0:
                    stale_data = self.serial.read(in_waiting)
                    logger.debug(f"清空残留数据 ({in_waiting} 字节): {stale_data.hex()}")
                self.serial.reset_input_buffer()
                self.serial.reset_output_buffer()

                # 发送命令
                logger.debug(f"发送命令 (地址={self.address}): {self._command.hex()}")
                self.serial.write(self._command)
                self.serial.flush()

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
        expected_addr = 1 if self.address == Address.BROADCAST else self.address

        # 读取地址，允许跳过最多 8 个非预期字节（处理异步返回数据干扰）
        skipped = b''
        addr = None
        for _ in range(8):
            byte = self.serial.read(1)
            if not byte:
                if skipped:
                    logger.debug(f"跳过了非预期字节后超时: 跳过={skipped.hex()}")
                raise CommandError("未收到响应")
            if byte[0] == expected_addr:
                addr = byte
                break
            else:
                skipped += byte
        
        if addr is None:
            logger.debug(
                f"地址不匹配详情: 发送命令={self._command.hex()}, "
                f"期望地址=0x{expected_addr:02X}({expected_addr}), "
                f"跳过的字节={skipped.hex()} ({len(skipped)} 字节)"
            )
            raise CommandError(f"地址不匹配: 期望 {expected_addr}, 跳过了 {skipped.hex()}")
        
        if skipped:
            logger.debug(
                f"跳过了 {len(skipped)} 个非预期字节: {skipped.hex()}, "
                f"命令={self._command.hex()}"
            )

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
        elif data[0] in (StatusCode.AT_ZERO, StatusCode.LIMIT_OR_HOME):
            logger.warning("零点/限位条件阻止动作 (0x%02X)", data[0])
            return False
        elif data[0] == StatusCode.PARAM_ERROR:
            logger.warning("命令参数错误")
            return False
        elif data[0] == StatusCode.FORMAT_ERROR:
            logger.warning("命令格式错误")
            return False
        return False

    @property
    def is_success(self) -> bool:
        """以返回状态字节为准(避免任意响应都被标为成功)."""
        return bool(self._data)


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


class ConfigureFastPosition(SimpleCommand):
    """快速位置模式设参 (Emm, V2.0.0+).
    
    对应命令: 5.3.13 快速位置模式控制（Emm）— F1
    发送: 01 F1 03 20 64 00 00 6B
    返回: 01 F1 02 6B
    """
    _code = Code.FAST_POSITION_CFG

    def __init__(
        self,
        device: DeviceParams,
        params: Optional[FastPositionParams] = None,
        speed: int = 100,
        acceleration: int = 10,
        motion_mode: MotionMode = MotionMode.RELATIVE_LAST,
        sync_flag: SyncFlag = SyncFlag.IMMEDIATE,
    ):
        if params:
            self.params = params
        else:
            self.params = FastPositionParams(
                speed=speed,
                acceleration=acceleration,
                motion_mode=motion_mode,
                sync_flag=sync_flag,
            )
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code]) + self.params.bytes


class FastPositionPulse(SimpleCommand):
    """快速位置模式发脉冲 (Emm, V2.0.0+).
    
    对应命令: 5.3.13 快速位置模式控制（Emm）— FC
    发送: 01 FC 00 00 0C 80 6B
    返回: 01 FC 02 6B
    
    脉冲数为有符号 int32（大端），负值表示反方向。
    """
    _code = Code.FAST_POSITION_PULSE

    def __init__(self, device: DeviceParams, pulses: int = 3200):
        if not -0x80000000 <= pulses <= 0x7FFFFFFF:
            raise ValueError("脉冲数必须在有符号 int32 范围内")
        self.pulses = pulses
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code]) + self.pulses.to_bytes(
            4, "big", signed=True
        )


class EStop(SimpleCommand):
    """立即停止.
    
    对应命令: 立即停止
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
    返回: 01 FF 02 6B (仅地址1回复)
    """
    _code = Code.SYNC_MOVE
    _protocol = Protocol.SYNC_MOVE

    def __init__(self, device: DeviceParams):
        # 广播发送、期望地址1回复；不得永久改写调用方的 address
        saved = device.address
        device.address = Address(Address.BROADCAST)
        try:
            super().__init__(device)
        finally:
            device.address = saved

    def _build_command_body(self) -> bytes:
        return bytes([Address.BROADCAST, self._code, self._protocol])


class MultiMotor(Command[bool]):
    """多电机命令.
    
    对应命令: 5.3.1 多电机命令（X42S/Y42）
    发送: 00 AA + 字节长度 + 子命令... + 6B
    
    子命令须为已含校验码的完整帧。运动类命令仅地址1会回复确认。
    """
    _code = Code.MULTI_MOTOR
    _response_length = 4

    def __init__(
        self,
        device: DeviceParams,
        frames: List[bytes],
        expect_ack: bool = True,
    ):
        if not frames:
            raise ValueError("多电机命令至少需要一条子命令")
        self.frames = frames
        self.expect_ack = expect_ack
        device.address = Address(Address.BROADCAST)
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        payload = b"".join(self.frames)
        # 总字节数 = 整帧长度(地址+功能码+长度字段+子命令+外层校验)
        total_len = 5 + len(payload)
        return bytes([
            Address.BROADCAST,
            self._code,
            (total_len >> 8) & 0xFF,
            total_len & 0xFF,
        ]) + payload

    def _parse_response(self, data: bytes) -> bool:
        if not data:
            return True
        return data[0] == StatusCode.SUCCESS

    def _execute(self) -> None:
        # 多电机帧禁止重试：位置/速度子命令重复发送会导致多转
        try:
            in_waiting = self.serial.in_waiting
            if in_waiting > 0:
                self.serial.read(in_waiting)
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            logger.debug(f"发送多电机命令: {self._command.hex()}")
            self.serial.write(self._command)
            self.serial.flush()
            if not self.expect_ack:
                self._status = StatusCode.SUCCESS
                self._data = True
                self._response = self._command
                return
            response = self._read_response()
            if response:
                self._response = response
                self._status = StatusCode.SUCCESS
            else:
                # 已发出去，勿重发；无 ACK 仍视为发送成功
                logger.warning("多电机命令未收到确认，但不会重发")
                self._status = StatusCode.SUCCESS
                self._data = True
        except Exception as e:
            logger.warning(f"多电机命令执行异常(不重发): {e}")
            # 帧可能已发出，标记成功避免上层误判为未发送
            self._status = StatusCode.SUCCESS
            self._data = True


def build_command_frame(body: bytes, checksum_mode: ChecksumMode = ChecksumMode.FIXED) -> bytes:
    """构建含校验码的完整命令帧(用于多电机命令子帧)."""
    return add_checksum(body, checksum_mode)


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
    返回: 01 9A 02 6B (已在零点时可能为 12)
    """
    _code = Code.HOME

    def __init__(self, device: DeviceParams, mode: HomingMode = HomingMode.NEAREST,
                 sync_flag: SyncFlag = SyncFlag.IMMEDIATE):
        self.mode = mode
        self.sync_flag = sync_flag
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code, self.mode, self.sync_flag])

    def _parse_response(self, data: bytes) -> bool:
        if data[0] in (StatusCode.SUCCESS, StatusCode.AT_ZERO):
            return True
        if data[0] == StatusCode.PARAM_ERROR:
            logger.warning("回零命令参数错误(若已在零点可先离开再试)")
            return False
        if data[0] == StatusCode.FORMAT_ERROR:
            logger.warning("回零命令格式错误")
            return False
        return False


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


class GetRealtimeTarget(Command[float]):
    """读取电机实时设定的目标位置.
    
    对应命令: 5.5.10 读取电机实时设定的目标位置
    发送: 01 34 6B
    返回: 01 34 + 5字节数据 + 6B
    """
    _code = Code.GET_REALTIME_TARGET
    _response_length = 8

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> float:
        """返回实时设定目标位置角度(度).
        
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


class GetHomeMotorStatus(Command[HomeMotorStatus]):
    """读取回零状态标志 + 电机状态标志.
    
    对应命令: 5.5.16 读取回零状态标志+电机状态标志（X42S/Y42）
    发送: 01 3C 6B
    返回: 01 3C + 2字节数据 + 6B
    """
    _code = Code.GET_HOME_MOTOR_STATUS
    _response_length = 5

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> HomeMotorStatus:
        return HomeMotorStatus.from_bytes(data)


class GetIOStatus(Command[IOStatus]):
    """读取引脚 IO 电平状态.
    
    对应命令: 5.5.17 读取引脚IO电平状态（X42S/Y42）
    发送: 01 3D 6B
    返回: 01 3D + 1字节数据 + 6B
    """
    _code = Code.GET_IO_STATUS
    _response_length = 4

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> IOStatus:
        return IOStatus.from_byte(data[0])


class TimedReturn(Command[Optional[bytes]]):
    """定时返回信息命令.
    
    对应命令: 5.5.1 定时返回信息命令（X42S/Y42）
    发送: 01 11 18 + 信息功能码 + 定时时间(ms) + 6B
    定时时间为0时停止返回，确认帧为 Addr 11 6B。
    """
    _code = Code.TIMED_RETURN
    _protocol = Protocol.TIMED_RETURN

    # 常见信息功能码对应的完整响应长度(含地址/功能码/校验)
    _INFO_RESPONSE_LENGTH = {
        Code.GET_VERSION: 7,
        Code.GET_MOTOR_RH: 7,
        Code.GET_BUS_VOLTAGE: 5,
        Code.GET_BUS_CURRENT: 5,
        Code.GET_PHASE_CURRENT: 5,
        Code.GET_ENCODER: 5,
        Code.GET_PULSE_COUNT: 7,
        Code.GET_TARGET_POSITION: 8,
        Code.GET_REALTIME_TARGET: 8,
        Code.GET_REALTIME_SPEED: 6,
        Code.GET_REALTIME_POSITION: 8,
        Code.GET_POSITION_ERROR: 8,
        Code.GET_TEMPERATURE: 5,
        Code.GET_MOTOR_STATUS: 4,
        Code.GET_HOME_STATUS: 4,
        Code.GET_HOME_MOTOR_STATUS: 5,
        Code.GET_IO_STATUS: 4,
    }

    def __init__(self, device: DeviceParams, info_code: int, interval_ms: int = 0):
        self.info_code = info_code & 0xFF
        self.interval_ms = max(0, min(interval_ms, 0xFFFF))
        if self.interval_ms == 0:
            # 实机停止确认: Addr 11 02 6B（手册示例偶发省略状态字节）
            self._response_length = 4
        else:
            self._response_length = self._INFO_RESPONSE_LENGTH.get(self.info_code, 8)
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
            self.info_code,
            (self.interval_ms >> 8) & 0xFF,
            self.interval_ms & 0xFF,
        ])

    def _parse_response(self, data: bytes) -> Optional[bytes]:
        return data if data else None


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
        expected_addr = 1 if self.address == Address.BROADCAST else self.address

        # 读取地址，允许跳过最多 8 个非预期字节（处理异步返回数据干扰）
        skipped = b''
        addr = None
        for _ in range(8):
            byte = self.serial.read(1)
            if not byte:
                if skipped:
                    logger.debug(f"[动态长度] 跳过了非预期字节后超时: 跳过={skipped.hex()}")
                raise CommandError("未收到响应")
            if byte[0] == expected_addr:
                addr = byte
                break
            else:
                skipped += byte
        
        if addr is None:
            logger.debug(
                f"[动态长度] 地址不匹配详情: 发送命令={self._command.hex()}, "
                f"期望地址=0x{expected_addr:02X}({expected_addr}), "
                f"跳过的字节={skipped.hex()} ({len(skipped)} 字节)"
            )
            raise CommandError(f"地址不匹配: 期望 {expected_addr}, 跳过了 {skipped.hex()}")
        
        if skipped:
            logger.debug(
                f"[动态长度] 跳过了 {len(skipped)} 个非预期字节: {skipped.hex()}, "
                f"命令={self._command.hex()}"
            )

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
    """修改位置到达窗口 (独立命令 D1 07).
    
    对应命令: 5.6.21 修改位置到达窗口（X42S/Y42）
    发送: 01 D1 07 01 0008 6B
    返回: 01 D1 02 6B
    
    注意: 部分 Emm 固件对该命令返回 EE。高层 API 请用
    EmmDevice.set_position_window（经 set_config 改写）。
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


class SetPowerOffFlag(SimpleCommand):
    """修改掉电标志.
    
    对应命令: 5.6.3 修改掉电标志
    发送: 01 50 00 6B
    返回: 01 50 02 6B
    """
    _code = Code.SET_POWER_OFF_FLAG

    def __init__(self, device: DeviceParams, flag: bool = False):
        self.flag = flag
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code, 1 if self.flag else 0])


class GetOptionStatus(Command[OptionStatus]):
    """读取选项参数状态.
    
    对应命令: 5.6.4 读取选项参数状态（X42S/Y42）
    发送: 01 1A 6B
    返回: 01 1A + 2字节数据 + 6B (实机 V1.0.7 为双字节，含锁定等级)
    
    注意: 部分固件该帧字段可能不可信。
    """
    _code = Code.GET_OPTION_STATUS
    _response_length = 5

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> OptionStatus:
        return OptionStatus.from_bytes(data)


class SetMotorType(SimpleCommand):
    """修改电机类型.
    
    对应命令: 5.6.5 修改电机类型
    发送: 01 D7 35 01 19 6B (1.8°)
    返回: 01 D7 02 6B
    
    实机确认: 0x19=1.8°, 0x32=0.9°。修改后需重新空载校准。
    """
    _code = Code.SET_MOTOR_TYPE
    _protocol = Protocol.SET_MOTOR_TYPE

    def __init__(
        self,
        device: DeviceParams,
        motor_type: MotorType = MotorType.DEGREE_18,
        store: bool = True,
    ):
        self.motor_type = motor_type
        self.store = store
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
            StoreFlag.STORE if self.store else StoreFlag.NO_STORE,
            int(self.motor_type),
        ])


class SetFirmwareType(SimpleCommand):
    """修改固件类型.
    
    对应命令: 5.6.6 修改固件类型
    发送: 01 D5 69 01 01 6B
    返回: 01 D5 02 6B
    
    建议在电机停止时修改。
    """
    _code = Code.SET_FIRMWARE_TYPE
    _protocol = Protocol.SET_FIRMWARE_TYPE

    def __init__(
        self,
        device: DeviceParams,
        firmware_type: FirmwareType = FirmwareType.EMM_FIRMWARE,
        store: bool = True,
    ):
        self.firmware_type = firmware_type
        self.store = store
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
            StoreFlag.STORE if self.store else StoreFlag.NO_STORE,
            int(self.firmware_type),
        ])


class GetDMX512Params(Command[DMX512Params]):
    """读取 DMX512 协议参数.
    
    对应命令: 5.6.18 读取DMX512协议参数（X42S/Y42）
    发送: 01 49 78 6B
    """
    _code = Code.GET_DMX512_PARAM
    _protocol = Protocol.GET_DMX512_PARAM
    _response_length = 17

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code, self._protocol])

    def _parse_response(self, data: bytes) -> DMX512Params:
        return DMX512Params.from_bytes(data)


class SetDMX512Params(SimpleCommand):
    """修改 DMX512 协议参数.
    
    对应命令: 5.6.19 修改DMX512协议参数（X42S/Y42）
    """
    _code = Code.SET_DMX512_PARAM
    _protocol = Protocol.SET_DMX512_PARAM

    def __init__(self, device: DeviceParams, params: DMX512Params, store: bool = True):
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


class GetPositionWindow(Command[float]):
    """读取位置到达窗口.
    
    对应命令: 5.6.20 读取位置到达窗口（X42S/Y42）
    发送: 01 41 6B
    返回: 01 41 + 2字节数据 + 6B
    """
    _code = Code.GET_POSITION_WINDOW
    _response_length = 5

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> float:
        """返回位置到达窗口(度)."""
        return to_int(data[0:2]) * 0.1


class GetProtectionThreshold(Command[ProtectionThreshold]):
    """读取过热过流保护检测阈值.
    
    对应命令: 5.6.22 读取过热过流保护检测阈值（X42S/Y42）
    发送: 01 13 6B
    """
    _code = Code.GET_PROTECTION_THRESHOLD
    _response_length = 9

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> ProtectionThreshold:
        return ProtectionThreshold.from_bytes(data)


class SetProtectionThreshold(SimpleCommand):
    """修改过热过流保护检测阈值.
    
    对应命令: 5.6.23 修改过热过流保护检测阈值（X42S/Y42）
    """
    _code = Code.SET_PROTECTION_THRESHOLD
    _protocol = Protocol.SET_PROTECTION_THRESHOLD

    def __init__(
        self,
        device: DeviceParams,
        params: ProtectionThreshold,
        store: bool = True,
    ):
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


class GetHeartbeatTime(Command[int]):
    """读取心跳保护功能时间.
    
    对应命令: 5.6.24 读取心跳保护功能时间（X42S/Y42）
    发送: 01 16 6B
    """
    _code = Code.GET_HEARTBEAT_TIME
    _response_length = 7

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> int:
        """返回心跳保护时间(ms)."""
        return to_int(data[0:4])


class GetIntegralStiffness(Command[int]):
    """读取积分限幅/刚性系数.
    
    对应命令: 5.6.26 读取积分限幅/刚性系数（X42S/Y42）
    Emm固件默认积分限幅 65535。
    """
    _code = Code.GET_INTEGRAL_STIFFNESS
    _response_length = 7

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> int:
        return to_int(data[0:4])


class SetIntegralStiffness(SimpleCommand):
    """修改积分限幅/刚性系数.
    
    对应命令: 5.6.27 修改积分限幅/刚性系数（X42S/Y42）
    """
    _code = Code.SET_INTEGRAL_STIFFNESS
    _protocol = Protocol.SET_INTEGRAL_STIFFNESS

    def __init__(self, device: DeviceParams, value: int = 65535, store: bool = True):
        self.value = value & 0xFFFFFFFF
        self.store = store
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
            StoreFlag.STORE if self.store else StoreFlag.NO_STORE,
            (self.value >> 24) & 0xFF,
            (self.value >> 16) & 0xFF,
            (self.value >> 8) & 0xFF,
            self.value & 0xFF,
        ])


class GetCollisionReturnAngle(Command[float]):
    """读取碰撞回零返回角度.
    
    对应命令: 5.6.28 读取碰撞回零返回角度（X42S/Y42）
    """
    _code = Code.GET_COLLISION_RETURN_ANGLE
    _response_length = 5

    def _build_command_body(self) -> bytes:
        return bytes([self.address, self._code])

    def _parse_response(self, data: bytes) -> float:
        """返回角度(度); 0 表示按电流检测返回."""
        return to_int(data[0:2]) * 0.1


class SetCollisionReturnAngle(SimpleCommand):
    """修改碰撞回零返回角度.
    
    对应命令: 5.6.29 修改碰撞回零返回角度（X42S/Y42）
    值为0表示基于电流检测返回；其余为固定角度(0.1°单位)。
    """
    _code = Code.SET_COLLISION_RETURN_ANGLE
    _protocol = Protocol.SET_COLLISION_RETURN_ANGLE

    def __init__(self, device: DeviceParams, angle_deg: float = 0.0, store: bool = True):
        self.angle_raw = int(round(angle_deg * 10)) & 0xFFFF
        self.store = store
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
            StoreFlag.STORE if self.store else StoreFlag.NO_STORE,
            (self.angle_raw >> 8) & 0xFF,
            self.angle_raw & 0xFF,
        ])


class SetLockParam(SimpleCommand):
    """修改锁定修改参数功能.
    
    对应命令: 5.6.31 修改锁定修改参数功能（X42S/Y42）
    """
    _code = Code.SET_LOCK_PARAM
    _protocol = Protocol.SET_LOCK_PARAM

    def __init__(
        self,
        device: DeviceParams,
        level: LockParamLevel = LockParamLevel.UNLOCKED,
        store: bool = True,
    ):
        self.level = level
        self.store = store
        super().__init__(device)

    def _build_command_body(self) -> bytes:
        return bytes([
            self.address,
            self._code,
            self._protocol,
            StoreFlag.STORE if self.store else StoreFlag.NO_STORE,
            int(self.level),
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