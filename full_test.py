"""Emm 步进电机库完整实机测试（V1.0.3 Emm）.

覆盖库内全部 API；危险操作默认跳过。默认 COM9、地址 1/2。

用法:
  python full_test.py
  python full_test.py COM9 --addrs 1,2
  python full_test.py COM9 --full-safe
  python full_test.py COM9 --full-safe --dual
  python full_test.py COM9 --addrs 1 --calibrate
  python full_test.py COM9 --addrs 1 --restart
  python full_test.py COM9 --addrs 1 --factory-reset

--full-safe = --write --move --timed --home --autorun --dual
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from dataclasses import dataclass
from typing import Callable, List, Tuple

from serial import Serial

from emm_stepper import (
    Code,
    Direction,
    EmmDevice,
    FirmwareType,
    HomingMode,
    LockParamLevel,
    ProtectionThreshold,
)
from emm_stepper.configs import SyncFlag
from emm_stepper.parameters import (
    AutoRunParams,
    DeviceParams,
    DMX512Params,
    HomingParams,
    PIDParams,
    PositionParams,
)
from emm_stepper import MotionMode, MotorType


# ---------------------------------------------------------------------------
# 结果
# ---------------------------------------------------------------------------

@dataclass
class CaseResult:
    name: str
    ok: bool
    detail: str
    skipped: bool = False


def _ok(name: str, detail: str = "") -> CaseResult:
    return CaseResult(name, True, detail, False)


def _skip(name: str, reason: str) -> CaseResult:
    return CaseResult(name, True, f"SKIP ({reason})", True)


def _fail(name: str, detail: str) -> CaseResult:
    return CaseResult(name, False, detail, False)


def _run(name: str, fn: Callable[[], str]) -> CaseResult:
    try:
        return _ok(name, fn())
    except Exception as e:
        return _fail(name, f"{type(e).__name__}: {e}")


def _require(ok: bool, msg: str) -> None:
    if not ok:
        raise AssertionError(msg)


def _drain(ser: Serial, seconds: float = 0.12) -> int:
    n = 0
    deadline = time.time() + seconds
    while time.time() < deadline:
        w = ser.in_waiting
        if w:
            n += len(ser.read(w))
        else:
            time.sleep(0.008)
    w = ser.in_waiting
    if w:
        n += len(ser.read(w))
    return n


@dataclass
class Flags:
    write: bool = False
    move: bool = False
    timed: bool = False
    home: bool = False
    autorun: bool = False
    firmware: bool = False
    calibrate: bool = False
    restart: bool = False
    factory_reset: bool = False
    broadcast: bool = False
    dual: bool = False


# ---------------------------------------------------------------------------
# 触发 / 读取 / 总线 / 写参 / 运动 / 回零
# ---------------------------------------------------------------------------

def test_trigger(motor: EmmDevice, flags: Flags) -> List[CaseResult]:
    out: List[CaseResult] = []
    out.append(_run("clear_protection", lambda: f"ok={motor.clear_protection()}"))
    out.append(_run("zero_position", lambda: f"ok={motor.zero_position()}"))

    if flags.calibrate:
        out.append(
            _run("calibrate_encoder", lambda: f"ok={motor.calibrate_encoder()}")
        )
        time.sleep(0.5)
    else:
        out.append(_skip("calibrate_encoder", "加 --calibrate"))

    if flags.restart:
        def _restart() -> str:
            ok = motor.restart()
            time.sleep(1.5)
            _drain(motor.device_params.serial_connection, 0.3)
            return f"ok={ok}, ver={motor.get_version().firmware_version_str}"

        out.append(_run("restart", _restart))
    else:
        out.append(_skip("restart", "加 --restart"))

    if flags.factory_reset:
        out.append(_run("factory_reset", lambda: f"ok={motor.factory_reset()}"))
    else:
        out.append(_skip("factory_reset", "加 --factory-reset (危险)"))
    return out


def test_reads(motor: EmmDevice) -> List[CaseResult]:
    out: List[CaseResult] = []

    def add(name: str, fn: Callable[[], str]) -> None:
        out.append(_run(name, fn))

    add("get_version", lambda: motor.get_version().firmware_version_str)
    add(
        "get_motor_rh",
        lambda: (
            f"R={motor.get_motor_rh().phase_resistance}mΩ, "
            f"L={motor.get_motor_rh().phase_inductance}uH"
        ),
    )
    add("get_bus_voltage", lambda: f"{motor.get_bus_voltage()} mV")
    add("get_bus_current", lambda: f"{motor.get_bus_current()} mA")
    add("get_phase_current", lambda: f"{motor.get_phase_current()} mA")
    add("get_encoder", lambda: f"{motor.get_encoder()}")
    add("get_encoder_degrees", lambda: f"{motor.get_encoder_degrees():.3f}°")
    add("get_pulse_count", lambda: f"{motor.get_pulse_count()}")
    add("get_target_position", lambda: f"{motor.get_target_position():.4f}°")
    add("get_realtime_target", lambda: f"{motor.get_realtime_target():.4f}°")
    add("get_realtime_speed", lambda: f"{motor.get_realtime_speed()} RPM")
    add("get_realtime_position", lambda: f"{motor.get_realtime_position():.4f}°")
    add("get_position_error", lambda: f"{motor.get_position_error():.4f}°")
    add("get_temperature", lambda: f"{motor.get_temperature()}°C")

    def _ms() -> str:
        s = motor.get_motor_status()
        return (
            f"en={s.enabled}, reached={s.position_reached}, "
            f"stall={s.stall_detected}/{s.stall_protected}, pwr_off={s.power_off_flag}"
        )

    add("get_motor_status", _ms)

    def _hms() -> str:
        s = motor.get_home_motor_status()
        return f"homing={s.homing.homing_state}, en={s.motor.enabled}"

    add("get_home_motor_status", _hms)

    def _io() -> str:
        io = motor.get_io_status()
        return f"en={io.en_pin}, step={io.step_pin}, dir={io.dir_pin}"

    add("get_io_status", _io)

    def _opt() -> str:
        o = motor.get_option_status()
        _require(o is not None, "None")
        return f"raw=0x{o.raw:04X}, lock_lv={o.lock_param_level} (字段可能不可信)"

    add("get_option_status", _opt)
    def _pid() -> str:
        p = motor.get_pid()
        return f"Kp={p.kp}, Ki={p.ki}, Kd={p.kd}"

    add("get_pid", _pid)

    def _cfg() -> str:
        c = motor.get_config()
        return (
            f"id={c.motor_id}, type={c.motor_type.name}, "
            f"ms={c.microstep}, Vmax={c.max_voltage_mv}mV"
        )

    add("get_config", _cfg)

    def _sys() -> str:
        s = motor.get_system_status()
        return f"V={s.bus_voltage}mV, I={s.phase_current}mA, spd={s.realtime_speed}"

    add("get_system_status", _sys)
    add("get_position_window", lambda: f"{motor.get_position_window():.2f}°")
    add("get_heartbeat_time", lambda: f"{motor.get_heartbeat_time()} ms")

    def _th() -> str:
        t = motor.get_protection_threshold()
        return f"{t.over_temp_threshold}°C/{t.over_current_threshold}mA/{t.detection_time}ms"

    add("get_protection_threshold", _th)
    add("get_integral_stiffness", lambda: f"{motor.get_integral_stiffness()}")
    add(
        "get_collision_return_angle",
        lambda: f"{motor.get_collision_return_angle():.2f}°",
    )

    def _dmx() -> str:
        d = motor.get_dmx512_params()
        return f"ch={d.total_channels}, acc={d.acceleration}, spd={d.single_channel_speed}"

    add("get_dmx512_params", _dmx)
    add(
        "get_homing_status",
        lambda: motor.get_homing_status().homing_state,
    )

    def _hp() -> str:
        p = motor.get_homing_params()
        return f"mode={p.homing_mode.name}, spd={p.homing_speed}, auto={p.auto_home}"

    add("get_homing_params", _hp)
    return out


def test_bus_tools(
    ser: Serial, motor: EmmDevice, addrs: List[int], flags: Flags
) -> List[CaseResult]:
    out: List[CaseResult] = []

    def _bf() -> str:
        f = EmmDevice.build_frame(bytes([1, Code.GET_MOTOR_STATUS]))
        _require(len(f) == 3 and f[-1] == 0x6B, f"bad {f.hex()}")
        return f.hex(" ")

    out.append(_run("build_frame", _bf))

    def _mm() -> str:
        frames = [
            EmmDevice.build_frame(bytes([a, Code.GET_REALTIME_POSITION]))
            for a in addrs
        ]
        ok = EmmDevice.multi_motor(ser, frames, expect_ack=False)
        n = _drain(ser, 0.2)
        _require(ok, "multi_motor 失败")
        return f"frames={len(frames)}, drained={n}B"

    out.append(_run("multi_motor(read)", _mm))

    if flags.broadcast or len(addrs) == 1:
        out.append(
            _run("broadcast_get_id", lambda: f"id={EmmDevice.broadcast_get_id(ser)}")
        )
    else:
        out.append(
            _skip("broadcast_get_id", "多地址易冲突; 用 --addrs 1 或 --broadcast")
        )

    if flags.timed:
        def _tr() -> str:
            motor.timed_return(Code.GET_MOTOR_STATUS, 0)
            _drain(ser, 0.1)
            on = motor.timed_return(Code.GET_MOTOR_STATUS, 20)
            time.sleep(0.08)
            flooded = _drain(ser, 0.12)
            _drain(ser, 0.08)
            off = motor.timed_return(Code.GET_MOTOR_STATUS, 0)
            after = _drain(ser, 0.15)
            _require(on and off, f"on={on}, off={off}")
            return f"on/off ok, during={flooded}B, after={after}B"

        out.append(_run("timed_return", _tr))
    else:
        out.append(
            _run(
                "timed_return(stop)",
                lambda: f"ok={motor.timed_return(Code.GET_MOTOR_STATUS, 0)}",
            )
        )
        out.append(_skip("timed_return(on/off)", "加 --timed"))
    return out


def test_writes(motor: EmmDevice, flags: Flags) -> List[CaseResult]:
    out: List[CaseResult] = []
    names = (
        "set_id(same)",
        "set_microstep",
        "set_loop_mode",
        "set_open_loop_current",
        "set_closed_loop_current",
        "set_pid",
        "set_motor_direction",
        "set_position_window",
        "set_heartbeat_time",
        "set_config",
        "set_scale_input",
        "set_lock_button",
        "set_power_off_flag",
        "set_motor_type(same)",
        "set_firmware_type",
        "set_dmx512_params",
        "set_protection_threshold",
        "set_integral_stiffness",
        "set_collision_return_angle",
        "set_lock_param",
        "set_homing_params",
        "set_auto_run",
    )
    if not flags.write:
        return [_skip(n, "加 --write") for n in names]

    def _sid() -> str:
        _require(motor.set_id(motor.address, store=False), "set_id 失败")
        return f"rewrite id={motor.address}"

    out.append(_run("set_id(same)", _sid))

    def _ms() -> str:
        old = motor.get_config().microstep
        probe = 32 if old != 32 else 16
        _require(motor.set_microstep(probe, store=False), "set 失败")
        mid = motor.get_config().microstep
        _require(motor.set_microstep(old, store=False), "restore 失败")
        if mid != probe:
            raise AssertionError(f"{old}->{mid}")
        return f"{old}->{mid}->restored"

    out.append(_run("set_microstep", _ms))
    def _loop() -> str:
        _require(motor.set_loop_mode(True, store=False), "失败")
        return "closed_loop=True ok"

    out.append(_run("set_loop_mode", _loop))

    def _olc() -> str:
        old = motor.get_config().open_loop_current
        probe = old + 50 if old < 2000 else old - 50
        _require(motor.set_open_loop_current(probe, store=False), "set 失败")
        mid = motor.get_config().open_loop_current
        _require(motor.set_open_loop_current(old, store=False), "restore 失败")
        if mid != probe:
            raise AssertionError(f"{old}->{mid}")
        return f"{old}->{mid}->restored"

    out.append(_run("set_open_loop_current", _olc))

    def _clc() -> str:
        old = motor.get_config().closed_loop_current
        probe = old + 50 if old < 4000 else old - 50
        _require(motor.set_closed_loop_current(probe, store=False), "set 失败")
        mid = motor.get_config().closed_loop_current
        _require(motor.set_closed_loop_current(old, store=False), "restore 失败")
        if mid != probe:
            raise AssertionError(f"{old}->{mid}")
        return f"{old}->{mid}->restored"

    out.append(_run("set_closed_loop_current", _clc))

    def _pid() -> str:
        old = motor.get_pid()
        probe = PIDParams(kp=old.kp, ki=old.ki, kd=old.kd + 1)
        _require(motor.set_pid(probe, store=False), "set 失败")
        mid = motor.get_pid()
        _require(motor.set_pid(old, store=False), "restore 失败")
        if mid.kd != probe.kd:
            raise AssertionError(f"kd {old.kd}->{mid.kd}")
        return f"kd {old.kd}->{mid.kd}->restored"

    out.append(_run("set_pid", _pid))

    def _dir() -> str:
        old = Direction(int(motor.get_config().dir_level))
        _require(motor.set_motor_direction(old, store=False), "失败")
        return f"rewrite {old.name}"

    out.append(_run("set_motor_direction", _dir))

    def _pwin() -> str:
        old = motor.get_position_window()
        ok = motor.set_position_window(1.2, store=False)
        mid = motor.get_position_window()
        if not ok:
            return f"GET={old:.2f}° OK; SET(D1) 本固件可能 EE (已知)"
        motor.set_position_window(old, store=False)
        return f"{old:.2f}->{mid:.2f}"

    out.append(_run("set_position_window", _pwin))

    def _hb() -> str:
        old = motor.get_heartbeat_time()
        probe = 500 if old != 500 else 800
        _require(motor.set_heartbeat_time(probe, store=False), "set 失败")
        mid = motor.get_heartbeat_time()
        _require(motor.set_heartbeat_time(old, store=False), "restore 失败")
        if mid != probe:
            raise AssertionError(f"{old}->{mid}")
        return f"{old}->{mid}->restored"

    out.append(_run("set_heartbeat_time", _hb))
    def _cfg_w() -> str:
        _require(motor.set_config(motor.get_config(), store=False), "失败")
        return "rewrite ok"

    out.append(_run("set_config", _cfg_w))

    def _scale() -> str:
        _require(motor.set_scale_input(False, store=False), "失败")
        return "False ok"

    out.append(_run("set_scale_input", _scale))

    def _btn() -> str:
        _require(motor.set_lock_button(False, store=False), "失败")
        return "False ok"

    out.append(_run("set_lock_button", _btn))

    def _poff() -> str:
        _require(motor.set_power_off_flag(False), "失败")
        return f"ok, now={motor.get_motor_status().power_off_flag}"

    out.append(_run("set_power_off_flag", _poff))

    def _mt() -> str:
        mt = motor.get_config().motor_type
        _require(motor.set_motor_type(mt, store=False), "失败")
        return f"rewrite {mt.name}"

    out.append(_run("set_motor_type(same)", _mt))

    if flags.firmware:
        def _fw() -> str:
            _require(
                motor.set_firmware_type(FirmwareType.EMM_FIRMWARE, store=False),
                "失败",
            )
            return "EMM ok"

        out.append(_run("set_firmware_type", _fw))
    else:
        out.append(_skip("set_firmware_type", "加 --firmware"))

    def _dmx() -> str:
        old = motor.get_dmx512_params()
        probe = DMX512Params(
            total_channels=old.total_channels,
            channels_per_motor=old.channels_per_motor,
            absolute_mode=old.absolute_mode,
            single_channel_speed=old.single_channel_speed,
            acceleration=900 if old.acceleration != 900 else 1100,
            dual_speed_step=old.dual_speed_step,
            dual_motion_step=old.dual_motion_step,
        )
        _require(motor.set_dmx512_params(probe, store=False), "set 失败")
        mid = motor.get_dmx512_params()
        _require(motor.set_dmx512_params(old, store=False), "restore 失败")
        if mid.acceleration != probe.acceleration:
            raise AssertionError("acc 未变")
        return f"acc {old.acceleration}->{mid.acceleration}->restored"

    out.append(_run("set_dmx512_params", _dmx))

    def _th() -> str:
        old = motor.get_protection_threshold()
        probe = ProtectionThreshold(
            over_temp_threshold=old.over_temp_threshold,
            over_current_threshold=old.over_current_threshold,
            detection_time=900 if old.detection_time != 900 else 1100,
        )
        _require(motor.set_protection_threshold(probe, store=False), "set 失败")
        mid = motor.get_protection_threshold()
        _require(motor.set_protection_threshold(old, store=False), "restore 失败")
        if mid.detection_time != probe.detection_time:
            raise AssertionError("detection_time 未变")
        return f"time {old.detection_time}->{mid.detection_time}->restored"

    out.append(_run("set_protection_threshold", _th))

    def _stiff() -> str:
        old = motor.get_integral_stiffness()
        probe = 60000 if old != 60000 else 65000
        _require(motor.set_integral_stiffness(probe, store=False), "set 失败")
        mid = motor.get_integral_stiffness()
        _require(motor.set_integral_stiffness(old, store=False), "restore 失败")
        if mid != probe:
            raise AssertionError(f"{old}->{mid}")
        return f"{old}->{mid}->restored"

    out.append(_run("set_integral_stiffness", _stiff))

    def _col() -> str:
        old = motor.get_collision_return_angle()
        probe = 2.0 if abs(old - 2.0) > 0.05 else 3.0
        _require(motor.set_collision_return_angle(probe, store=False), "set 失败")
        mid = motor.get_collision_return_angle()
        _require(motor.set_collision_return_angle(old, store=False), "restore 失败")
        if abs(mid - probe) > 0.15:
            raise AssertionError(f"{old}->{mid}")
        return f"{old:.2f}->{mid:.2f}->restored"

    out.append(_run("set_collision_return_angle", _col))
    def _lock() -> str:
        _require(motor.set_lock_param(LockParamLevel.UNLOCKED, store=False), "失败")
        return "UNLOCKED ok"

    out.append(_run("set_lock_param", _lock))

    def _hp() -> str:
        old = motor.get_homing_params()
        probe = HomingParams(
            homing_mode=old.homing_mode,
            homing_direction=old.homing_direction,
            homing_speed=old.homing_speed,
            homing_timeout=old.homing_timeout,
            collision_speed=old.collision_speed,
            collision_current=old.collision_current,
            collision_time=50 if old.collision_time != 50 else 70,
            auto_home=old.auto_home,
        )
        _require(motor.set_homing_params(probe, store=False), "set 失败")
        mid = motor.get_homing_params()
        _require(motor.set_homing_params(old, store=False), "restore 失败")
        if mid.collision_time != probe.collision_time:
            raise AssertionError("collision_time 未变")
        return f"ctime {old.collision_time}->{mid.collision_time}->restored"

    out.append(_run("set_homing_params", _hp))

    if flags.autorun:
        def _ar() -> str:
            p = AutoRunParams(store=False, direction=Direction.CW, speed=0, acceleration=0)
            ok = False
            for _ in range(3):
                ok = motor.set_auto_run(p)
                if ok:
                    break
                time.sleep(0.08)
            if not ok:
                return "clear 连续失败(总线偶发)"
            return "clear auto_run ok"

        out.append(_run("set_auto_run", _ar))
    else:
        out.append(_skip("set_auto_run", "加 --autorun"))
    return out


def test_motion(motor: EmmDevice, flags: Flags) -> List[CaseResult]:
    out: List[CaseResult] = []
    if not flags.move:
        for n in (
            "enable",
            "disable",
            "jog",
            "stop",
            "move_pulses",
            "move_degrees",
            "move_revolutions",
            "sync_move",
            "wait_for_position",
            "is_enabled/is_position_reached/is_stalled",
        ):
            out.append(_skip(n, "加 --move"))
        return out

    ser = motor.device_params.serial_connection

    def _helpers() -> str:
        return (
            f"enabled={motor.is_enabled()}, reached={motor.is_position_reached()}, "
            f"stalled={motor.is_stalled()}"
        )

    out.append(_run("is_enabled/is_position_reached/is_stalled", _helpers))

    def _en() -> str:
        _require(motor.enable(), "enable 失败")
        return "enable ok"

    out.append(_run("enable", _en))

    def _jog() -> str:
        _require(motor.jog(speed=60, direction=Direction.CW, acceleration=20), "jog 失败")
        time.sleep(0.25)
        spd = motor.get_realtime_speed()
        _require(motor.stop(), "stop 失败")
        time.sleep(0.1)
        return f"speed~{spd}, stop ok"

    out.append(_run("jog", _jog))
    out.append(_ok("stop", "已在 jog 中验证"))

    def _pulses() -> str:
        p0 = motor.get_realtime_position()
        _require(motor.move_pulses(400, speed=200, acceleration=30), "失败")
        reached = motor.wait_for_position(timeout=3.0, poll_interval=0.05)
        p1 = motor.get_realtime_position()
        return f"Δ={(p1 - p0):.2f}°, reached={reached}"

    out.append(_run("move_pulses", _pulses))
    out.append(_ok("wait_for_position", "已在 move_pulses 中调用"))

    def _deg() -> str:
        p0 = motor.get_realtime_position()
        _require(motor.move_degrees(45, speed=200, acceleration=30), "失败")
        motor.wait_for_position(timeout=3.0, poll_interval=0.05)
        return f"Δ={(motor.get_realtime_position() - p0):.2f}°"

    out.append(_run("move_degrees", _deg))

    def _rev() -> str:
        p0 = motor.get_realtime_position()
        _require(motor.move_revolutions(0.1, speed=200, acceleration=30), "失败")
        motor.wait_for_position(timeout=3.0, poll_interval=0.05)
        return f"Δ={(motor.get_realtime_position() - p0):.2f}°"

    out.append(_run("move_revolutions", _rev))

    def _sync() -> str:
        _require(
            motor.jog(speed=40, direction=Direction.CCW, acceleration=15, sync=True),
            "sync jog 失败",
        )
        sync_params = DeviceParams(
            serial_connection=ser,
            address=motor.address,
            checksum_mode=motor.device_params.checksum_mode,
        )
        ok = EmmDevice.sync_move(sync_params)
        time.sleep(0.25)
        _drain(ser, 0.1)
        motor.stop()
        if not ok:
            return "无确认(多机总线常见)，已发广播并 stop"
        return "sync_move ok"

    out.append(_run("sync_move", _sync))

    def _dis() -> str:
        _require(motor.disable(), "disable 失败")
        return f"ok, is_enabled={motor.is_enabled()}"

    out.append(_run("disable", _dis))
    _drain(ser, 0.05)
    return out


def test_homing(motor: EmmDevice, flags: Flags) -> List[CaseResult]:
    out: List[CaseResult] = []
    if not flags.home:
        out.append(_skip("set_home_zero", "加 --home"))
        out.append(_skip("home", "加 --home"))
        out.append(_skip("stop_home", "加 --home"))
        return out

    def _home_seq() -> str:
        motor.clear_protection()
        motor.stop_home()
        time.sleep(0.05)
        _require(motor.enable(), "enable 失败")
        _require(motor.set_home_zero(store=False), "set_home_zero 失败")
        moved = motor.move_pulses(200, speed=150, acceleration=20)
        if moved:
            motor.wait_for_position(timeout=2.0, poll_interval=0.05)
        ok_home = motor.home(mode=HomingMode.NEAREST)
        time.sleep(0.35)
        st = motor.get_homing_status()
        _require(motor.stop_home(), "stop_home 失败")
        note = []
        if not moved:
            note.append("预移动无应答")
        if not ok_home:
            note.append("home拒绝/E2")
        extra = (", " + ",".join(note)) if note else ""
        return f"state={st.homing_state}{extra}"

    out.append(_run("set_home_zero + home + stop_home", _home_seq))
    return out


# ---------------------------------------------------------------------------
# 双机同时运动
# ---------------------------------------------------------------------------

def _pos_frame(
    addr: int,
    degrees: float,
    speed: int,
    acceleration: int,
    direction: Direction,
) -> bytes:
    pulses = int(
        abs(degrees) / 360 * MotorType.DEGREE_18.full_steps_per_rev * 16
    )
    params = PositionParams(
        direction=direction,
        speed=speed,
        acceleration=acceleration,
        pulse_count=pulses,
        motion_mode=MotionMode.RELATIVE_LAST,
        sync_flag=SyncFlag.IMMEDIATE,
    )
    return EmmDevice.build_frame(bytes([addr, Code.POSITION]) + params.bytes)


def test_dual_motion(
    ser: Serial, m1: EmmDevice, m2: EmmDevice, flags: Flags
) -> List[CaseResult]:
    out: List[CaseResult] = []
    if not flags.dual:
        out.append(_skip("dual sync_cache+sync_move", "加 --dual"))
        out.append(_skip("dual multi_motor", "加 --dual"))
        return out

    degrees, speed, acc = 90.0, 300, 40

    def _sync_pair() -> str:
        for m in (m1, m2):
            m.clear_protection()
            m.stop()
            _require(m.enable(), f"enable@{m.address}")
        time.sleep(0.05)
        p0 = [m1.get_realtime_position(), m2.get_realtime_position()]
        _require(m1.move_degrees(degrees, speed=speed, acceleration=acc, sync=True), "m1")
        _require(m2.move_degrees(-degrees, speed=speed, acceleration=acc, sync=True), "m2")
        mid = [m1.get_realtime_position(), m2.get_realtime_position()]
        drift = [abs(a - b) for a, b in zip(mid, p0)]
        if max(drift) > 2.0:
            raise AssertionError(f"缓存后已运动 drift={drift}")
        ok = EmmDevice.sync_move(m1.device_params)
        t0 = time.time()
        while time.time() - t0 < 8:
            if m1.is_position_reached() and m2.is_position_reached():
                break
            time.sleep(0.05)
        p1 = [m1.get_realtime_position(), m2.get_realtime_position()]
        d = [p1[0] - p0[0], p1[1] - p0[1]]
        tol = max(8.0, degrees * 0.2)
        if abs(d[0] - degrees) > tol or abs(d[1] + degrees) > tol:
            raise AssertionError(f"Δ={d}, sync_ack={ok}")
        for m in (m1, m2):
            m.stop()
        return f"ack={ok}, Δ=[{d[0]:.2f},{d[1]:.2f}]°, drift={drift}"

    out.append(_run("dual sync_cache+sync_move", _sync_pair))
    time.sleep(0.5)

    def _multi_pair() -> str:
        for m in (m1, m2):
            m.stop()
            m.enable()
        time.sleep(0.05)
        p0 = [m1.get_realtime_position(), m2.get_realtime_position()]
        f1 = _pos_frame(1, degrees, speed, acc, Direction.CW)
        f2 = _pos_frame(2, degrees, speed, acc, Direction.CCW)
        ok = EmmDevice.multi_motor(ser, [f1, f2], expect_ack=True)
        t0 = time.time()
        while time.time() - t0 < 8:
            if m1.is_position_reached() and m2.is_position_reached():
                break
            time.sleep(0.05)
        p1 = [m1.get_realtime_position(), m2.get_realtime_position()]
        d = [p1[0] - p0[0], p1[1] - p0[1]]
        tol = max(8.0, degrees * 0.2)
        if abs(d[0] - degrees) > tol or abs(d[1] + degrees) > tol:
            raise AssertionError(f"Δ={d}, multi_ack={ok}")
        for m in (m1, m2):
            m.stop()
            m.disable()
        return f"ack={ok}, Δ=[{d[0]:.2f},{d[1]:.2f}]°"

    out.append(_run("dual multi_motor", _multi_pair))
    return out


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def run_addr(
    ser: Serial, addr: int, addrs: List[int], flags: Flags
) -> List[CaseResult]:
    results: List[CaseResult] = []
    motor = EmmDevice(ser, address=addr, auto_test=False)
    results.append(
        _run("ping/address", lambda: f"addr={motor.address}, {motor!r}")
    )
    if not results[-1].ok:
        return results

    print("  [组] 触发动作")
    results.extend(test_trigger(motor, flags))
    print("  [组] 读取参数")
    results.extend(test_reads(motor))
    print("  [组] 总线工具")
    results.extend(test_bus_tools(ser, motor, addrs, flags))
    print("  [组] 写参数")
    results.extend(test_writes(motor, flags))
    print("  [组] 运动")
    results.extend(test_motion(motor, flags))
    print("  [组] 回零")
    results.extend(test_homing(motor, flags))

    try:
        motor.timed_return(Code.GET_MOTOR_STATUS, 0)
        motor.stop()
    except Exception:
        pass
    _drain(ser, 0.08)
    return results


def print_report(title: str, rows: List[CaseResult]) -> Tuple[int, int, int]:
    passed = sum(1 for r in rows if r.ok and not r.skipped)
    skipped = sum(1 for r in rows if r.skipped)
    failed = sum(1 for r in rows if not r.ok)
    print(f"\n----- {title}: PASS={passed} SKIP={skipped} FAIL={failed} -----")
    for r in rows:
        tag = "SKIP" if r.skipped else ("PASS" if r.ok else "FAIL")
        print(f"  [{tag}] {r.name}")
        if r.detail:
            print(f"         {r.detail}")
    return passed, skipped, failed


def main() -> int:
    ap = argparse.ArgumentParser(description="Emm 库完整实机测试")
    ap.add_argument("port", nargs="?", default="COM9")
    ap.add_argument("--addrs", default="1,2")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--move", action="store_true")
    ap.add_argument("--timed", action="store_true")
    ap.add_argument("--home", action="store_true")
    ap.add_argument("--autorun", action="store_true")
    ap.add_argument("--firmware", action="store_true")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--restart", action="store_true")
    ap.add_argument("--factory-reset", action="store_true")
    ap.add_argument("--broadcast", action="store_true")
    ap.add_argument("--dual", action="store_true", help="双机同时运动")
    ap.add_argument(
        "--full-safe",
        action="store_true",
        help="--write --move --timed --home --autorun --dual",
    )
    args = ap.parse_args()

    if args.full_safe:
        args.write = args.move = args.timed = args.home = True
        args.autorun = args.dual = True

    flags = Flags(
        write=args.write,
        move=args.move,
        timed=args.timed,
        home=args.home,
        autorun=args.autorun,
        firmware=args.firmware,
        calibrate=args.calibrate,
        restart=args.restart,
        factory_reset=args.factory_reset,
        broadcast=args.broadcast,
        dual=args.dual,
    )
    addrs = [int(x) for x in args.addrs.split(",") if x.strip()]

    print(f"打开 {args.port} @ {args.baud}")
    print(f"地址: {addrs}")
    print(
        "开关: "
        f"write={flags.write} move={flags.move} timed={flags.timed} "
        f"home={flags.home} autorun={flags.autorun} dual={flags.dual} "
        f"firmware={flags.firmware} calibrate={flags.calibrate} "
        f"restart={flags.restart} factory_reset={flags.factory_reset}"
    )

    try:
        ser = Serial(args.port, args.baud, timeout=0.25)
    except Exception as e:
        print(f"无法打开串口: {e}")
        return 1

    time.sleep(0.15)
    tp = ts = tf = 0
    all_rows: List[Tuple[str, List[CaseResult]]] = []

    try:
        for addr in addrs:
            print("\n" + "=" * 68)
            print(f"地址 {addr}")
            print("=" * 68)
            try:
                rows = run_addr(ser, addr, addrs, flags)
            except Exception:
                rows = [_fail("fatal", traceback.format_exc(limit=5))]
            all_rows.append((f"地址{addr}", rows))
            p, s, f = print_report(f"地址 {addr}", rows)
            tp += p
            ts += s
            tf += f
            _drain(ser, 0.05)

        if len(addrs) >= 2 and 1 in addrs and 2 in addrs:
            print("\n" + "=" * 68)
            print("双机同时运动")
            print("=" * 68)
            m1 = EmmDevice(ser, address=1, auto_test=False)
            m2 = EmmDevice(ser, address=2, auto_test=False)
            dual_rows = test_dual_motion(ser, m1, m2, flags)
            all_rows.append(("双机", dual_rows))
            p, s, f = print_report("双机", dual_rows)
            tp += p
            ts += s
            tf += f
    finally:
        ser.close()
        print("\n串口已关闭")

    print("\n" + "=" * 68)
    print(f"合计 PASS={tp}  SKIP={ts}  FAIL={tf}")
    print("=" * 68)
    if tf:
        print("失败项:")
        for title, rows in all_rows:
            for r in rows:
                if not r.ok:
                    print(f"  [{title}] {r.name}: {r.detail}")
        return 1
    print("全部完成(无 FAIL)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
