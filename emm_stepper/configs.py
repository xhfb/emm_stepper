"""Emm固件步进电机配置常量.

基于ZDT_X42S第二代闭环步进电机用户手册V1.0.3_251224。
"""

from dataclasses import dataclass, field
from enum import IntEnum


class ExtendedIntEnum(IntEnum):
    """扩展的整数枚举，支持字节表示."""

    @property
    def bytes(self) -> bytes:
        """返回字节表示."""
        return self.value.to_bytes(1, "big")


@dataclass(frozen=True)
class SystemConstants:
    """系统常量."""

    SERIAL_TIMEOUT: float = field(default=0.1)
    MAX_RETRIES: int = field(default=3)
    DEFAULT_BAUDRATE: int = field(default=115200)


class Code(ExtendedIntEnum):
    """命令功能码 - Emm固件."""

    # 触发动作命令
    CAL_ENCODER = 0x06  # 触发编码器校准
    RESTART = 0x08  # 重启电机
    ZERO_POSITION = 0x0A  # 将当前位置角度清零
    CLEAR_PROTECTION = 0x0E  # 解除堵转/过热/过流保护
    FACTORY_RESET = 0x0F  # 恢复出厂设置

    # 运动控制命令
    MULTI_MOTOR = 0xAA  # 多电机命令
    ENABLE = 0xF3  # 电机使能控制
    JOG = 0xF6  # 速度模式控制(Emm)
    POSITION = 0xFD  # 位置模式控制(Emm)
    ESTOP = 0xFE  # 立即停止
    SYNC_MOVE = 0xFF  # 触发多机同步运动

    # 原点回零命令
    SET_HOME_ZERO = 0x93  # 设置单圈回零的零点位置
    HOME = 0x9A  # 触发回零
    STOP_HOME = 0x9C  # 强制中断并退出回零操作
    GET_HOME_STATUS = 0x3B  # 读取回零状态标志
    GET_HOME_PARAM = 0x22  # 读取回零参数
    SET_HOME_PARAM = 0x4C  # 修改回零参数

    # 读取系统参数命令
    TIMED_RETURN = 0x11  # 定时返回信息命令
    GET_VERSION = 0x1F  # 读取固件版本和硬件版本
    GET_MOTOR_RH = 0x20  # 读取相电阻和相电感
    GET_PID = 0x21  # 读取PID参数
    GET_INTEGRAL_STIFFNESS = 0x23  # 读取积分限幅/刚性系数
    GET_BUS_VOLTAGE = 0x24  # 读取总线电压
    GET_BUS_CURRENT = 0x26  # 读取总线电流
    GET_PHASE_CURRENT = 0x27  # 读取相电流
    GET_ENCODER = 0x31  # 读取线性化编码器值
    GET_PULSE_COUNT = 0x32  # 读取输入脉冲数
    GET_TARGET_POSITION = 0x33  # 读取电机目标位置
    GET_REALTIME_TARGET = 0x34  # 读取电机实时设定的目标位置
    GET_REALTIME_SPEED = 0x35  # 读取电机实时转速
    GET_REALTIME_POSITION = 0x36  # 读取电机实时位置
    GET_POSITION_ERROR = 0x37  # 读取电机位置误差
    GET_BATTERY_VOLTAGE = 0x38  # 读取电池电压(Y42)
    GET_TEMPERATURE = 0x39  # 读取驱动温度
    GET_MOTOR_STATUS = 0x3A  # 读取电机状态标志
    GET_HOME_MOTOR_STATUS = 0x3C  # 读取回零状态标志+电机状态标志
    GET_IO_STATUS = 0x3D  # 读取引脚IO电平状态
    GET_COLLISION_RETURN_ANGLE = 0x3F  # 读取碰撞回零返回角度
    GET_POSITION_WINDOW = 0x41  # 读取位置到达窗口
    GET_SYS_STATUS = 0x43  # 读取系统状态参数
    GET_CONFIG = 0x42  # 读取驱动配置参数

    # 读写驱动参数命令
    GET_PROTECTION_THRESHOLD = 0x13  # 读取过热过流保护检测阈值
    BROADCAST_GET_ID = 0x15  # 广播读取ID地址
    GET_HEARTBEAT_TIME = 0x16  # 读取心跳保护功能时间
    GET_OPTION_STATUS = 0x1A  # 读取选项参数状态
    SET_OPEN_LOOP_CURRENT = 0x44  # 修改开环模式工作电流
    SET_CLOSED_LOOP_CURRENT = 0x45  # 修改闭环模式最大电流
    SET_LOOP_MODE = 0x46  # 修改开环/闭环控制模式
    SET_CONFIG = 0x48  # 修改驱动配置参数
    SET_PID = 0x4A  # 修改PID参数
    SET_INTEGRAL_STIFFNESS = 0x4B  # 修改积分限幅/刚性系数
    SET_SCALE_INPUT = 0x4F  # 修改命令速度值是否缩小10倍输入
    SET_POWER_OFF_FLAG = 0x50  # 修改掉电标志
    SET_COLLISION_RETURN_ANGLE = 0x5C  # 修改碰撞回零返回角度
    SET_HEARTBEAT_TIME = 0x68  # 修改心跳保护功能时间
    SET_MICROSTEP = 0x84  # 修改细分值
    SET_ID = 0xAE  # 修改电机ID/地址
    SET_LOCK_BUTTON = 0xD0  # 修改锁定按键功能
    SET_POSITION_WINDOW = 0xD1  # 修改位置到达窗口
    SET_PROTECTION_THRESHOLD = 0xD3  # 修改过热过流保护检测阈值
    SET_MOTOR_DIRECTION = 0xD4  # 修改电机运动正方向
    SET_FIRMWARE_TYPE = 0xD5  # 修改固件类型
    SET_LOCK_PARAM = 0xD6  # 修改锁定修改参数功能
    SET_MOTOR_TYPE = 0xD7  # 修改电机类型
    SET_DMX512_PARAM = 0xD9  # 修改DMX512协议参数

    # 上电自动运行命令
    SET_AUTO_RUN = 0xF7  # 存储一组速度参数，上电自动运行


class Protocol(ExtendedIntEnum):
    """协议辅助码."""

    # 触发动作命令
    CAL_ENCODER = 0x45
    RESTART = 0x97
    ZERO_POSITION = 0x6D
    CLEAR_PROTECTION = 0x52
    FACTORY_RESET = 0x5F

    # 运动控制命令
    ENABLE = 0xAB
    ESTOP = 0x98
    SYNC_MOVE = 0x66

    # 原点回零命令
    SET_HOME_ZERO = 0x88
    STOP_HOME = 0x48
    SET_HOME_PARAM = 0xAE

    # 定时返回
    TIMED_RETURN = 0x18

    # 读取配置
    GET_CONFIG = 0x6C
    GET_SYS_STATUS = 0x7A
    GET_DMX512_PARAM = 0x78

    # 设置命令
    SET_MICROSTEP = 0x8A
    SET_ID = 0x4B
    SET_OPEN_LOOP_CURRENT = 0x33
    SET_CLOSED_LOOP_CURRENT = 0x66
    SET_LOOP_MODE = 0xA6
    SET_CONFIG = 0xD1
    SET_PID = 0xC3
    SET_AUTO_RUN = 0x1C
    SET_SCALE_INPUT = 0x71
    SET_MOTOR_DIRECTION = 0x60
    SET_FIRMWARE_TYPE = 0x69
    SET_MOTOR_TYPE = 0x35
    SET_LOCK_BUTTON = 0xB3
    SET_POSITION_WINDOW = 0x07
    SET_PROTECTION_THRESHOLD = 0x56
    SET_HEARTBEAT_TIME = 0x38
    SET_INTEGRAL_STIFFNESS = 0x57
    SET_COLLISION_RETURN_ANGLE = 0xAC
    SET_LOCK_PARAM = 0x4B
    SET_DMX512_PARAM = 0x90


class StatusCode(ExtendedIntEnum):
    """状态码."""

    FIXED_CHECKSUM = 0x6B  # 固定校验码
    SUCCESS = 0x02  # 命令正确
    AT_ZERO = 0x12  # 触发回零时当前就在零点处
    PARAM_ERROR = 0xE2  # 命令参数错误
    FORMAT_ERROR = 0xEE  # 命令格式错误
    ACTION_COMPLETE = 0x9F  # 动作执行完成


class ChecksumMode(ExtendedIntEnum):
    """校验方式."""

    FIXED = 0  # 固定0x6B
    XOR = 1  # 异或校验
    CRC8 = 2  # CRC-8校验
    MODBUS = 3  # Modbus-RTU协议
    DMX512 = 4  # DMX512协议

    default = FIXED


class Address(int):
    """电机地址 (1-255, 0为广播地址)."""

    BROADCAST = 0
    MIN = 0
    MAX = 255
    DEFAULT = 1

    def __new__(cls, value: int = DEFAULT) -> "Address":
        if not cls.MIN <= value <= cls.MAX:
            raise ValueError(f"地址必须在 {cls.MIN} 到 {cls.MAX} 之间")
        return super().__new__(cls, value)

    @property
    def bytes(self) -> bytes:
        return self.to_bytes(1, "big")


class Direction(ExtendedIntEnum):
    """运动方向."""

    CW = 0  # 顺时针
    CCW = 1  # 逆时针

    default = CW


class SyncFlag(ExtendedIntEnum):
    """同步标志."""

    IMMEDIATE = 0  # 立即执行
    SYNC = 1  # 先缓存当前命令

    default = IMMEDIATE


class StoreFlag(ExtendedIntEnum):
    """存储标志."""

    NO_STORE = 0  # 不存储
    STORE = 1  # 存储(掉电不丢失)

    default = NO_STORE


class EnableFlag(ExtendedIntEnum):
    """使能标志."""

    DISABLE = 0  # 不使能(松轴)
    ENABLE = 1  # 使能(锁轴)

    default = ENABLE


class MotionMode(ExtendedIntEnum):
    """运动模式."""

    RELATIVE_LAST = 0  # 相对上一输入目标位置进行相对位置运动
    ABSOLUTE = 1  # 相对坐标零点进行绝对位置运动
    RELATIVE_CURRENT = 2  # 相对当前实时位置进行相对位置运动

    default = RELATIVE_LAST


class HomingMode(ExtendedIntEnum):
    """回零模式."""

    NEAREST = 0  # 单圈就近回零
    DIRECTION = 1  # 单圈方向回零
    COLLISION = 2  # 无限位碰撞回零
    LIMIT_SWITCH = 3  # 限位回零
    ABS_ZERO = 4  # 回到绝对位置坐标零点
    LAST_POWER_OFF = 5  # 回到上次掉电位置角度

    default = NEAREST


class HomingDirection(ExtendedIntEnum):
    """回零方向."""

    CW = 0  # 顺时针
    CCW = 1  # 逆时针

    default = CW


class ControlMode(ExtendedIntEnum):
    """控制模式."""

    OPEN_LOOP = 0  # 开环模式
    CLOSED_LOOP = 1  # FOC闭环模式

    default = CLOSED_LOOP


class MotorType(ExtendedIntEnum):
    """电机类型."""

    DEGREE_09 = 0x19  # 0.9度步进电机
    DEGREE_18 = 0x32  # 1.8度步进电机

    default = DEGREE_18


class FirmwareType(ExtendedIntEnum):
    """固件类型."""

    X_FIRMWARE = 0  # X固件
    EMM_FIRMWARE = 1  # Emm固件
    EMM_TURBO = 2  # Emm固件狂暴模式

    default = EMM_FIRMWARE


class BaudRate(ExtendedIntEnum):
    """串口波特率."""

    BAUD_9600 = 0
    BAUD_19200 = 1
    BAUD_25000 = 2
    BAUD_38400 = 3
    BAUD_57600 = 4
    BAUD_115200 = 5
    BAUD_256000 = 6
    BAUD_512000 = 7
    BAUD_921600 = 8

    default = BAUD_115200

    @property
    def value_hz(self) -> int:
        """返回实际波特率值."""
        rates = [9600, 19200, 25000, 38400, 57600, 115200, 256000, 512000, 921600]
        return rates[self.value]


class CanRate(ExtendedIntEnum):
    """CAN通讯速率."""

    CAN_10K = 0
    CAN_20K = 1
    CAN_50K = 2
    CAN_83K = 3
    CAN_100K = 4
    CAN_125K = 5
    CAN_250K = 6
    CAN_500K = 7
    CAN_800K = 8
    CAN_1M = 9

    default = CAN_500K


class ResponseMode(ExtendedIntEnum):
    """控制命令应答方式."""

    NONE = 0  # 不返回任何命令
    RECEIVE = 1  # 只返回确认收到命令
    REACHED = 2  # 只返回到位/回零完成命令
    BOTH = 3  # 既返回确认收到命令，也返回动作完成命令
    OTHER = 4  # 位置模式返回动作完成命令，其他返回确认收到命令

    default = RECEIVE


class StallProtect(ExtendedIntEnum):
    """堵转保护."""

    DISABLE = 0  # 关闭堵转保护
    ENABLE = 1  # 使能堵转保护
    AUTO_ZERO = 2  # 堵转后复位为零点

    default = ENABLE


class PulsePortMode(ExtendedIntEnum):
    """脉冲端口复用模式."""

    OFF = 0  # 关闭脉冲端口
    OPEN = 1  # 开环模式
    FOC = 2  # FOC闭环模式
    ESI_RCO = 3  # 限位回零输入
    PLR_ESI = 4  # 左右限位功能

    default = FOC


class SerialPortMode(ExtendedIntEnum):
    """通讯端口复用模式."""

    OFF = 0  # 关闭通讯端口
    ESI_ALO = 1  # 限位输入+报警输出
    UART = 2  # 串口通讯
    CAN = 3  # CAN通讯
    ULR_ESI = 4  # 左右限位功能

    default = UART


class EnableLevel(ExtendedIntEnum):
    """En引脚有效电平."""

    LOW = 0  # 低电平有效
    HIGH = 1  # 高电平有效
    HOLD = 2  # 一直有效

    default = HOLD


class DirLevel(ExtendedIntEnum):
    """Dir引脚有效电平."""

    CW = 0  # 顺时针
    CCW = 1  # 逆时针

    default = CW


# CRC8查找表
CRC8_TABLE = bytes([
    0x00, 0x5E, 0xBC, 0xE2, 0x61, 0x3F, 0xDD, 0x83,
    0xC2, 0x9C, 0x7E, 0x20, 0xA3, 0xFD, 0x1F, 0x41,
    0x9D, 0xC3, 0x21, 0x7F, 0xFC, 0xA2, 0x40, 0x1E,
    0x5F, 0x01, 0xE3, 0xBD, 0x3E, 0x60, 0x82, 0xDC,
    0x23, 0x7D, 0x9F, 0xC1, 0x42, 0x1C, 0xFE, 0xA0,
    0xE1, 0xBF, 0x5D, 0x03, 0x80, 0xDE, 0x3C, 0x62,
    0xBE, 0xE0, 0x02, 0x5C, 0xDF, 0x81, 0x63, 0x3D,
    0x7C, 0x22, 0xC0, 0x9E, 0x1D, 0x43, 0xA1, 0xFF,
    0x46, 0x18, 0xFA, 0xA4, 0x27, 0x79, 0x9B, 0xC5,
    0x84, 0xDA, 0x38, 0x66, 0xE5, 0xBB, 0x59, 0x07,
    0xDB, 0x85, 0x67, 0x39, 0xBA, 0xE4, 0x06, 0x58,
    0x19, 0x47, 0xA5, 0xFB, 0x78, 0x26, 0xC4, 0x9A,
    0x65, 0x3B, 0xD9, 0x87, 0x04, 0x5A, 0xB8, 0xE6,
    0xA7, 0xF9, 0x1B, 0x45, 0xC6, 0x98, 0x7A, 0x24,
    0xF8, 0xA6, 0x44, 0x1A, 0x99, 0xC7, 0x25, 0x7B,
    0x3A, 0x64, 0x86, 0xD8, 0x5B, 0x05, 0xE7, 0xB9,
    0x8C, 0xD2, 0x30, 0x6E, 0xED, 0xB3, 0x51, 0x0F,
    0x4E, 0x10, 0xF2, 0xAC, 0x2F, 0x71, 0x93, 0xCD,
    0x11, 0x4F, 0xAD, 0xF3, 0x70, 0x2E, 0xCC, 0x92,
    0xD3, 0x8D, 0x6F, 0x31, 0xB2, 0xEC, 0x0E, 0x50,
    0xAF, 0xF1, 0x13, 0x4D, 0xCE, 0x90, 0x72, 0x2C,
    0x6D, 0x33, 0xD1, 0x8F, 0x0C, 0x52, 0xB0, 0xEE,
    0x32, 0x6C, 0x8E, 0xD0, 0x53, 0x0D, 0xEF, 0xB1,
    0xF0, 0xAE, 0x4C, 0x12, 0x91, 0xCF, 0x2D, 0x73,
    0xCA, 0x94, 0x76, 0x28, 0xAB, 0xF5, 0x17, 0x49,
    0x08, 0x56, 0xB4, 0xEA, 0x69, 0x37, 0xD5, 0x8B,
    0x57, 0x09, 0xEB, 0xB5, 0x36, 0x68, 0x8A, 0xD4,
    0x95, 0xCB, 0x29, 0x77, 0xF4, 0xAA, 0x48, 0x16,
    0xE9, 0xB7, 0x55, 0x0B, 0x88, 0xD6, 0x34, 0x6A,
    0x2B, 0x75, 0x97, 0xC9, 0x4A, 0x14, 0xF6, 0xA8,
    0x74, 0x2A, 0xC8, 0x96, 0x15, 0x4B, 0xA9, 0xF7,
    0xB6, 0xE8, 0x0A, 0x54, 0xD7, 0x89, 0x6B, 0x35,
])


def calculate_checksum(data: bytes, mode: ChecksumMode = ChecksumMode.FIXED) -> int:
    """计算校验码.
    
    Args:
        data: 需要计算校验的数据
        mode: 校验模式
        
    Returns:
        校验码
    """
    if mode == ChecksumMode.FIXED:
        return StatusCode.FIXED_CHECKSUM
    elif mode == ChecksumMode.XOR:
        checksum = 0
        for byte in data:
            checksum ^= byte
        return checksum
    elif mode == ChecksumMode.CRC8:
        crc8 = data[0]
        for i in range(1, len(data)):
            crc8 = CRC8_TABLE[crc8 ^ data[i]]
        return crc8
    else:
        return StatusCode.FIXED_CHECKSUM


def add_checksum(data: bytes, mode: ChecksumMode = ChecksumMode.FIXED) -> bytes:
    """添加校验码到数据末尾.
    
    Args:
        data: 原始数据
        mode: 校验模式
        
    Returns:
        带校验码的数据
    """
    checksum = calculate_checksum(data, mode)
    return data + bytes([checksum])
