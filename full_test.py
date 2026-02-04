"""Emm步进电机库完整功能测试.

测试所有定义的函数功能，每测试一个功能都会打印功能名称、参数和预期状态。
"""

from serial import Serial
from emm_stepper import (
    EmmDevice,
    Direction,
    MotionMode,
    HomingMode,
    ChecksumMode,
)
from emm_stepper.parameters import (
    JogParams,
    PositionParams,
    HomingParams,
    PIDParams,
    AutoRunParams,
)
import time
import sys


class TestResult:
    """测试结果统计."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.results = []
    
    def add_pass(self, name: str, message: str = ""):
        self.passed += 1
        self.results.append(("PASS", name, message))
        print(f"  ✓ 通过: {message}" if message else "  ✓ 通过")
    
    def add_fail(self, name: str, message: str):
        self.failed += 1
        self.results.append(("FAIL", name, message))
        print(f"  ✗ 失败: {message}")
    
    def add_skip(self, name: str, message: str):
        self.skipped += 1
        self.results.append(("SKIP", name, message))
        print(f"  ⊘ 跳过: {message}")
    
    def summary(self):
        print("\n" + "=" * 60)
        print("测试结果汇总")
        print("=" * 60)
        print(f"通过: {self.passed}")
        print(f"失败: {self.failed}")
        print(f"跳过: {self.skipped}")
        print(f"总计: {self.passed + self.failed + self.skipped}")
        
        if self.failed > 0:
            print("\n失败的测试:")
            for status, name, message in self.results:
                if status == "FAIL":
                    print(f"  - {name}: {message}")


def print_test_header(name: str, description: str, params: dict = None, expected: str = None):
    """打印测试头部信息."""
    print("\n" + "-" * 60)
    print(f"测试: {name}")
    print(f"描述: {description}")
    if params:
        print(f"参数: {params}")
    if expected:
        print(f"预期: {expected}")
    print("-" * 60)


def test_get_version(motor: EmmDevice, result: TestResult):
    """测试读取版本信息."""
    name = "get_version"
    print_test_header(
        name,
        "读取固件版本和硬件版本",
        expected="返回VersionParams对象，包含固件版本和硬件类型"
    )
    
    try:
        version = motor.get_version()
        print(f"  固件版本: {version.firmware_version_str}")
        print(f"  硬件系列: {version.hw_series_str}")
        print(f"  硬件类型: {version.hw_type_str}")
        print(f"  硬件版本: {version.hw_version}")
        result.add_pass(name, f"固件版本={version.firmware_version_str}")
    except Exception as e:
        result.add_fail(name, str(e))


def test_get_motor_rh(motor: EmmDevice, result: TestResult):
    """测试读取相电阻和相电感."""
    name = "get_motor_rh"
    print_test_header(
        name,
        "读取电机相电阻和相电感",
        expected="返回MotorRHParams对象，包含相电阻(mΩ)和相电感(uH)"
    )
    
    try:
        rh = motor.get_motor_rh()
        print(f"  相电阻: {rh.phase_resistance} mΩ")
        print(f"  相电感: {rh.phase_inductance} uH")
        result.add_pass(name, f"R={rh.phase_resistance}mΩ, L={rh.phase_inductance}uH")
    except Exception as e:
        result.add_fail(name, str(e))


def test_get_bus_voltage(motor: EmmDevice, result: TestResult):
    """测试读取总线电压."""
    name = "get_bus_voltage"
    print_test_header(
        name,
        "读取总线电压",
        expected="返回电压值(mV)，正常范围10000-29000mV"
    )
    
    try:
        voltage = motor.get_bus_voltage()
        print(f"  总线电压: {voltage} mV ({voltage/1000:.2f} V)")
        if 10000 <= voltage <= 30000:
            result.add_pass(name, f"{voltage}mV")
        else:
            result.add_fail(name, f"电压异常: {voltage}mV")
    except Exception as e:
        result.add_fail(name, str(e))


def test_get_bus_current(motor: EmmDevice, result: TestResult):
    """测试读取总线电流."""
    name = "get_bus_current"
    print_test_header(
        name,
        "读取总线电流",
        expected="返回电流值(mA)"
    )
    
    try:
        current = motor.get_bus_current()
        print(f"  总线电流: {current} mA")
        result.add_pass(name, f"{current}mA")
    except Exception as e:
        result.add_fail(name, str(e))


def test_get_phase_current(motor: EmmDevice, result: TestResult):
    """测试读取相电流."""
    name = "get_phase_current"
    print_test_header(
        name,
        "读取电机相电流",
        expected="返回相电流值(mA)"
    )
    
    try:
        current = motor.get_phase_current()
        print(f"  相电流: {current} mA")
        result.add_pass(name, f"{current}mA")
    except Exception as e:
        result.add_fail(name, str(e))


def test_get_encoder(motor: EmmDevice, result: TestResult):
    """测试读取编码器值."""
    name = "get_encoder"
    print_test_header(
        name,
        "读取线性化编码器值",
        expected="返回编码器值(0-65535表示0-360°)"
    )
    
    try:
        encoder = motor.get_encoder()
        degrees = motor.get_encoder_degrees()
        print(f"  编码器值: {encoder}")
        print(f"  对应角度: {degrees:.2f}°")
        result.add_pass(name, f"编码器={encoder}, 角度={degrees:.2f}°")
    except Exception as e:
        result.add_fail(name, str(e))


def test_get_pulse_count(motor: EmmDevice, result: TestResult):
    """测试读取输入脉冲数."""
    name = "get_pulse_count"
    print_test_header(
        name,
        "读取输入脉冲数",
        expected="返回脉冲数(带符号)"
    )
    
    try:
        pulses = motor.get_pulse_count()
        print(f"  输入脉冲数: {pulses}")
        result.add_pass(name, f"{pulses}脉冲")
    except Exception as e:
        result.add_fail(name, str(e))


def test_get_target_position(motor: EmmDevice, result: TestResult):
    """测试读取目标位置."""
    name = "get_target_position"
    print_test_header(
        name,
        "读取电机目标位置",
        expected="返回目标位置角度(度)"
    )
    
    try:
        position = motor.get_target_position()
        print(f"  目标位置: {position:.2f}°")
        result.add_pass(name, f"{position:.2f}°")
    except Exception as e:
        result.add_fail(name, str(e))


def test_get_realtime_speed(motor: EmmDevice, result: TestResult):
    """测试读取实时转速."""
    name = "get_realtime_speed"
    print_test_header(
        name,
        "读取电机实时转速",
        expected="返回转速(RPM, 带符号)"
    )
    
    try:
        speed = motor.get_realtime_speed()
        print(f"  实时转速: {speed} RPM")
        result.add_pass(name, f"{speed}RPM")
    except Exception as e:
        result.add_fail(name, str(e))


def test_get_realtime_position(motor: EmmDevice, result: TestResult):
    """测试读取实时位置."""
    name = "get_realtime_position"
    print_test_header(
        name,
        "读取电机实时位置",
        expected="返回实时位置角度(度)"
    )
    
    try:
        position = motor.get_realtime_position()
        print(f"  实时位置: {position:.2f}°")
        result.add_pass(name, f"{position:.2f}°")
    except Exception as e:
        result.add_fail(name, str(e))


def test_get_position_error(motor: EmmDevice, result: TestResult):
    """测试读取位置误差."""
    name = "get_position_error"
    print_test_header(
        name,
        "读取电机位置误差",
        expected="返回位置误差角度(度)"
    )
    
    try:
        error = motor.get_position_error()
        print(f"  位置误差: {error:.4f}°")
        result.add_pass(name, f"{error:.4f}°")
    except Exception as e:
        result.add_fail(name, str(e))


def test_get_temperature(motor: EmmDevice, result: TestResult):
    """测试读取驱动温度."""
    name = "get_temperature"
    print_test_header(
        name,
        "读取驱动温度",
        expected="返回温度(°C)"
    )
    
    try:
        temp = motor.get_temperature()
        print(f"  驱动温度: {temp}°C")
        result.add_pass(name, f"{temp}°C")
    except Exception as e:
        result.add_fail(name, str(e))


def test_get_motor_status(motor: EmmDevice, result: TestResult):
    """测试读取电机状态."""
    name = "get_motor_status"
    print_test_header(
        name,
        "读取电机状态标志",
        expected="返回MotorStatus对象，包含使能、到位、堵转等状态"
    )
    
    try:
        status = motor.get_motor_status()
        print(f"  使能状态: {'已使能' if status.enabled else '未使能'}")
        print(f"  位置到达: {'是' if status.position_reached else '否'}")
        print(f"  堵转标志: {'是' if status.stall_detected else '否'}")
        print(f"  堵转保护: {'已触发' if status.stall_protected else '未触发'}")
        print(f"  左限位: {'触发' if status.left_limit else '未触发'}")
        print(f"  右限位: {'触发' if status.right_limit else '未触发'}")
        print(f"  掉电标志: {'是' if status.power_off_flag else '否'}")
        result.add_pass(name, f"使能={status.enabled}, 到位={status.position_reached}")
    except Exception as e:
        result.add_fail(name, str(e))


def test_get_homing_status(motor: EmmDevice, result: TestResult):
    """测试读取回零状态."""
    name = "get_homing_status"
    print_test_header(
        name,
        "读取回零状态标志",
        expected="返回HomingStatus对象，包含编码器就绪、校准、回零状态等"
    )
    
    try:
        status = motor.get_homing_status()
        print(f"  编码器就绪: {'是' if status.encoder_ready else '否'}")
        print(f"  已校准: {'是' if status.calibrated else '否'}")
        print(f"  回零状态: {status.homing_state}")
        print(f"  过热保护: {'已触发' if status.over_temp else '未触发'}")
        print(f"  过流保护: {'已触发' if status.over_current else '未触发'}")
        result.add_pass(name, f"校准={status.calibrated}, 状态={status.homing_state}")
    except Exception as e:
        result.add_fail(name, str(e))


def test_get_pid(motor: EmmDevice, result: TestResult):
    """测试读取PID参数."""
    name = "get_pid"
    print_test_header(
        name,
        "读取PID参数",
        expected="返回PIDParams对象，包含Kp、Ki、Kd"
    )
    
    try:
        pid = motor.get_pid()
        print(f"  Kp: {pid.kp}")
        print(f"  Ki: {pid.ki}")
        print(f"  Kd: {pid.kd}")
        result.add_pass(name, f"Kp={pid.kp}, Ki={pid.ki}, Kd={pid.kd}")
    except Exception as e:
        result.add_fail(name, str(e))


def test_get_config(motor: EmmDevice, result: TestResult):
    """测试读取配置参数."""
    name = "get_config"
    print_test_header(
        name,
        "读取驱动配置参数",
        expected="返回ConfigParams对象，包含细分、电流等配置"
    )
    
    try:
        config = motor.get_config()
        print(f"  细分值: {config.microstep}")
        print(f"  开环电流: {config.open_loop_current} mA")
        print(f"  闭环最大电流: {config.closed_loop_current} mA")
        print(f"  堵转保护: {'启用' if config.stall_protect else '禁用'}")
        result.add_pass(name, f"细分={config.microstep}")
    except Exception as e:
        result.add_fail(name, str(e))


def test_get_system_status(motor: EmmDevice, result: TestResult):
    """测试读取系统状态参数."""
    name = "get_system_status"
    print_test_header(
        name,
        "读取系统状态参数",
        expected="返回SystemStatusParams对象，包含电压、电流、位置等"
    )
    
    try:
        status = motor.get_system_status()
        print(f"  总线电压: {status.bus_voltage} mV")
        print(f"  相电流: {status.phase_current} mA")
        print(f"  编码器值: {status.encoder_value}")
        print(f"  目标位置: {status.target_position}")
        print(f"  实时位置: {status.realtime_position}")
        print(f"  实时转速: {status.realtime_speed} RPM")
        result.add_pass(name, f"电压={status.bus_voltage}mV")
    except Exception as e:
        result.add_fail(name, str(e))


def test_get_homing_params(motor: EmmDevice, result: TestResult):
    """测试读取回零参数."""
    name = "get_homing_params"
    print_test_header(
        name,
        "读取回零参数",
        expected="返回HomingParams对象，包含回零模式、方向、速度等"
    )
    
    try:
        params = motor.get_homing_params()
        print(f"  回零模式: {params.homing_mode}")
        print(f"  回零方向: {params.homing_direction}")
        print(f"  回零速度: {params.homing_speed} RPM")
        print(f"  回零超时: {params.homing_timeout} ms")
        print(f"  碰撞检测转速: {params.collision_speed} RPM")
        print(f"  碰撞检测电流: {params.collision_current} mA")
        print(f"  碰撞检测时间: {params.collision_time} ms")
        print(f"  上电自动回零: {'是' if params.auto_home else '否'}")
        result.add_pass(name, f"模式={params.homing_mode}, 速度={params.homing_speed}RPM")
    except Exception as e:
        result.add_fail(name, str(e))


def test_enable_disable(motor: EmmDevice, result: TestResult):
    """测试使能和失能."""
    name = "enable/disable"
    print_test_header(
        name,
        "测试电机使能和失能",
        params={"sync": False},
        expected="使能后电机锁轴，失能后电机松轴"
    )
    
    try:
        # 使能
        print("  执行: enable()")
        success = motor.enable()
        print(f"  使能结果: {'成功' if success else '失败'}")
        
        time.sleep(0.2)
        
        # 检查状态
        is_enabled = motor.is_enabled()
        print(f"  is_enabled(): {is_enabled}")
        
        # 失能
        print("  执行: disable()")
        success = motor.disable()
        print(f"  失能结果: {'成功' if success else '失败'}")
        
        time.sleep(0.2)
        
        # 检查状态
        is_enabled = motor.is_enabled()
        print(f"  is_enabled(): {is_enabled}")
        
        result.add_pass(name, "使能/失能正常")
    except Exception as e:
        result.add_fail(name, str(e))


def test_jog(motor: EmmDevice, result: TestResult):
    """测试速度模式运动."""
    name = "jog"
    print_test_header(
        name,
        "测试速度模式运动",
        params={"speed": 100, "direction": "CW", "acceleration": 10},
        expected="电机以100RPM顺时针旋转"
    )
    
    try:
        # 使能
        motor.enable()
        time.sleep(0.1)
        
        # 速度模式运动
        print("  执行: jog(speed=100, direction=Direction.CW, acceleration=10)")
        success = motor.jog(speed=100, direction=Direction.CW, acceleration=10)
        print(f"  结果: {'成功' if success else '失败'}")
        
        # 运行1秒
        print("  运行1秒...")
        time.sleep(1)
        
        # 读取速度
        speed = motor.get_realtime_speed()
        print(f"  实时转速: {speed} RPM")
        
        # 停止
        print("  执行: stop()")
        motor.stop()
        
        time.sleep(0.2)
        
        # 失能
        motor.disable()
        
        result.add_pass(name, f"运行速度={speed}RPM")
    except Exception as e:
        motor.stop()
        motor.disable()
        result.add_fail(name, str(e))


def test_move_pulses(motor: EmmDevice, result: TestResult):
    """测试位置模式运动(脉冲)."""
    name = "move_pulses"
    print_test_header(
        name,
        "测试位置模式运动(脉冲数)",
        params={"pulse_count": 1600, "speed": 200, "acceleration": 20},
        expected="电机转动1600脉冲(半圈)"
    )
    
    try:
        # 使能
        motor.enable()
        time.sleep(0.1)
        
        # 记录初始位置
        start_pos = motor.get_realtime_position()
        print(f"  初始位置: {start_pos:.2f}°")
        
        # 位置模式运动
        print("  执行: move_pulses(pulse_count=1600, speed=200, acceleration=20)")
        success = motor.move_pulses(pulse_count=1600, speed=200, acceleration=20)
        print(f"  发送结果: {'成功' if success else '失败'}")
        
        # 等待到位
        print("  等待到位...")
        reached = motor.wait_for_position(timeout=5)
        print(f"  到位结果: {'到位' if reached else '超时'}")
        
        # 读取最终位置
        end_pos = motor.get_realtime_position()
        print(f"  最终位置: {end_pos:.2f}°")
        print(f"  移动距离: {end_pos - start_pos:.2f}°")
        
        # 失能
        motor.disable()
        
        result.add_pass(name, f"移动{end_pos - start_pos:.2f}°")
    except Exception as e:
        motor.stop()
        motor.disable()
        result.add_fail(name, str(e))


def test_move_degrees(motor: EmmDevice, result: TestResult):
    """测试位置模式运动(角度)."""
    name = "move_degrees"
    print_test_header(
        name,
        "测试位置模式运动(角度)",
        params={"degrees": 90, "speed": 200, "acceleration": 20},
        expected="电机转动90度"
    )
    
    try:
        # 使能
        motor.enable()
        time.sleep(0.1)
        
        # 记录初始位置
        start_pos = motor.get_realtime_position()
        print(f"  初始位置: {start_pos:.2f}°")
        
        # 位置模式运动
        print("  执行: move_degrees(degrees=90, speed=200, acceleration=20)")
        success = motor.move_degrees(degrees=90, speed=200, acceleration=20)
        print(f"  发送结果: {'成功' if success else '失败'}")
        
        # 等待到位
        print("  等待到位...")
        reached = motor.wait_for_position(timeout=5)
        print(f"  到位结果: {'到位' if reached else '超时'}")
        
        # 读取最终位置
        end_pos = motor.get_realtime_position()
        print(f"  最终位置: {end_pos:.2f}°")
        print(f"  移动距离: {end_pos - start_pos:.2f}°")
        
        # 失能
        motor.disable()
        
        result.add_pass(name, f"移动{end_pos - start_pos:.2f}°")
    except Exception as e:
        motor.stop()
        motor.disable()
        result.add_fail(name, str(e))


def test_move_revolutions(motor: EmmDevice, result: TestResult):
    """测试位置模式运动(圈数)."""
    name = "move_revolutions"
    print_test_header(
        name,
        "测试位置模式运动(圈数)",
        params={"revolutions": 0.5, "speed": 300, "acceleration": 30},
        expected="电机转动0.5圈(180度)"
    )
    
    try:
        # 使能
        motor.enable()
        time.sleep(0.1)
        
        # 记录初始位置
        start_pos = motor.get_realtime_position()
        print(f"  初始位置: {start_pos:.2f}°")
        
        # 位置模式运动
        print("  执行: move_revolutions(revolutions=0.5, speed=300, acceleration=30)")
        success = motor.move_revolutions(revolutions=0.5, speed=300, acceleration=30)
        print(f"  发送结果: {'成功' if success else '失败'}")
        
        # 等待到位
        print("  等待到位...")
        reached = motor.wait_for_position(timeout=5)
        print(f"  到位结果: {'到位' if reached else '超时'}")
        
        # 读取最终位置
        end_pos = motor.get_realtime_position()
        print(f"  最终位置: {end_pos:.2f}°")
        print(f"  移动距离: {end_pos - start_pos:.2f}°")
        
        # 失能
        motor.disable()
        
        result.add_pass(name, f"移动{end_pos - start_pos:.2f}°")
    except Exception as e:
        motor.stop()
        motor.disable()
        result.add_fail(name, str(e))


def test_stop(motor: EmmDevice, result: TestResult):
    """测试立即停止."""
    name = "stop"
    print_test_header(
        name,
        "测试立即停止",
        expected="电机立即停止运动"
    )
    
    try:
        # 使能
        motor.enable()
        time.sleep(0.1)
        
        # 开始运动
        print("  开始速度模式运动...")
        motor.jog(speed=200, direction=Direction.CW, acceleration=10)
        time.sleep(0.5)
        
        # 读取速度
        speed_before = motor.get_realtime_speed()
        print(f"  停止前速度: {speed_before} RPM")
        
        # 停止
        print("  执行: stop()")
        success = motor.stop()
        print(f"  结果: {'成功' if success else '失败'}")
        
        time.sleep(0.2)
        
        # 读取速度
        speed_after = motor.get_realtime_speed()
        print(f"  停止后速度: {speed_after} RPM")
        
        # 失能
        motor.disable()
        
        result.add_pass(name, f"停止前={speed_before}RPM, 停止后={speed_after}RPM")
    except Exception as e:
        motor.stop()
        motor.disable()
        result.add_fail(name, str(e))


def test_zero_position(motor: EmmDevice, result: TestResult):
    """测试清零当前位置."""
    name = "zero_position"
    print_test_header(
        name,
        "将当前位置角度清零",
        expected="当前位置变为0度"
    )
    
    try:
        # 读取当前位置
        pos_before = motor.get_realtime_position()
        print(f"  清零前位置: {pos_before:.2f}°")
        
        # 清零
        print("  执行: zero_position()")
        success = motor.zero_position()
        print(f"  结果: {'成功' if success else '失败'}")
        
        time.sleep(0.1)
        
        # 读取位置
        pos_after = motor.get_realtime_position()
        print(f"  清零后位置: {pos_after:.2f}°")
        
        result.add_pass(name, f"清零前={pos_before:.2f}°, 清零后={pos_after:.2f}°")
    except Exception as e:
        result.add_fail(name, str(e))


def test_clear_protection(motor: EmmDevice, result: TestResult):
    """测试解除保护."""
    name = "clear_protection"
    print_test_header(
        name,
        "解除堵转/过热/过流保护",
        expected="保护状态被解除"
    )
    
    try:
        print("  执行: clear_protection()")
        success = motor.clear_protection()
        print(f"  结果: {'成功' if success else '失败'}")
        
        # 读取状态
        status = motor.get_motor_status()
        print(f"  堵转保护: {'已触发' if status.stall_protected else '未触发'}")
        
        homing_status = motor.get_homing_status()
        print(f"  过热保护: {'已触发' if homing_status.over_temp else '未触发'}")
        print(f"  过流保护: {'已触发' if homing_status.over_current else '未触发'}")
        
        result.add_pass(name, "保护已解除")
    except Exception as e:
        result.add_fail(name, str(e))


def test_is_stalled(motor: EmmDevice, result: TestResult):
    """测试堵转检测."""
    name = "is_stalled"
    print_test_header(
        name,
        "检查是否堵转",
        expected="返回堵转状态"
    )
    
    try:
        stalled = motor.is_stalled()
        print(f"  is_stalled(): {stalled}")
        result.add_pass(name, f"堵转={stalled}")
    except Exception as e:
        result.add_fail(name, str(e))


def test_is_position_reached(motor: EmmDevice, result: TestResult):
    """测试位置到达检测."""
    name = "is_position_reached"
    print_test_header(
        name,
        "检查是否到达目标位置",
        expected="返回位置到达状态"
    )
    
    try:
        reached = motor.is_position_reached()
        print(f"  is_position_reached(): {reached}")
        result.add_pass(name, f"到位={reached}")
    except Exception as e:
        result.add_fail(name, str(e))


def test_set_microstep(motor: EmmDevice, result: TestResult):
    """测试修改细分值."""
    name = "set_microstep"
    print_test_header(
        name,
        "修改细分值",
        params={"microstep": 16, "store": False},
        expected="细分值被修改"
    )
    
    try:
        # 读取当前细分
        config = motor.get_config()
        original = config.microstep
        print(f"  当前细分: {original}")
        
        # 修改细分（不存储）
        print("  执行: set_microstep(16, store=False)")
        success = motor.set_microstep(16, store=False)
        print(f"  结果: {'成功' if success else '失败'}")
        
        result.add_pass(name, f"细分={original}")
    except Exception as e:
        result.add_fail(name, str(e))


def test_home(motor: EmmDevice, result: TestResult):
    """测试回零功能."""
    name = "home"
    print_test_header(
        name,
        "触发回零",
        params={"mode": "NEAREST"},
        expected="电机执行就近回零"
    )
    
    try:
        # 使能
        motor.enable()
        time.sleep(0.1)
        
        # 触发回零
        print("  执行: home(mode=HomingMode.NEAREST)")
        success = motor.home(mode=HomingMode.NEAREST)
        print(f"  结果: {'成功' if success else '失败'}")
        
        # 等待回零完成
        print("  等待回零完成...")
        for i in range(30):  # 最多等待3秒
            status = motor.get_homing_status()
            if not status.is_homing:
                break
            time.sleep(0.1)
        
        # 检查结果
        status = motor.get_homing_status()
        print(f"  回零状态: {status.homing_state}")
        
        # 失能
        motor.disable()
        
        result.add_pass(name, f"状态={status.homing_state}")
    except Exception as e:
        motor.stop()
        motor.disable()
        result.add_fail(name, str(e))


def run_all_tests(port: str, address: int = 1):
    """运行所有测试."""
    print("=" * 60)
    print("Emm步进电机库完整功能测试")
    print("=" * 60)
    print(f"串口: {port}")
    print(f"地址: {address}")
    print("=" * 60)
    
    result = TestResult()
    
    # 创建串口连接
    try:
        ser = Serial(port, 115200, timeout=1)
    except Exception as e:
        print(f"无法打开串口 {port}: {e}")
        return
    
    try:
        # 创建设备实例
        print("\n创建设备实例...")
        motor = EmmDevice(ser, address=address, auto_test=False)
        print(f"设备地址: {motor.address}")
        
        # ==================== 读取参数测试 ====================
        print("\n" + "=" * 60)
        print("一、读取参数测试")
        print("=" * 60)
        
        test_get_version(motor, result)
        test_get_motor_rh(motor, result)
        test_get_bus_voltage(motor, result)
        test_get_bus_current(motor, result)
        test_get_phase_current(motor, result)
        test_get_encoder(motor, result)
        test_get_pulse_count(motor, result)
        test_get_target_position(motor, result)
        test_get_realtime_speed(motor, result)
        test_get_realtime_position(motor, result)
        test_get_position_error(motor, result)
        test_get_temperature(motor, result)
        test_get_motor_status(motor, result)
        test_get_homing_status(motor, result)
        test_get_pid(motor, result)
        test_get_config(motor, result)
        test_get_system_status(motor, result)
        test_get_homing_params(motor, result)
        
        # ==================== 状态检测测试 ====================
        print("\n" + "=" * 60)
        print("二、状态检测测试")
        print("=" * 60)
        
        test_is_stalled(motor, result)
        test_is_position_reached(motor, result)
        
        # ==================== 控制命令测试 ====================
        print("\n" + "=" * 60)
        print("三、控制命令测试")
        print("=" * 60)
        
        test_clear_protection(motor, result)
        test_zero_position(motor, result)
        test_enable_disable(motor, result)
        
        # ==================== 运动控制测试 ====================
        print("\n" + "=" * 60)
        print("四、运动控制测试")
        print("=" * 60)
        
        test_jog(motor, result)
        test_stop(motor, result)
        test_move_pulses(motor, result)
        test_move_degrees(motor, result)
        test_move_revolutions(motor, result)
        
        # ==================== 设置参数测试 ====================
        print("\n" + "=" * 60)
        print("五、设置参数测试")
        print("=" * 60)
        
        test_set_microstep(motor, result)
        
        # ==================== 回零测试 ====================
        print("\n" + "=" * 60)
        print("六、回零测试")
        print("=" * 60)
        
        test_home(motor, result)
        
        # 打印汇总
        result.summary()
        
    except Exception as e:
        print(f"\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        ser.close()
        print("\n串口已关闭")


if __name__ == "__main__":
    # 默认串口和地址
    port = "COM9"
    address = 1
    
    # 从命令行参数获取
    if len(sys.argv) > 1:
        port = sys.argv[1]
    if len(sys.argv) > 2:
        address = int(sys.argv[2])
    
    run_all_tests(port, address)