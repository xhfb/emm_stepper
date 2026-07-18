"""Emm固件步进电机参数类.

基于ZDT_X42S第二代闭环步进电机用户手册V1.0.3_251224。
"""

from dataclasses import dataclass, field
from typing import Optional

from serial import Serial

from .configs import (
    Address,
    ChecksumMode,
    Direction,
    SyncFlag,
    StoreFlag,
    MotionMode,
    HomingMode,
    HomingDirection,
    ControlMode,
    MotorType,
    FirmwareType,
    BaudRate,
    CanRate,
    ResponseMode,
    StallProtect,
    PulsePortMode,
    SerialPortMode,
    EnableLevel,
    DirLevel,
)


def to_int(data: bytes) -> int:
    """将字节转换为整数."""
    return int.from_bytes(data, "big")


def to_signed_int(data: bytes) -> int:
    """将带符号字节转换为有符号整数.
    
    第一个字节为符号位: 00=正, 01=负
    """
    if len(data) < 2:
        return to_int(data)
    sign = -1 if data[0] == 1 else 1
    return sign * to_int(data[1:])


@dataclass
class DeviceParams:
    """设备参数类.
    
    Args:
        serial_connection: 串口连接对象
        address: 电机地址 (1-255, 0为广播地址)
        checksum_mode: 校验模式
        delay: 通讯延迟(秒)
    """
    serial_connection: Serial
    address: int = Address.DEFAULT
    checksum_mode: ChecksumMode = ChecksumMode.FIXED
    delay: Optional[float] = None

    def __post_init__(self):
        if isinstance(self.address, int) and not isinstance(self.address, Address):
            self.address = Address(self.address)


@dataclass
class JogParams:
    """速度模式参数 (Emm固件).
    
    对应命令: 5.3.7 速度模式控制（Emm）
    
    Args:
        direction: 运动方向 (CW/CCW)
        speed: 速度 (0-6000 RPM)
        acceleration: 加速度档位 (0-255)
        sync_flag: 同步标志
    """
    direction: Direction = Direction.CW
    speed: int = 100  # 0-6000 RPM
    acceleration: int = 10  # 0-255档位
    sync_flag: SyncFlag = SyncFlag.IMMEDIATE

    def __post_init__(self):
        # 速度范围检查 (手册命令表仍写 0BB8/3000，V1.0.5 产品规格与实机为 6000)
        if not 0 <= self.speed <= 6000:
            raise ValueError("速度必须在 0-6000 RPM 之间")
        # 加速度范围检查
        if not 0 <= self.acceleration <= 255:
            raise ValueError("加速度必须在 0-255 之间")

    @property
    def bytes(self) -> bytes:
        """返回命令字节."""
        return bytes([
            self.direction,
            (self.speed >> 8) & 0xFF,
            self.speed & 0xFF,
            self.acceleration,
            self.sync_flag,
        ])


@dataclass
class PositionParams:
    """位置模式参数 (Emm固件).
    
    对应命令: 5.3.12 位置模式控制（Emm）
    
    Args:
        direction: 运动方向 (CW/CCW)
        speed: 速度 (0-6000 RPM)
        acceleration: 加速度档位 (0-255)
        pulse_count: 脉冲数 (默认16细分下，3200个脉冲=一圈360°)
        motion_mode: 运动模式 (相对/绝对)
        sync_flag: 同步标志
    """
    direction: Direction = Direction.CW
    speed: int = 100  # 0-6000 RPM
    acceleration: int = 10  # 0-255档位
    pulse_count: int = 3200  # 脉冲数
    motion_mode: MotionMode = MotionMode.RELATIVE_LAST
    sync_flag: SyncFlag = SyncFlag.IMMEDIATE

    def __post_init__(self):
        if not 0 <= self.speed <= 6000:
            raise ValueError("速度必须在 0-6000 RPM 之间")
        if not 0 <= self.acceleration <= 255:
            raise ValueError("加速度必须在 0-255 之间")
        if not 0 <= self.pulse_count <= 0xFFFFFFFF:
            raise ValueError("脉冲数必须在 0-4294967295 之间")

    @property
    def bytes(self) -> bytes:
        """返回命令字节."""
        return bytes([
            self.direction,
            (self.speed >> 8) & 0xFF,
            self.speed & 0xFF,
            self.acceleration,
            (self.pulse_count >> 24) & 0xFF,
            (self.pulse_count >> 16) & 0xFF,
            (self.pulse_count >> 8) & 0xFF,
            self.pulse_count & 0xFF,
            self.motion_mode,
            self.sync_flag,
        ])


@dataclass
class FastPositionParams:
    """快速位置模式设参 (Emm, V2.0.0+).
    
    对应命令: 5.3.13 快速位置模式控制（Emm）— F1 设参。
    方向由后续 FC 脉冲的有符号 int32 隐含。
    
    Args:
        speed: 速度 (0-6000 RPM)
        acceleration: 加速度档位 (0-255)
        motion_mode: 运动模式 (相对上一目标/绝对/相对当前位置)
        sync_flag: 同步标志
    """
    speed: int = 100
    acceleration: int = 10
    motion_mode: MotionMode = MotionMode.RELATIVE_LAST
    sync_flag: SyncFlag = SyncFlag.IMMEDIATE

    def __post_init__(self):
        if not 0 <= self.speed <= 6000:
            raise ValueError("速度必须在 0-6000 RPM 之间")
        if not 0 <= self.acceleration <= 255:
            raise ValueError("加速度必须在 0-255 之间")

    @property
    def bytes(self) -> bytes:
        """返回 F1 命令体（不含地址/功能码/校验）."""
        return bytes([
            (self.speed >> 8) & 0xFF,
            self.speed & 0xFF,
            self.acceleration,
            self.motion_mode,
            self.sync_flag,
        ])


@dataclass
class HomingParams:
    """回零参数.
    
    对应命令: 5.4.6 修改回零参数
    
    Args:
        homing_mode: 回零模式
        homing_direction: 回零方向
        homing_speed: 回零速度 (0-3000 RPM)
        homing_timeout: 回零超时时间 (毫秒)
        collision_speed: 碰撞回零检测转速 (RPM)
        collision_current: 碰撞回零检测电流 (mA)
        collision_time: 碰撞回零检测时间 (ms)
        auto_home: 是否使能上电自动触发回零
    """
    homing_mode: HomingMode = HomingMode.NEAREST
    homing_direction: HomingDirection = HomingDirection.CW
    homing_speed: int = 30  # RPM
    homing_timeout: int = 10000  # ms
    collision_speed: int = 300  # RPM
    collision_current: int = 800  # mA
    collision_time: int = 60  # ms
    auto_home: bool = False

    @property
    def bytes(self) -> bytes:
        """返回命令字节."""
        return bytes([
            self.homing_mode,
            self.homing_direction,
            (self.homing_speed >> 8) & 0xFF,
            self.homing_speed & 0xFF,
            (self.homing_timeout >> 24) & 0xFF,
            (self.homing_timeout >> 16) & 0xFF,
            (self.homing_timeout >> 8) & 0xFF,
            self.homing_timeout & 0xFF,
            (self.collision_speed >> 8) & 0xFF,
            self.collision_speed & 0xFF,
            (self.collision_current >> 8) & 0xFF,
            self.collision_current & 0xFF,
            (self.collision_time >> 8) & 0xFF,
            self.collision_time & 0xFF,
            1 if self.auto_home else 0,
        ])

    @classmethod
    def from_bytes(cls, data: bytes) -> "HomingParams":
        """从字节数据解析回零参数."""
        return cls(
            homing_mode=HomingMode(data[0]),
            homing_direction=HomingDirection(data[1]),
            homing_speed=to_int(data[2:4]),
            homing_timeout=to_int(data[4:8]),
            collision_speed=to_int(data[8:10]),
            collision_current=to_int(data[10:12]),
            collision_time=to_int(data[12:14]),
            auto_home=bool(data[14]),
        )


@dataclass
class VersionParams:
    """版本参数.
    
    对应命令: 5.5.2 读取固件版本和硬件版本
    """
    firmware_version: int = 0
    hw_series: int = 0  # 0=X系列, 1=Y系列
    hw_type: int = 0  # 0/1/2/3/4/5/6 = 20/28/35/42/57/86
    hw_version: int = 0

    @classmethod
    def from_bytes(cls, data: bytes) -> "VersionParams":
        """从字节数据解析版本参数."""
        fw_ver = to_int(data[0:2])
        hw_info = to_int(data[2:4])
        return cls(
            firmware_version=fw_ver,
            hw_series=(hw_info >> 12) & 0x0F,
            hw_type=(hw_info >> 8) & 0x0F,
            hw_version=hw_info & 0xFF,
        )

    @property
    def firmware_version_str(self) -> str:
        """返回固件版本字符串."""
        major = self.firmware_version // 100
        minor = (self.firmware_version % 100) // 10
        patch = self.firmware_version % 10
        return f"V{major}.{minor}.{patch}"

    @property
    def is_v2(self) -> bool:
        """是否为 V2.0.0 及以上固件 (firmware_version >= 200)."""
        return self.firmware_version >= 200

    @property
    def hw_series_str(self) -> str:
        """返回硬件系列字符串."""
        return "X系列" if self.hw_series == 0 else "Y系列"

    @property
    def hw_type_str(self) -> str:
        """返回硬件类型字符串."""
        types = {0: "20", 1: "28", 2: "35", 3: "42", 4: "57", 5: "86"}
        series = "X" if self.hw_series == 0 else "Y"
        return f"{series}{types.get(self.hw_type, 'Unknown')}"


@dataclass
class MotorRHParams:
    """电机相电阻和相电感参数.
    
    对应命令: 5.5.3 读取相电阻和相电感
    """
    phase_resistance: int = 0  # mΩ
    phase_inductance: int = 0  # uH

    @classmethod
    def from_bytes(cls, data: bytes) -> "MotorRHParams":
        """从字节数据解析."""
        return cls(
            phase_resistance=to_int(data[0:2]),
            phase_inductance=to_int(data[2:4]),
        )


@dataclass
class PIDParams:
    """PID参数 (Emm固件).
    
    对应命令: 5.6.16 读取PID参数（Emm）
    """
    kp: int = 18000  # 比例系数
    ki: int = 10  # 积分系数
    kd: int = 18000  # 微分系数

    @property
    def bytes(self) -> bytes:
        """返回命令字节."""
        return bytes([
            (self.kp >> 24) & 0xFF,
            (self.kp >> 16) & 0xFF,
            (self.kp >> 8) & 0xFF,
            self.kp & 0xFF,
            (self.ki >> 24) & 0xFF,
            (self.ki >> 16) & 0xFF,
            (self.ki >> 8) & 0xFF,
            self.ki & 0xFF,
            (self.kd >> 24) & 0xFF,
            (self.kd >> 16) & 0xFF,
            (self.kd >> 8) & 0xFF,
            self.kd & 0xFF,
        ])

    @classmethod
    def from_bytes(cls, data: bytes) -> "PIDParams":
        """从字节数据解析PID参数."""
        return cls(
            kp=to_int(data[0:4]),
            ki=to_int(data[4:8]),
            kd=to_int(data[8:12]),
        )


@dataclass
class HomingStatus:
    """回零状态标志.
    
    对应命令: 5.4.4 读取回零状态标志
    """
    encoder_ready: bool = False  # 编码器就绪
    calibrated: bool = False  # 校准表就绪
    is_homing: bool = False  # 正在回零
    homing_failed: bool = False  # 回零失败
    over_temp: bool = False  # 过热保护
    over_current: bool = False  # 过流保护

    @classmethod
    def from_byte(cls, data: int) -> "HomingStatus":
        """从字节数据解析回零状态."""
        return cls(
            encoder_ready=bool(data & 0x01),
            calibrated=bool(data & 0x02),
            is_homing=bool(data & 0x04),
            homing_failed=bool(data & 0x08),
            over_temp=bool(data & 0x10),
            over_current=bool(data & 0x20),
        )

    @property
    def homing_state(self) -> str:
        """返回回零状态字符串."""
        if self.is_homing:
            return "正在回零"
        elif self.homing_failed:
            return "回零失败"
        else:
            return "回零成功/未回零"


@dataclass
class MotorStatus:
    """电机状态标志.
    
    对应命令: 5.5.15 读取电机状态标志
    """
    enabled: bool = False  # 使能状态
    position_reached: bool = False  # 位置到达
    stall_detected: bool = False  # 堵转标志
    stall_protected: bool = False  # 堵转保护
    left_limit: bool = False  # 左限位开关状态
    right_limit: bool = False  # 右限位开关状态
    power_off_flag: bool = True  # 掉电标志

    @classmethod
    def from_byte(cls, data: int) -> "MotorStatus":
        """从字节数据解析电机状态."""
        return cls(
            enabled=bool(data & 0x01),
            position_reached=bool(data & 0x02),
            stall_detected=bool(data & 0x04),
            stall_protected=bool(data & 0x08),
            left_limit=bool(data & 0x10),
            right_limit=bool(data & 0x20),
            power_off_flag=bool(data & 0x80),
        )


@dataclass
class SystemStatusParams:
    """系统状态参数 (Emm固件).
    
    对应命令: 5.8.2 读取系统状态参数（Emm）
    """
    bus_voltage: int = 0  # mV
    phase_current: int = 0  # mA
    encoder_value: int = 0  # 线性化编码器值
    target_position: int = 0  # 电机目标位置
    target_position_sign: int = 0  # 符号
    realtime_speed: int = 0  # 电机实时转速 RPM
    realtime_speed_sign: int = 0  # 符号
    realtime_position: int = 0  # 电机实时位置
    realtime_position_sign: int = 0  # 符号
    position_error: int = 0  # 电机位置误差
    position_error_sign: int = 0  # 符号
    homing_status: HomingStatus = field(default_factory=HomingStatus)
    motor_status: MotorStatus = field(default_factory=MotorStatus)

    @classmethod
    def from_bytes(cls, data: bytes) -> "SystemStatusParams":
        """从字节数据解析系统状态参数."""
        # Emm固件返回格式: 1F 09 + 数据
        return cls(
            bus_voltage=to_int(data[0:2]),
            phase_current=to_int(data[2:4]),
            encoder_value=to_int(data[4:6]),
            target_position_sign=data[6],
            target_position=to_int(data[7:11]),
            realtime_speed_sign=data[11],
            realtime_speed=to_int(data[12:14]),
            realtime_position_sign=data[14],
            realtime_position=to_int(data[15:19]),
            position_error_sign=data[19],
            position_error=to_int(data[20:24]),
            homing_status=HomingStatus.from_byte(data[24]),
            motor_status=MotorStatus.from_byte(data[25]),
        )

    @property
    def target_position_deg(self) -> float:
        """返回目标位置角度(度)."""
        sign = -1 if self.target_position_sign == 1 else 1
        return sign * (self.target_position * 360) / 65536

    @property
    def realtime_position_deg(self) -> float:
        """返回实时位置角度(度)."""
        sign = -1 if self.realtime_position_sign == 1 else 1
        return sign * (self.realtime_position * 360) / 65536

    @property
    def position_error_deg(self) -> float:
        """返回位置误差角度(度)."""
        sign = -1 if self.position_error_sign == 1 else 1
        return sign * (self.position_error * 360) / 65536

    @property
    def realtime_speed_rpm(self) -> int:
        """返回实时转速(RPM)."""
        sign = -1 if self.realtime_speed_sign == 1 else 1
        return sign * self.realtime_speed


@dataclass
class ConfigParams:
    """驱动配置参数 (Emm固件).
    
    对应命令: 5.8.5 读取驱动配置参数（Emm）
    """
    motor_type: MotorType = MotorType.DEGREE_18
    pulse_port_mode: PulsePortMode = PulsePortMode.FOC
    serial_port_mode: SerialPortMode = SerialPortMode.UART
    enable_level: EnableLevel = EnableLevel.HOLD
    dir_level: DirLevel = DirLevel.CW
    microstep: int = 16
    microstep_interp: bool = True
    open_loop_current: int = 1200  # mA
    closed_loop_current: int = 3000  # mA
    max_voltage: int = 4000  # 闭环最大输出电压原始值; 实际 mV = value * 3
    baud_rate: BaudRate = BaudRate.BAUD_115200
    can_rate: CanRate = CanRate.CAN_500K
    motor_id: int = 1  # 仅读取有效; SET 配置时该位为保留字节须写 0
    checksum_mode: ChecksumMode = ChecksumMode.FIXED
    response_mode: ResponseMode = ResponseMode.RECEIVE
    stall_protect: StallProtect = StallProtect.ENABLE  # 0/1/2 均有效
    stall_speed: int = 8  # RPM
    stall_current: int = 2200  # mA
    stall_time: int = 2000  # ms
    position_window: int = 8  # *0.1度

    @property
    def bytes(self) -> bytes:
        """返回 5.8.6 修改驱动配置参数 的数据区字节.

        注意: 读配置 data[16] 为电机 ID; 写配置同一位置为保留字节, 必须为 0。
        修改地址请使用 set_id (0xAE), 勿通过 set_config 写入 ID。
        """
        return bytes([
            self.motor_type,
            self.pulse_port_mode,
            self.serial_port_mode,
            self.enable_level,
            self.dir_level,
            self.microstep,
            1 if self.microstep_interp else 0,
            0,  # 保留 (读配置时为自动熄屏)
            (self.open_loop_current >> 8) & 0xFF,
            self.open_loop_current & 0xFF,
            (self.closed_loop_current >> 8) & 0xFF,
            self.closed_loop_current & 0xFF,
            (self.max_voltage >> 8) & 0xFF,
            self.max_voltage & 0xFF,
            self.baud_rate,
            self.can_rate,
            0,  # 保留 (读配置时为 ID/地址)
            self.checksum_mode,
            self.response_mode,
            self.stall_protect,
            (self.stall_speed >> 8) & 0xFF,
            self.stall_speed & 0xFF,
            (self.stall_current >> 8) & 0xFF,
            self.stall_current & 0xFF,
            (self.stall_time >> 8) & 0xFF,
            self.stall_time & 0xFF,
            (self.position_window >> 8) & 0xFF,
            self.position_window & 0xFF,
        ])

    @classmethod
    def from_bytes(cls, data: bytes) -> "ConfigParams":
        """从 5.8.5 读取驱动配置参数 的数据区解析."""
        return cls(
            motor_type=MotorType(data[0]),
            pulse_port_mode=PulsePortMode(data[1]),
            serial_port_mode=SerialPortMode(data[2]),
            enable_level=EnableLevel(data[3]),
            dir_level=DirLevel(data[4]),
            microstep=data[5],
            microstep_interp=bool(data[6]),
            open_loop_current=to_int(data[8:10]),
            closed_loop_current=to_int(data[10:12]),
            max_voltage=to_int(data[12:14]),
            baud_rate=BaudRate(data[14]),
            can_rate=CanRate(data[15]),
            motor_id=data[16],
            checksum_mode=ChecksumMode(data[17]),
            response_mode=ResponseMode(data[18]),
            stall_protect=StallProtect(data[19]),
            stall_speed=to_int(data[20:22]),
            stall_current=to_int(data[22:24]),
            stall_time=to_int(data[24:26]),
            position_window=to_int(data[26:28]),
        )

    @property
    def position_window_deg(self) -> float:
        """返回位置到达窗口(度)."""
        return self.position_window * 0.1

    @property
    def max_voltage_mv(self) -> int:
        """闭环最大输出电压 (mV), 原始值 × 3."""
        return self.max_voltage * 3


@dataclass
class ProtectionThreshold:
    """过热过流保护检测阈值.
    
    对应命令: 5.6.22 读取过热过流保护检测阈值
    """
    over_temp_threshold: int = 100  # °C
    over_current_threshold: int = 6600  # mA
    detection_time: int = 1000  # ms

    @property
    def bytes(self) -> bytes:
        """返回命令字节."""
        return bytes([
            (self.over_temp_threshold >> 8) & 0xFF,
            self.over_temp_threshold & 0xFF,
            (self.over_current_threshold >> 8) & 0xFF,
            self.over_current_threshold & 0xFF,
            (self.detection_time >> 8) & 0xFF,
            self.detection_time & 0xFF,
        ])

    @classmethod
    def from_bytes(cls, data: bytes) -> "ProtectionThreshold":
        """从字节数据解析."""
        return cls(
            over_temp_threshold=to_int(data[0:2]),
            over_current_threshold=to_int(data[2:4]),
            detection_time=to_int(data[4:6]),
        )


@dataclass
class AutoRunParams:
    """上电自动运行参数 (Emm固件).
    
    对应命令: 5.7.2 存储一组速度参数，上电自动运行（Emm）
    """
    store: bool = True  # 存储/清除
    direction: Direction = Direction.CW
    speed: int = 600  # RPM
    acceleration: int = 100  # 档位
    enable_en_control: bool = False  # 是否使能En引脚控制启停

    @property
    def bytes(self) -> bytes:
        """返回命令字节."""
        return bytes([
            1 if self.store else 0,
            self.direction,
            (self.speed >> 8) & 0xFF,
            self.speed & 0xFF,
            self.acceleration,
            1 if self.enable_en_control else 0,
        ])


@dataclass
class IOStatus:
    """引脚 IO 电平状态.
    
    对应命令: 5.5.17 读取引脚IO电平状态（X42S/Y42）
    """
    en_pin: bool = False  # En引脚高电平
    step_pin: bool = False  # 脉冲引脚高电平
    dir_pin: bool = False  # 方向引脚高电平
    dir_output_mode: bool = False  # 方向引脚为输出模式

    @classmethod
    def from_byte(cls, data: int) -> "IOStatus":
        return cls(
            en_pin=bool(data & 0x01),
            step_pin=bool(data & 0x04),
            dir_pin=bool(data & 0x10),
            dir_output_mode=bool(data & 0x20),
        )


@dataclass
class HomeMotorStatus:
    """回零状态 + 电机状态.
    
    对应命令: 5.5.16 读取回零状态标志+电机状态标志
    """
    homing: HomingStatus = field(default_factory=HomingStatus)
    motor: MotorStatus = field(default_factory=MotorStatus)

    @classmethod
    def from_bytes(cls, data: bytes) -> "HomeMotorStatus":
        return cls(
            homing=HomingStatus.from_byte(data[0]),
            motor=MotorStatus.from_byte(data[1]),
        )


@dataclass
class OptionStatus:
    """选项参数状态.
    
    对应命令: 5.6.4 读取选项参数状态（X42S/Y42）
    
    注意: 部分固件上该帧字段(尤其 FwType)可能不可信，勿单独用于判固件类型。
    实机(V1.0.7)返回 2 字节: 低字节为手册 bit0-bit7，高字节低 2 位为锁定等级。
    """
    motor_is_09_degree: bool = False  # True=0.9°, False=1.8°
    firmware_is_emm: bool = True  # True=Emm, False=X
    closed_loop: bool = True
    direction_ccw: bool = False  # True=CCW为正方向
    button_locked: bool = False
    scale_input: bool = False  # 速度缩小10倍输入
    lock_param_level: int = 0  # 0-3, 见 LockParamLevel
    raw: int = 0  # 原始 16-bit (高字节在前时为 data0<<8|data1 的相反——此处存 LE: b0|(b1<<8))

    @classmethod
    def from_byte(cls, data: int) -> "OptionStatus":
        return cls.from_bytes(bytes([data & 0xFF]))

    @classmethod
    def from_bytes(cls, data: bytes) -> "OptionStatus":
        b0 = data[0] if data else 0
        b1 = data[1] if len(data) > 1 else 0
        return cls(
            motor_is_09_degree=bool(b0 & 0x01),
            firmware_is_emm=bool(b0 & 0x02),
            closed_loop=bool(b0 & 0x04),
            direction_ccw=bool(b0 & 0x10),
            button_locked=bool(b0 & 0x20),
            scale_input=bool(b0 & 0x80),
            lock_param_level=b1 & 0x03,
            raw=b0 | (b1 << 8),
        )


@dataclass
class DMX512Params:
    """DMX512 协议参数.
    
    对应命令: 5.6.18/5.6.19 读取/修改DMX512协议参数
    """
    total_channels: int = 192  # 总通道数 1-64(手册示例默认192)
    channels_per_motor: int = 1  # 1=单通道, 2=双通道
    absolute_mode: bool = True  # True=绝对位置, False=相对位置
    single_channel_speed: int = 1000  # RPM
    acceleration: int = 1000  # Emm: acc=值/8
    dual_speed_step: int = 10  # 双通道速度步长 RPM
    dual_motion_step: int = 100  # 双通道运动步长(×0.1°)

    @property
    def dual_motion_step_deg(self) -> float:
        return self.dual_motion_step * 0.1

    @property
    def bytes(self) -> bytes:
        return bytes([
            (self.total_channels >> 8) & 0xFF,
            self.total_channels & 0xFF,
            self.channels_per_motor,
            1 if self.absolute_mode else 0,
            (self.single_channel_speed >> 8) & 0xFF,
            self.single_channel_speed & 0xFF,
            (self.acceleration >> 8) & 0xFF,
            self.acceleration & 0xFF,
            (self.dual_speed_step >> 8) & 0xFF,
            self.dual_speed_step & 0xFF,
            (self.dual_motion_step >> 24) & 0xFF,
            (self.dual_motion_step >> 16) & 0xFF,
            (self.dual_motion_step >> 8) & 0xFF,
            self.dual_motion_step & 0xFF,
        ])

    @classmethod
    def from_bytes(cls, data: bytes) -> "DMX512Params":
        return cls(
            total_channels=to_int(data[0:2]),
            channels_per_motor=data[2],
            absolute_mode=bool(data[3]),
            single_channel_speed=to_int(data[4:6]),
            acceleration=to_int(data[6:8]),
            dual_speed_step=to_int(data[8:10]),
            dual_motion_step=to_int(data[10:14]),
        )
