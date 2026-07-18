# Emm Stepper - ZDT X42S 第二代闭环步进电机控制库

基于 **ZDT_X42S第二代闭环步进电机用户手册V1.0.3_251224**，仅支持 **Emm固件**,作者测试电机的固件为`ZDT_X42S_V1.0.7_260203`  

## 参考文档

- [ZDT_X42S第二代闭环步进电机用户手册V1.0.3_251224](./ZDT_X42S第二代闭环步进电机用户手册V1.0.3_251224.pdf)
- [lyehe/ZDT_stepper](https://github.com/lyehe/ZDT_stepper) - 本项目参考其架构风格开发

## 目录

- [特性](#特性)
- [安装](#安装)
- [快速开始](#快速开始)
- [API参考](#api参考)
  - [EmmDevice类](#emmdevice类)
  - [参数类](#参数类)
  - [枚举类型](#枚举类型)
- [使用示例](#使用示例)
- [注意事项](#注意事项)

## 特性

- ✅ 支持串口TTL/RS485通讯
- ✅ 支持多电机控制（同一串口不同地址）
- ✅ 速度模式控制（0-3000 RPM）
- ✅ 位置模式控制（脉冲数/角度/圈数）
- ✅ 原点回零功能（单圈就近/方向回零、多圈碰撞/限位回零）
- ✅ 堵转检测与保护
- ✅ 读取电机状态（位置、速度、电流、温度等）
- ✅ 参数配置（细分、电流、PID等）

## 安装

本项目已发布到 PyPI，推荐直接使用 pip 安装，无需下载源码：

```bash
pip install emm_stepper
```

该命令会自动安装所需的依赖库（如 `pyserial`）。

### 导入库

```python
from serial import Serial
from emm_stepper import (
    EmmDevice,
    Direction,
    MotionMode,
    HomingMode,
    ChecksumMode,
)
```

## 快速开始

```python
from serial import Serial
from emm_stepper import EmmDevice, Direction

# 1. 创建串口连接
ser = Serial('COM9', 115200, timeout=0.1)

# 2. 创建电机实例
motor = EmmDevice(ser, address=1)

# 3. 使能电机
motor.enable()

# 4. 速度模式运动（100 RPM，顺时针）
motor.jog(speed=100, direction=Direction.CW, acceleration=10)

# 5. 等待2秒
import time
time.sleep(2)

# 6. 停止
motor.stop()

# 7. 位置模式运动（转动一圈）
motor.move_pulses(pulse_count=3200, speed=200, acceleration=20)
motor.wait_for_position(timeout=10)

# 8. 失能电机
motor.disable()

# 9. 关闭串口
ser.close()
```

## API参考

### EmmDevice类

#### 初始化

```python
EmmDevice(
    serial_connection: Serial,  # 串口连接对象
    address: int = 1,           # 电机地址 (1-255)
    checksum_mode: ChecksumMode = ChecksumMode.FIXED,  # 校验模式
    delay: Optional[float] = None,  # 通讯延迟(秒)
    auto_test: bool = True,     # 是否自动测试连接
)
```

**参数说明：**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| serial_connection | Serial | 必填 | pyserial的Serial对象 |
| address | int | 1 | 电机地址，范围1-255 |
| checksum_mode | ChecksumMode | FIXED | 校验模式：FIXED(0x6B)、XOR、CRC8 |
| delay | float | None | 命令间延迟时间 |
| auto_test | bool | True | 初始化时是否测试连接 |

#### 多电机控制

```python
from serial import Serial
from emm_stepper import EmmDevice

# 创建串口连接（共享）
ser = Serial('COM9', 115200, timeout=0.1)

# 创建多个电机实例（不同地址）
motor1 = EmmDevice(ser, address=1)
motor2 = EmmDevice(ser, address=2)
motor3 = EmmDevice(ser, address=3)

# 分别控制
motor1.jog(speed=100)
motor2.jog(speed=200)
motor3.jog(speed=300)

# 关闭串口（由用户管理）
ser.close()
```

---

### 触发动作命令

#### calibrate_encoder()
触发编码器校准。电机将缓慢正转一圈然后反转一圈对编码器进行线性化校准。

```python
success = motor.calibrate_encoder()
```

#### restart()
重启电机。

```python
success = motor.restart()
```

#### zero_position()
将当前位置角度清零。

```python
success = motor.zero_position()
```

#### clear_protection()
解除堵转/过热/过流保护。

```python
success = motor.clear_protection()
```

#### factory_reset()
恢复出厂设置。注意：恢复后需要断电重新上电，再空载校准电机编码器。

```python
success = motor.factory_reset()
```

---

### 运动控制命令

#### enable(sync=False)
使能电机（锁轴）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| sync | bool | False | 是否使用同步模式 |

```python
motor.enable()
```

#### disable(sync=False)
失能电机（松轴）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| sync | bool | False | 是否使用同步模式 |

```python
motor.disable()
```

#### jog(speed, direction, acceleration, sync)
速度模式运动。电机以指定速度持续运动，直到收到停止命令。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| speed | int | 100 | 速度 (0-3000 RPM) |
| direction | Direction | CW | 运动方向 |
| acceleration | int | 10 | 加速度档位 (0-255) |
| sync | bool | False | 是否使用同步模式 |

```python
# 顺时针100RPM
motor.jog(speed=100, direction=Direction.CW, acceleration=10)

# 逆时针200RPM
motor.jog(speed=200, direction=Direction.CCW, acceleration=20)
```

#### move_pulses(pulse_count, speed, direction, acceleration, motion_mode, sync)
位置模式运动（脉冲数）。默认16细分下，3200个脉冲=一圈360°。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| pulse_count | int | 必填 | 脉冲数（正数CW，负数CCW） |
| speed | int | 100 | 速度 (0-3000 RPM) |
| direction | Direction | None | 运动方向（None则根据pulse_count正负判断） |
| acceleration | int | 10 | 加速度档位 (0-255) |
| motion_mode | MotionMode | RELATIVE_LAST | 运动模式 |
| sync | bool | False | 是否使用同步模式 |

```python
# 转动一圈（3200脉冲）
motor.move_pulses(pulse_count=3200, speed=200, acceleration=20)

# 反向转动半圈
motor.move_pulses(pulse_count=-1600, speed=200, acceleration=20)
```

#### move_degrees(degrees, speed, acceleration, motion_mode, microstep, motor_type, sync)
位置模式运动（角度）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| degrees | float | 必填 | 角度（正数CW，负数CCW） |
| speed | int | 100 | 速度 (0-3000 RPM) |
| acceleration | int | 10 | 加速度档位 (0-255) |
| motion_mode | MotionMode | RELATIVE_LAST | 运动模式 |
| microstep | int | 16 | 细分值 |
| motor_type | MotorType | DEGREE_18 | 步距角类型（影响脉冲换算） |
| sync | bool | False | 是否使用同步模式 |

```python
# 转动90度
motor.move_degrees(degrees=90, speed=200, acceleration=20)

# 反向转动180度
motor.move_degrees(degrees=-180, speed=200, acceleration=20)
```

#### move_revolutions(revolutions, speed, acceleration, motion_mode, microstep, motor_type, sync)
位置模式运动（圈数）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| revolutions | float | 必填 | 圈数（正数CW，负数CCW） |
| speed | int | 100 | 速度 (0-3000 RPM) |
| acceleration | int | 10 | 加速度档位 (0-255) |
| motion_mode | MotionMode | RELATIVE_LAST | 运动模式 |
| microstep | int | 16 | 细分值 |
| motor_type | MotorType | DEGREE_18 | 步距角类型（影响脉冲换算） |
| sync | bool | False | 是否使用同步模式 |

```python
# 转动2圈
motor.move_revolutions(revolutions=2, speed=300, acceleration=30)

# 反向转动0.5圈
motor.move_revolutions(revolutions=-0.5, speed=300, acceleration=30)
```

#### stop(sync=False)
立即停止电机。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| sync | bool | False | 是否使用同步模式 |

```python
motor.stop()
```

#### sync_move(device_params) [静态方法]
触发多机同步运动。使用广播地址发送，使所有缓存了命令的电机同步开始执行。

```python
# 先发送同步命令给各电机
motor1.jog(speed=100, sync=True)
motor2.jog(speed=200, sync=True)

# 触发同步运动
EmmDevice.sync_move(motor1.device_params)
```

---

### 原点回零命令

#### set_home_zero(store=True)
设置单圈回零的零点位置。将当前位置设置为单圈回零的零点位置。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| store | bool | True | 是否存储（掉电不丢失） |

```python
motor.set_home_zero(store=True)
```

#### home(mode, sync)
触发回零。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| mode | HomingMode | NEAREST | 回零模式 |
| sync | bool | False | 是否使用同步模式 |

**回零模式：**
| 模式 | 值 | 说明 |
|------|-----|------|
| NEAREST | 0 | 单圈就近回零 |
| DIRECTION | 1 | 单圈方向回零 |
| SENSORLESS | 2 | 无限位碰撞回零 |
| ENDSTOP | 3 | 限位开关回零 |
| ABS_ZERO | 4 | 回到绝对位置坐标零点 |
| LAST_POWER_OFF | 5 | 回到上次掉电位置 |

```python
# 单圈就近回零
motor.home(mode=HomingMode.NEAREST)

# 无限位碰撞回零
motor.home(mode=HomingMode.SENSORLESS)
```

#### stop_home()
强制中断并退出回零操作。

```python
motor.stop_home()
```

#### get_homing_status()
读取回零状态标志。

**返回值：** `HomingStatus` 对象

| 属性 | 类型 | 说明 |
|------|------|------|
| encoder_ready | bool | 编码器就绪 |
| calibrated | bool | 校准表就绪 |
| is_homing | bool | 正在回零 |
| homing_failed | bool | 回零失败 |
| over_temp | bool | 过热保护 |
| over_current | bool | 过流保护 |
| homing_state | str | 回零状态字符串 |

```python
status = motor.get_homing_status()
print(f"编码器就绪: {status.encoder_ready}")
print(f"已校准: {status.calibrated}")
print(f"回零状态: {status.homing_state}")
```

#### get_homing_params()
读取回零参数。

**返回值：** `HomingParams` 对象

```python
params = motor.get_homing_params()
print(f"回零模式: {params.homing_mode}")
print(f"回零速度: {params.homing_speed} RPM")
```

#### set_homing_params(params, store)
修改回零参数。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| params | HomingParams | 必填 | 回零参数 |
| store | bool | True | 是否存储 |

```python
from emm_stepper.parameters import HomingParams

params = HomingParams(
    homing_mode=HomingMode.SENSORLESS,
    homing_speed=60,
    homing_timeout=15000,
    collision_speed=300,
    collision_current=1000,
    collision_time=100,
)
motor.set_homing_params(params, store=True)
```

---

### 读取系统参数命令

#### get_version()
读取固件版本和硬件版本。

**返回值：** `VersionParams` 对象

| 属性 | 类型 | 说明 |
|------|------|------|
| firmware_version | int | 固件版本号 |
| firmware_version_str | str | 固件版本字符串（如"V1.0.7"） |
| hw_series | int | 硬件系列（0=X系列，1=Y系列） |
| hw_series_str | str | 硬件系列字符串 |
| hw_type | int | 硬件类型 |
| hw_type_str | str | 硬件类型字符串（如"X42"） |
| hw_version | int | 硬件版本号 |

```python
version = motor.get_version()
print(f"固件版本: {version.firmware_version_str}")
print(f"硬件类型: {version.hw_type_str}")
```

#### get_motor_rh()
读取相电阻和相电感。

**返回值：** `MotorRHParams` 对象

| 属性 | 类型 | 说明 |
|------|------|------|
| phase_resistance | int | 相电阻 (mΩ) |
| phase_inductance | int | 相电感 (uH) |

```python
rh = motor.get_motor_rh()
print(f"相电阻: {rh.phase_resistance} mΩ")
print(f"相电感: {rh.phase_inductance} uH")
```

#### get_bus_voltage()
读取总线电压。

**返回值：** `int` - 总线电压 (mV)

```python
voltage = motor.get_bus_voltage()
print(f"总线电压: {voltage} mV ({voltage/1000:.2f} V)")
```

#### get_bus_current()
读取总线电流。

**返回值：** `int` - 总线电流 (mA)

```python
current = motor.get_bus_current()
print(f"总线电流: {current} mA")
```

#### get_phase_current()
读取相电流。

**返回值：** `int` - 相电流 (mA)

```python
current = motor.get_phase_current()
print(f"相电流: {current} mA")
```

#### get_encoder()
读取线性化编码器值。

**返回值：** `int` - 编码器值 (0-65535表示0-360°)

```python
encoder = motor.get_encoder()
angle = (encoder * 360) / 65536
print(f"编码器值: {encoder}, 角度: {angle:.2f}°")
```

#### get_encoder_degrees()
读取编码器角度。

**返回值：** `float` - 编码器角度 (度)

```python
angle = motor.get_encoder_degrees()
print(f"编码器角度: {angle:.2f}°")
```

#### get_pulse_count()
读取输入脉冲数。

**返回值：** `int` - 输入脉冲数（带符号）

```python
pulses = motor.get_pulse_count()
print(f"输入脉冲数: {pulses}")
```

#### get_target_position()
读取电机目标位置。

**返回值：** `float` - 目标位置角度 (度)

```python
position = motor.get_target_position()
print(f"目标位置: {position:.2f}°")
```

#### get_realtime_target()
读取电机实时设定的目标位置。

**返回值：** `float` - 实时设定目标位置角度 (度)

```python
position = motor.get_realtime_target()
print(f"实时设定目标: {position:.2f}°")
```

#### get_realtime_speed()
读取电机实时转速。

**返回值：** `int` - 实时转速 (RPM，带符号)

```python
speed = motor.get_realtime_speed()
print(f"实时转速: {speed} RPM")
```

#### get_realtime_position()
读取电机实时位置。

**返回值：** `float` - 实时位置角度 (度)

```python
position = motor.get_realtime_position()
print(f"实时位置: {position:.2f}°")
```

#### get_position_error()
读取电机位置误差。

**返回值：** `float` - 位置误差角度 (度)

```python
error = motor.get_position_error()
print(f"位置误差: {error:.4f}°")
```

#### get_temperature()
读取驱动温度。

**返回值：** `int` - 温度 (°C)

```python
temp = motor.get_temperature()
print(f"驱动温度: {temp}°C")
```

#### get_motor_status()
读取电机状态标志。

**返回值：** `MotorStatus` 对象

| 属性 | 类型 | 说明 |
|------|------|------|
| enabled | bool | 使能状态 |
| position_reached | bool | 位置到达 |
| stall_detected | bool | 堵转标志 |
| stall_protected | bool | 堵转保护 |
| left_limit | bool | 左限位开关状态 |
| right_limit | bool | 右限位开关状态 |
| power_off_flag | bool | 掉电标志 |

```python
status = motor.get_motor_status()
print(f"使能状态: {'已使能' if status.enabled else '未使能'}")
print(f"位置到达: {'是' if status.position_reached else '否'}")
print(f"堵转标志: {'是' if status.stall_detected else '否'}")
print(f"堵转保护: {'已触发' if status.stall_protected else '未触发'}")
```

#### get_home_motor_status() / get_io_status() / timed_return()
- `get_home_motor_status()`：回零状态 + 电机状态（`HomeMotorStatus`）
- `get_io_status()`：En/Step/Dir 引脚电平（`IOStatus`）
- `timed_return(info_code, interval_ms)`：定时返回；`interval_ms=0` 停止

```python
from emm_stepper import Code

combo = motor.get_home_motor_status()
io = motor.get_io_status()
motor.timed_return(Code.GET_REALTIME_POSITION, interval_ms=10)
motor.timed_return(Code.GET_REALTIME_POSITION, interval_ms=0)  # 停止
```

#### get_pid()
读取PID参数。

**返回值：** `PIDParams` 对象

| 属性 | 类型 | 说明 |
|------|------|------|
| kp | int | 比例系数 |
| ki | int | 积分系数 |
| kd | int | 微分系数 |

```python
pid = motor.get_pid()
print(f"Kp: {pid.kp}, Ki: {pid.ki}, Kd: {pid.kd}")
```

#### get_config()
读取驱动配置参数。

**返回值：** `ConfigParams` 对象

| 属性 | 类型 | 说明 |
|------|------|------|
| motor_type | MotorType | 电机类型 |
| microstep | int | 细分值 |
| open_loop_current | int | 开环模式工作电流 (mA) |
| closed_loop_current | int | 闭环模式最大电流 (mA) |
| stall_protect | StallProtect | 堵转保护 |
| stall_speed | int | 堵转检测转速 (RPM) |
| stall_current | int | 堵转检测电流 (mA) |
| stall_time | int | 堵转检测时间 (ms) |
| position_window | int | 位置到达窗口 (*0.1度) |

```python
config = motor.get_config()
print(f"细分值: {config.microstep}")
print(f"闭环最大电流: {config.closed_loop_current} mA")
print(f"位置到达窗口: {config.position_window_deg}°")
```

#### get_system_status()
读取系统状态参数。

**返回值：** `SystemStatusParams` 对象

```python
status = motor.get_system_status()
print(f"总线电压: {status.bus_voltage} mV")
print(f"相电流: {status.phase_current} mA")
print(f"实时位置: {status.realtime_position_deg:.2f}°")
print(f"实时转速: {status.realtime_speed_rpm} RPM")
```

---

### 设置命令

#### set_id(new_id, store)
修改电机ID/地址。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| new_id | int | 必填 | 新ID (1-255) |
| store | bool | True | 是否存储 |

```python
motor.set_id(new_id=2, store=True)
```

#### set_microstep(microstep, store)
修改细分值。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| microstep | int | 必填 | 细分值 (1-256) |
| store | bool | True | 是否存储 |

```python
motor.set_microstep(microstep=32, store=True)
```

#### set_loop_mode(closed_loop, store)
修改开环/闭环控制模式。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| closed_loop | bool | True | True为闭环，False为开环 |
| store | bool | True | 是否存储 |

```python
motor.set_loop_mode(closed_loop=True, store=True)
```

#### set_open_loop_current(current_ma, store)
修改开环模式工作电流。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| current_ma | int | 必填 | 电流 (0-5000 mA) |
| store | bool | True | 是否存储 |

```python
motor.set_open_loop_current(current_ma=1200, store=True)
```

#### set_closed_loop_current(current_ma, store)
修改闭环模式最大电流。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| current_ma | int | 必填 | 电流 (0-5000 mA) |
| store | bool | True | 是否存储 |

```python
motor.set_closed_loop_current(current_ma=3000, store=True)
```

#### set_pid(params, store)
修改PID参数。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| params | PIDParams | 必填 | PID参数 |
| store | bool | True | 是否存储 |

```python
from emm_stepper.parameters import PIDParams

params = PIDParams(kp=18000, ki=10, kd=18000)
motor.set_pid(params, store=True)
```

#### set_motor_direction(direction, store)
修改电机运动正方向。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| direction | Direction | CW | 运动方向 |
| store | bool | True | 是否存储 |

```python
motor.set_motor_direction(direction=Direction.CW, store=True)
```

#### set_position_window(window_deg, store) / get_position_window()
修改/读取位置到达窗口（度）。

```python
motor.set_position_window(window_deg=0.8, store=True)
print(motor.get_position_window())
```

#### set_heartbeat_time(time_ms, store) / get_heartbeat_time()
修改/读取心跳保护时间（ms，0=关闭）。

```python
motor.set_heartbeat_time(time_ms=1000, store=True)
print(motor.get_heartbeat_time())
```

#### 其他驱动参数读写（V1.0.3 Emm）
| 方法 | 说明 |
|------|------|
| `set_power_off_flag(flag)` | 修改掉电标志 |
| `get_option_status()` | 选项参数状态（部分固件字段可能不可信） |
| `set_motor_type(motor_type, store)` | 电机类型 `0x19`/`0x32` |
| `set_firmware_type(firmware_type, store)` | 固件类型 X/Emm/狂暴 |
| `get_dmx512_params()` / `set_dmx512_params(params, store)` | DMX512 参数 |
| `get_protection_threshold()` / `set_protection_threshold(params, store)` | 过热过流阈值 |
| `get_integral_stiffness()` / `set_integral_stiffness(value, store)` | 积分限幅 |
| `get_collision_return_angle()` / `set_collision_return_angle(angle_deg, store)` | 碰撞回零返回角 |
| `set_lock_param(level, store)` | 锁定修改参数等级 |
| `multi_motor(ser, frames, expect_ack=...)` | 多电机命令（静态） |
| `build_frame(body)` | 构建含子校验的帧（静态） |

```python
from emm_stepper import MotorType, LockParamLevel

motor.set_motor_type(MotorType.DEGREE_18, store=True)
motor.set_lock_param(LockParamLevel.UNLOCKED, store=True)

frame = EmmDevice.build_frame(bytes([2, 0x36]))  # 地址2读实时位置
EmmDevice.multi_motor(ser, [frame], expect_ack=False)
```

#### set_auto_run(params)
存储一组速度参数，上电自动运行。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| params | AutoRunParams | 必填 | 自动运行参数 |

```python
from emm_stepper.parameters import AutoRunParams

params = AutoRunParams(
    store=True,
    direction=Direction.CW,
    speed=600,
    acceleration=100,
    enable_en_control=True,
)
motor.set_auto_run(params)
```

#### set_config(params, store)
修改驱动配置参数。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| params | ConfigParams | 必填 | 配置参数 |
| store | bool | True | 是否存储 |

```python
config = motor.get_config()
config.microstep = 32
config.closed_loop_current = 3500
motor.set_config(config, store=True)
```

#### set_scale_input(enable, store)
修改命令速度值是否缩小10倍输入。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| enable | bool | False | 是否使能（使能后输入1RPM实际为0.1RPM） |
| store | bool | True | 是否存储 |

```python
motor.set_scale_input(enable=True, store=True)
```

#### set_lock_button(lock, store)
修改锁定按键功能。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| lock | bool | False | 是否锁定 |
| store | bool | True | 是否存储 |

```python
motor.set_lock_button(lock=True, store=True)
```

#### broadcast_get_id(serial_connection) [静态方法]
广播读取ID地址。当忘记电机ID地址时，可以单独接线该电机，广播读取该电机的地址。

```python
motor_id = EmmDevice.broadcast_get_id(ser)
print(f"电机ID: {motor_id}")
```

---

### 便捷方法

#### is_enabled()
检查电机是否使能。

**返回值：** `bool`

```python
if motor.is_enabled():
    print("电机已使能")
```

#### is_position_reached()
检查是否到达目标位置。

**返回值：** `bool`

```python
if motor.is_position_reached():
    print("已到达目标位置")
```

#### is_stalled()
检查是否堵转。

**返回值：** `bool`

```python
if motor.is_stalled():
    print("电机堵转！")
    motor.clear_protection()
```

#### wait_for_position(timeout, poll_interval)
等待电机到达目标位置。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| timeout | float | 30.0 | 超时时间 (秒) |
| poll_interval | float | 0.1 | 轮询间隔 (秒) |

**返回值：** `bool` - True表示到达位置，False表示超时

```python
motor.move_pulses(pulse_count=3200, speed=200)
if motor.wait_for_position(timeout=10):
    print("到达目标位置")
else:
    print("超时未到达")
```

---

## 参数类

### Direction (枚举)
运动方向。

| 值 | 说明 |
|-----|------|
| CW | 顺时针 |
| CCW | 逆时针 |

### MotionMode (枚举)
位置模式运动类型。

| 值 | 说明 |
|-----|------|
| RELATIVE_LAST | 相对于上次目标位置 |
| ABSOLUTE | 绝对位置 |
| RELATIVE_CURRENT | 相对于当前位置 |

### HomingMode (枚举)
回零模式。

| 值 | 说明 |
|-----|------|
| NEAREST | 单圈就近回零 |
| DIRECTION | 单圈方向回零 |
| SENSORLESS | 无限位碰撞回零 |
| ENDSTOP | 限位开关回零 |
| ABS_ZERO | 回到绝对位置坐标零点 |
| LAST_POWER_OFF | 回到上次掉电位置 |

### ChecksumMode (枚举)
校验模式。

| 值 | 说明 |
|-----|------|
| FIXED | 固定值0x6B |
| XOR | 异或校验 |
| CRC8 | CRC8校验 |

### MotorType (枚举)
电机步距角类型（配置字节，Emm）。

| 值 | 字节 | 说明 |
|-----|------|------|
| DEGREE_18 | 0x19 | 1.8° 步进电机（默认） |
| DEGREE_09 | 0x32 | 0.9° 步进电机 |

### StallProtect (枚举)
堵转保护模式。

| 值 | 说明 |
|-----|------|
| DISABLED | 禁用 |
| ENABLED | 启用 |

---

## 使用示例

### 基本速度控制

```python
from serial import Serial
from emm_stepper import EmmDevice, Direction

ser = Serial('COM9', 115200, timeout=0.1)
motor = EmmDevice(ser, address=1)

# 使能电机
motor.enable()

# 顺时针100RPM运行
motor.jog(speed=100, direction=Direction.CW, acceleration=10)

import time
time.sleep(3)

# 停止
motor.stop()

# 失能电机
motor.disable()
ser.close()
```

### 位置控制

```python
from serial import Serial
from emm_stepper import EmmDevice, MotionMode

ser = Serial('COM9', 115200, timeout=0.1)
motor = EmmDevice(ser, address=1)

motor.enable()

# 转动90度
motor.move_degrees(degrees=90, speed=200, acceleration=20)
motor.wait_for_position(timeout=10)

# 转动到绝对位置180度
motor.move_degrees(degrees=180, speed=200, motion_mode=MotionMode.ABSOLUTE)
motor.wait_for_position(timeout=10)

# 转动2圈
motor.move_revolutions(revolutions=2, speed=300)
motor.wait_for_position(timeout=10)

motor.disable()
ser.close()
```

### 堵转检测与处理

```python
from serial import Serial
from emm_stepper import EmmDevice, Direction
import time

ser = Serial('COM9', 115200, timeout=0.1)
motor = EmmDevice(ser, address=1)

motor.enable()

# 以100RPM运行
motor.jog(speed=100, direction=Direction.CW, acceleration=10)

# 监测堵转
while True:
    time.sleep(0.1)
    if motor.is_stalled():
        print("检测到堵转！")
        motor.stop()
        motor.clear_protection()
        
        # 反向转动3200脉冲
        motor.move_pulses(
            pulse_count=3200,
            speed=100,
            direction=Direction.CCW,
            acceleration=10
        )
        motor.wait_for_position(timeout=10)
        break

motor.disable()
ser.close()
```

### 原点回零

```python
from serial import Serial
from emm_stepper import EmmDevice, HomingMode
import time

ser = Serial('COM9', 115200, timeout=0.1)
motor = EmmDevice(ser, address=1)

motor.enable()

# 设置当前位置为零点
motor.set_home_zero(store=True)

# 移动一段距离
motor.move_degrees(degrees=180, speed=200)
motor.wait_for_position(timeout=10)

# 回零
motor.home(mode=HomingMode.NEAREST)

# 等待回零完成
while True:
    time.sleep(0.1)
    status = motor.get_homing_status()
    if not status.is_homing:
        if status.homing_failed:
            print("回零失败")
        else:
            print("回零完成")
        break

motor.disable()
ser.close()
```

### 多电机同步控制

```python
from serial import Serial
from emm_stepper import EmmDevice, Direction

ser = Serial('COM9', 115200, timeout=0.1)

# 创建多个电机实例
motor1 = EmmDevice(ser, address=1)
motor2 = EmmDevice(ser, address=2)

motor1.enable()
motor2.enable()

# 发送同步命令（不立即执行）
motor1.jog(speed=100, direction=Direction.CW, sync=True)
motor2.jog(speed=200, direction=Direction.CCW, sync=True)

# 触发同步执行
EmmDevice.sync_move(motor1.device_params)

import time
time.sleep(3)

# 同步停止
motor1.stop(sync=True)
motor2.stop(sync=True)
EmmDevice.sync_move(motor1.device_params)

motor1.disable()
motor2.disable()
ser.close()
```

### 读取电机状态

```python
from serial import Serial
from emm_stepper import EmmDevice

ser = Serial('COM9', 115200, timeout=0.1)
motor = EmmDevice(ser, address=1)

# 读取版本信息
version = motor.get_version()
print(f"固件版本: {version.firmware_version_str}")
print(f"硬件类型: {version.hw_type_str}")

# 读取电气参数
print(f"总线电压: {motor.get_bus_voltage()} mV")
print(f"相电流: {motor.get_phase_current()} mA")
print(f"驱动温度: {motor.get_temperature()}°C")

# 读取位置信息
print(f"编码器角度: {motor.get_encoder_degrees():.2f}°")
print(f"实时位置: {motor.get_realtime_position():.2f}°")
print(f"实时转速: {motor.get_realtime_speed()} RPM")

# 读取电机状态
status = motor.get_motor_status()
print(f"使能状态: {'已使能' if status.enabled else '未使能'}")
print(f"位置到达: {'是' if status.position_reached else '否'}")
print(f"堵转标志: {'是' if status.stall_detected else '否'}")

ser.close()
```

### 修改配置参数

```python
from serial import Serial
from emm_stepper import EmmDevice
from emm_stepper.parameters import PIDParams

ser = Serial('COM9', 115200, timeout=0.1)
motor = EmmDevice(ser, address=1)

# 修改细分值
motor.set_microstep(microstep=32, store=True)

# 修改闭环电流
motor.set_closed_loop_current(current_ma=3000, store=True)

# 修改PID参数
pid = PIDParams(kp=18000, ki=10, kd=18000)
motor.set_pid(pid, store=True)

# 修改位置到达窗口
motor.set_position_window(window_deg=0.5, store=True)

# 读取并修改配置
config = motor.get_config()
print(f"当前细分: {config.microstep}")
config.microstep = 64
motor.set_config(config, store=True)

ser.close()
```

---

## 注意事项

### 通讯设置

1. **波特率**：默认115200，支持9600-921600
2. **超时时间**：建议设置0.1秒以上
3. **校验模式**：默认使用固定值0x6B，需与电机设置一致

### 电机使用

1. **首次使用**：需要进行编码器校准（`calibrate_encoder()`）
2. **堵转保护**：触发后需要调用`clear_protection()`解除
3. **位置模式**：运动完成后建议使用`wait_for_position()`等待到位
4. **速度范围**：0-3000 RPM
5. **加速度范围**：0-255档位

### 多电机控制

1. **地址设置**：每个电机需要设置不同的地址（1-255）
2. **串口共享**：多个电机可以共享同一个串口连接
3. **同步运动**：使用`sync=True`参数发送命令，然后调用`sync_move()`触发

### 回零功能

1. **单圈回零**：需要先设置零点位置（`set_home_zero()`）
2. **碰撞回零**：需要设置合适的碰撞检测参数
3. **限位回零**：需要正确接线限位开关

### 错误处理

```python
try:
    motor = EmmDevice(ser, address=1)
except Exception as e:
    print(f"连接失败: {e}")

# 检查命令执行结果
if not motor.enable():
    print("使能失败")

# 检查堵转
if motor.is_stalled():
    motor.clear_protection()
```

---

## 许可证

MIT License

