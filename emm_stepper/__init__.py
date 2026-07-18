"""ZDT X42S Emm固件步进电机控制库.

基于ZDT_X42S第二代闭环步进电机用户手册V1.0.3_251224开发。
仅支持Emm固件通讯协议。
"""

from .device import EmmDevice
from .configs import (
    Address,
    ChecksumMode,
    Direction,
    SyncFlag,
    StoreFlag,
    MotionMode,
    HomingMode,
    MotorType,
    FirmwareType,
    LockParamLevel,
    Code,
)
from .parameters import (
    DeviceParams,
    JogParams,
    PositionParams,
    HomingParams,
    ProtectionThreshold,
    DMX512Params,
    IOStatus,
    OptionStatus,
    HomeMotorStatus,
)

__version__ = "1.0.2"
__all__ = [
    "EmmDevice",
    "Address",
    "ChecksumMode",
    "Direction",
    "SyncFlag",
    "StoreFlag",
    "MotionMode",
    "HomingMode",
    "MotorType",
    "FirmwareType",
    "LockParamLevel",
    "Code",
    "DeviceParams",
    "JogParams",
    "PositionParams",
    "HomingParams",
    "ProtectionThreshold",
    "DMX512Params",
    "IOStatus",
    "OptionStatus",
    "HomeMotorStatus",
]
