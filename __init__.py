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
)
from .parameters import (
    DeviceParams,
    JogParams,
    PositionParams,
    HomingParams,
)

__version__ = "1.0.0"
__all__ = [
    "EmmDevice",
    "Address",
    "ChecksumMode",
    "Direction",
    "SyncFlag",
    "StoreFlag",
    "MotionMode",
    "HomingMode",
    "DeviceParams",
    "JogParams",
    "PositionParams",
    "HomingParams",
]
