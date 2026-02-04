"""Emm固件步进电机设备类.

基于ZDT_X42S第二代闭环步进电机用户手册V1.0.3_251224。
提供高级API接口用于控制步进电机。
"""

import logging
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
    AutoRunParams,
)
from .commands import (
    # 触发动作命令
    CalibrateEncoder,
    Restart,
    ZeroPosition,
    ClearProtection,
    FactoryReset,
    # 运动控制命令
    Enable,
    Disable,
    Jog,
    Position,
    EStop,
    SyncMove,
    # 原点回零命令
    SetHomeZero,
    Home,
    StopHome,
    GetHomingStatus,
    GetHomingParams,
    SetHomingParams,
    # 读取系统参数命令
    GetVersion,
    GetMotorRH,
    GetBusVoltage,
    GetBusCurrent,
    GetPhaseCurrent,
    GetEncoder,
    GetPulseCount,
    GetTargetPosition,
    GetRealtimeSpeed,
    GetRealtimePosition,
    GetPositionError,
    GetTemperature,
    GetMotorStatus,
    GetPID,
    GetConfig,
    GetSystemStatus,
    # 设置命令
    SetID,
    SetMicrostep,
    SetLoopMode,
    SetOpenLoopCurrent,
    SetClosedLoopCurrent,
    SetPID,
    SetMotorDirection,
    SetPositionWindow,
    SetHeartbeatTime,
    SetAutoRun,
    SetConfig,
    SetScaleInput,
    SetLockButton,
    BroadcastGetID,
)

logger = logging.getLogger(__name__)


class EmmDevice:
    """Emm固件步进电机设备类.
    
    提供高级API接口用于控制ZDT X42S第二代闭环步进电机(Emm固件)。
    
    注意: 串口连接需要在外部创建，这样可以支持一个串口连接多个电机（通过不同地址）。
    
    使用示例:
        ```python
        from serial import Serial
        from emm_stepper import EmmDevice, ChecksumMode
        
        # 创建串口连接
        ser = Serial('COM3', 115200, timeout=1)
        
        # 创建设备实例（可以用同一个串口创建多个不同地址的电机）
        motor1 = EmmDevice(ser, address=1)
        motor2 = EmmDevice(ser, address=2)
        
        # 使能电机
        motor1.enable()
        
        # 速度模式运动
        motor1.jog(speed=100, direction=0)
        
        # 位置模式运动
        motor1.move_pulses(pulses=3200, speed=500)  # 转一圈
        
        # 停止
        motor1.stop()
        
        # 失能电机
        motor1.disable()
        
        # 关闭串口（由用户管理）
        ser.close()
        ```
    """

    def __init__(
        self,
        serial_connection: Serial,
        address: int = 1,
        checksum_mode: ChecksumMode = ChecksumMode.FIXED,
        delay: Optional[float] = None,
        auto_test: bool = True,
    ):
        """初始化设备.
        
        Args:
            serial_connection: 串口连接对象
            address: 电机地址 (1-255)
            checksum_mode: 校验模式
            delay: 通讯延迟(秒)
            auto_test: 是否自动测试连接 (默认True)
        """
        self._serial = serial_connection
        self._device_params = DeviceParams(
            serial_connection=serial_connection,
            address=address,
            checksum_mode=checksum_mode,
            delay=delay,
        )
        
        # 测试连接
        if auto_test:
            self._test_connection()
        
        logger.info(f"已连接到电机 (地址: {address})")

    def _test_connection(self) -> None:
        """测试与电机的连接."""
        try:
            version = self.get_version()
            logger.info(f"固件版本: {version.firmware_version_str}, 硬件: {version.hw_type_str}")
        except Exception as e:
            raise ConnectionError(f"无法连接到电机: {e}")

    @property
    def device_params(self) -> DeviceParams:
        """返回设备参数."""
        return self._device_params

    @property
    def address(self) -> int:
        """返回电机地址."""
        return self._device_params.address

    # ==================== 触发动作命令 ====================

    def calibrate_encoder(self) -> bool:
        """触发编码器校准.
        
        电机将缓慢正转一圈然后反转一圈对编码器进行线性化校准。
        
        Returns:
            是否成功
        """
        cmd = CalibrateEncoder(self._device_params)
        return cmd.is_success

    def restart(self) -> bool:
        """重启电机.
        
        Returns:
            是否成功
        """
        cmd = Restart(self._device_params)
        return cmd.is_success

    def zero_position(self) -> bool:
        """将当前位置角度清零.
        
        Returns:
            是否成功
        """
        cmd = ZeroPosition(self._device_params)
        return cmd.is_success

    def clear_protection(self) -> bool:
        """解除堵转/过热/过流保护.
        
        Returns:
            是否成功
        """
        cmd = ClearProtection(self._device_params)
        return cmd.is_success

    def factory_reset(self) -> bool:
        """恢复出厂设置.
        
        注意: 恢复后需要断电重新上电，再空载校准电机编码器。
        
        Returns:
            是否成功
        """
        cmd = FactoryReset(self._device_params)
        return cmd.is_success

    # ==================== 运动控制命令 ====================

    def enable(self, sync: bool = False) -> bool:
        """使能电机(锁轴).
        
        Args:
            sync: 是否使用同步模式
            
        Returns:
            是否成功
        """
        sync_flag = SyncFlag.SYNC if sync else SyncFlag.IMMEDIATE
        cmd = Enable(self._device_params, enable=True, sync_flag=sync_flag)
        return cmd.is_success

    def disable(self, sync: bool = False) -> bool:
        """失能电机(松轴).
        
        Args:
            sync: 是否使用同步模式
            
        Returns:
            是否成功
        """
        sync_flag = SyncFlag.SYNC if sync else SyncFlag.IMMEDIATE
        cmd = Disable(self._device_params, sync_flag=sync_flag)
        return cmd.is_success

    def jog(
        self,
        speed: int = 100,
        direction: Direction = Direction.CW,
        acceleration: int = 10,
        sync: bool = False,
    ) -> bool:
        """速度模式运动.
        
        电机以指定速度持续运动，直到收到停止命令。
        
        Args:
            speed: 速度 (0-3000 RPM)
            direction: 运动方向
            acceleration: 加速度档位 (0-255)
            sync: 是否使用同步模式
            
        Returns:
            是否成功
        """
        params = JogParams(
            direction=direction,
            speed=speed,
            acceleration=acceleration,
            sync_flag=SyncFlag.SYNC if sync else SyncFlag.IMMEDIATE,
        )
        cmd = Jog(self._device_params, params=params)
        return cmd.is_success

    def move_pulses(
        self,
        pulse_count: int,
        speed: int = 100,
        direction: Optional[Direction] = None,
        acceleration: int = 10,
        motion_mode: MotionMode = MotionMode.RELATIVE_LAST,
        sync: bool = False,
    ) -> bool:
        """位置模式运动(脉冲数).
        
        电机运动指定的脉冲数。默认16细分下，3200个脉冲=一圈360°。
        
        Args:
            pulse_count: 脉冲数 (正数为CW方向，负数为CCW方向)
            speed: 速度 (0-3000 RPM)
            direction: 运动方向 (如果为None，则根据pulse_count的正负自动判断)
            acceleration: 加速度档位 (0-255)
            motion_mode: 运动模式
            sync: 是否使用同步模式
            
        Returns:
            是否成功
        """
        if direction is None:
            if pulse_count < 0:
                direction = Direction.CCW
                pulse_count = abs(pulse_count)
            else:
                direction = Direction.CW
        
        params = PositionParams(
            direction=direction,
            speed=speed,
            acceleration=acceleration,
            pulse_count=pulse_count,
            motion_mode=motion_mode,
            sync_flag=SyncFlag.SYNC if sync else SyncFlag.IMMEDIATE,
        )
        cmd = Position(self._device_params, params=params)
        return cmd.is_success

    def move_degrees(
        self,
        degrees: float,
        speed: int = 100,
        acceleration: int = 10,
        motion_mode: MotionMode = MotionMode.RELATIVE_LAST,
        microstep: int = 16,
        sync: bool = False,
    ) -> bool:
        """位置模式运动(角度).
        
        电机运动指定的角度。
        
        Args:
            degrees: 角度 (正数为CW方向，负数为CCW方向)
            speed: 速度 (0-3000 RPM)
            acceleration: 加速度档位 (0-255)
            motion_mode: 运动模式
            microstep: 细分值 (用于计算脉冲数)
            sync: 是否使用同步模式
            
        Returns:
            是否成功
        """
        # 计算脉冲数: 1.8°电机，一圈200步，细分后一圈 = 200 * microstep 脉冲
        pulses_per_revolution = 200 * microstep
        pulse_count = int(degrees / 360 * pulses_per_revolution)
        
        return self.move_pulses(
            pulse_count=pulse_count,
            speed=speed,
            acceleration=acceleration,
            motion_mode=motion_mode,
            sync=sync,
        )

    def move_revolutions(
        self,
        revolutions: float,
        speed: int = 100,
        acceleration: int = 10,
        motion_mode: MotionMode = MotionMode.RELATIVE_LAST,
        microstep: int = 16,
        sync: bool = False,
    ) -> bool:
        """位置模式运动(圈数).
        
        电机运动指定的圈数。
        
        Args:
            revolutions: 圈数 (正数为CW方向，负数为CCW方向)
            speed: 速度 (0-3000 RPM)
            acceleration: 加速度档位 (0-255)
            motion_mode: 运动模式
            microstep: 细分值 (用于计算脉冲数)
            sync: 是否使用同步模式
            
        Returns:
            是否成功
        """
        return self.move_degrees(
            degrees=revolutions * 360,
            speed=speed,
            acceleration=acceleration,
            motion_mode=motion_mode,
            microstep=microstep,
            sync=sync,
        )

    def stop(self, sync: bool = False) -> bool:
        """立即停止电机.
        
        Args:
            sync: 是否使用同步模式
            
        Returns:
            是否成功
        """
        sync_flag = SyncFlag.SYNC if sync else SyncFlag.IMMEDIATE
        cmd = EStop(self._device_params, sync_flag=sync_flag)
        return cmd.is_success

    @staticmethod
    def sync_move(device_params: DeviceParams) -> bool:
        """触发多机同步运动.
        
        使用广播地址发送，使所有缓存了命令的电机同步开始执行。
        
        Args:
            device_params: 任意一个设备的参数(用于获取串口连接)
            
        Returns:
            是否成功
        """
        cmd = SyncMove(device_params)
        return cmd.is_success

    # ==================== 原点回零命令 ====================

    def set_home_zero(self, store: bool = True) -> bool:
        """设置单圈回零的零点位置.
        
        将当前位置设置为单圈回零的零点位置。
        
        Args:
            store: 是否存储(掉电不丢失)
            
        Returns:
            是否成功
        """
        cmd = SetHomeZero(self._device_params, store=store)
        return cmd.is_success

    def home(
        self,
        mode: HomingMode = HomingMode.NEAREST,
        sync: bool = False,
    ) -> bool:
        """触发回零.
        
        Args:
            mode: 回零模式
            sync: 是否使用同步模式
            
        Returns:
            是否成功
        """
        sync_flag = SyncFlag.SYNC if sync else SyncFlag.IMMEDIATE
        cmd = Home(self._device_params, mode=mode, sync_flag=sync_flag)
        return cmd.is_success

    def stop_home(self) -> bool:
        """强制中断并退出回零操作.
        
        Returns:
            是否成功
        """
        cmd = StopHome(self._device_params)
        return cmd.is_success

    def get_homing_status(self) -> HomingStatus:
        """读取回零状态标志.
        
        Returns:
            回零状态
        """
        cmd = GetHomingStatus(self._device_params)
        return cmd.data

    def get_homing_params(self) -> HomingParams:
        """读取回零参数.
        
        Returns:
            回零参数
        """
        cmd = GetHomingParams(self._device_params)
        return cmd.data

    def set_homing_params(self, params: HomingParams, store: bool = True) -> bool:
        """修改回零参数.
        
        Args:
            params: 回零参数
            store: 是否存储
            
        Returns:
            是否成功
        """
        cmd = SetHomingParams(self._device_params, params=params, store=store)
        return cmd.is_success

    # ==================== 读取系统参数命令 ====================

    def get_version(self) -> VersionParams:
        """读取固件版本和硬件版本.
        
        Returns:
            版本参数
        """
        cmd = GetVersion(self._device_params)
        return cmd.data

    def get_motor_rh(self) -> MotorRHParams:
        """读取相电阻和相电感.
        
        Returns:
            电机RH参数
        """
        cmd = GetMotorRH(self._device_params)
        return cmd.data

    def get_bus_voltage(self) -> int:
        """读取总线电压.
        
        Returns:
            总线电压(mV)
        """
        cmd = GetBusVoltage(self._device_params)
        return cmd.data

    def get_bus_current(self) -> int:
        """读取总线电流.
        
        Returns:
            总线电流(mA)
        """
        cmd = GetBusCurrent(self._device_params)
        return cmd.data

    def get_phase_current(self) -> int:
        """读取相电流.
        
        Returns:
            相电流(mA)
        """
        cmd = GetPhaseCurrent(self._device_params)
        return cmd.data

    def get_encoder(self) -> int:
        """读取线性化编码器值.
        
        Returns:
            编码器值(0-65535表示0-360度)
        """
        cmd = GetEncoder(self._device_params)
        return cmd.data

    def get_encoder_degrees(self) -> float:
        """读取编码器角度.
        
        Returns:
            编码器角度(度)
        """
        encoder = self.get_encoder()
        return (encoder * 360) / 65536

    def get_pulse_count(self) -> int:
        """读取输入脉冲数.
        
        Returns:
            输入脉冲数(带符号)
        """
        cmd = GetPulseCount(self._device_params)
        return cmd.data

    def get_target_position(self) -> float:
        """读取电机目标位置.
        
        Returns:
            目标位置角度(度)
        """
        cmd = GetTargetPosition(self._device_params)
        return cmd.data

    def get_realtime_speed(self) -> int:
        """读取电机实时转速.
        
        Returns:
            实时转速(RPM, 带符号)
        """
        cmd = GetRealtimeSpeed(self._device_params)
        return cmd.data

    def get_realtime_position(self) -> float:
        """读取电机实时位置.
        
        Returns:
            实时位置角度(度)
        """
        cmd = GetRealtimePosition(self._device_params)
        return cmd.data

    def get_position_error(self) -> float:
        """读取电机位置误差.
        
        Returns:
            位置误差角度(度)
        """
        cmd = GetPositionError(self._device_params)
        return cmd.data

    def get_temperature(self) -> int:
        """读取驱动温度.
        
        Returns:
            温度(°C)
        """
        cmd = GetTemperature(self._device_params)
        return cmd.data

    def get_motor_status(self) -> MotorStatus:
        """读取电机状态标志.
        
        Returns:
            电机状态
        """
        cmd = GetMotorStatus(self._device_params)
        return cmd.data

    def get_pid(self) -> PIDParams:
        """读取PID参数.
        
        Returns:
            PID参数
        """
        cmd = GetPID(self._device_params)
        return cmd.data

    def get_config(self) -> ConfigParams:
        """读取驱动配置参数.
        
        Returns:
            配置参数
        """
        cmd = GetConfig(self._device_params)
        return cmd.data

    def get_system_status(self) -> SystemStatusParams:
        """读取系统状态参数.
        
        Returns:
            系统状态参数
        """
        cmd = GetSystemStatus(self._device_params)
        return cmd.data

    # ==================== 设置命令 ====================

    def set_id(self, new_id: int, store: bool = True) -> bool:
        """修改电机ID/地址.
        
        Args:
            new_id: 新ID (1-255)
            store: 是否存储
            
        Returns:
            是否成功
        """
        cmd = SetID(self._device_params, new_id=new_id, store=store)
        if cmd.is_success:
            self._device_params.address = Address(new_id)
        return cmd.is_success

    def set_microstep(self, microstep: int, store: bool = True) -> bool:
        """修改细分值.
        
        Args:
            microstep: 细分值 (1-256)
            store: 是否存储
            
        Returns:
            是否成功
        """
        cmd = SetMicrostep(self._device_params, microstep=microstep, store=store)
        return cmd.is_success

    def set_loop_mode(self, closed_loop: bool = True, store: bool = True) -> bool:
        """修改开环/闭环控制模式.
        
        Args:
            closed_loop: True为闭环模式，False为开环模式
            store: 是否存储
            
        Returns:
            是否成功
        """
        cmd = SetLoopMode(self._device_params, closed_loop=closed_loop, store=store)
        return cmd.is_success

    def set_open_loop_current(self, current_ma: int, store: bool = True) -> bool:
        """修改开环模式工作电流.
        
        Args:
            current_ma: 电流(mA, 0-5000)
            store: 是否存储
            
        Returns:
            是否成功
        """
        cmd = SetOpenLoopCurrent(self._device_params, current_ma=current_ma, store=store)
        return cmd.is_success

    def set_closed_loop_current(self, current_ma: int, store: bool = True) -> bool:
        """修改闭环模式最大电流.
        
        Args:
            current_ma: 电流(mA, 0-5000)
            store: 是否存储
            
        Returns:
            是否成功
        """
        cmd = SetClosedLoopCurrent(self._device_params, current_ma=current_ma, store=store)
        return cmd.is_success

    def set_pid(self, params: PIDParams, store: bool = True) -> bool:
        """修改PID参数.
        
        Args:
            params: PID参数
            store: 是否存储
            
        Returns:
            是否成功
        """
        cmd = SetPID(self._device_params, params=params, store=store)
        return cmd.is_success

    def set_motor_direction(self, direction: Direction = Direction.CW, store: bool = True) -> bool:
        """修改电机运动正方向.
        
        Args:
            direction: 运动方向
            store: 是否存储
            
        Returns:
            是否成功
        """
        cmd = SetMotorDirection(self._device_params, direction=direction, store=store)
        return cmd.is_success

    def set_position_window(self, window_deg: float = 0.8, store: bool = True) -> bool:
        """修改位置到达窗口.
        
        Args:
            window_deg: 位置到达窗口(度)
            store: 是否存储
            
        Returns:
            是否成功
        """
        cmd = SetPositionWindow(self._device_params, window_deg=window_deg, store=store)
        return cmd.is_success

    def set_heartbeat_time(self, time_ms: int = 0, store: bool = True) -> bool:
        """修改心跳保护功能时间.
        
        Args:
            time_ms: 心跳保护时间(毫秒), 0表示关闭
            store: 是否存储
            
        Returns:
            是否成功
        """
        cmd = SetHeartbeatTime(self._device_params, time_ms=time_ms, store=store)
        return cmd.is_success

    def set_auto_run(self, params: AutoRunParams) -> bool:
        """存储一组速度参数，上电自动运行.
        
        Args:
            params: 自动运行参数
            
        Returns:
            是否成功
        """
        cmd = SetAutoRun(self._device_params, params=params)
        return cmd.is_success

    def set_config(self, params: ConfigParams, store: bool = True) -> bool:
        """修改驱动配置参数.
        
        Args:
            params: 配置参数
            store: 是否存储
            
        Returns:
            是否成功
        """
        cmd = SetConfig(self._device_params, params=params, store=store)
        return cmd.is_success

    def set_scale_input(self, enable: bool = False, store: bool = True) -> bool:
        """修改命令速度值是否缩小10倍输入.
        
        Args:
            enable: 是否使能(使能后输入1RPM实际为0.1RPM)
            store: 是否存储
            
        Returns:
            是否成功
        """
        cmd = SetScaleInput(self._device_params, enable=enable, store=store)
        return cmd.is_success

    def set_lock_button(self, lock: bool = False, store: bool = True) -> bool:
        """修改锁定按键功能.
        
        Args:
            lock: 是否锁定
            store: 是否存储
            
        Returns:
            是否成功
        """
        cmd = SetLockButton(self._device_params, lock=lock, store=store)
        return cmd.is_success

    @staticmethod
    def broadcast_get_id(serial_connection: Serial) -> int:
        """广播读取ID地址.
        
        当忘记电机ID地址时，可以单独接线该电机，广播读取该电机的地址。
        
        Args:
            serial_connection: 串口连接
            
        Returns:
            电机ID
        """
        device_params = DeviceParams(
            serial_connection=serial_connection,
            address=Address.BROADCAST,
        )
        cmd = BroadcastGetID(device_params)
        return cmd.data

    # ==================== 便捷方法 ====================

    def is_enabled(self) -> bool:
        """检查电机是否使能.
        
        Returns:
            是否使能
        """
        status = self.get_motor_status()
        return status.enabled

    def is_position_reached(self) -> bool:
        """检查是否到达目标位置.
        
        Returns:
            是否到达
        """
        status = self.get_motor_status()
        return status.position_reached

    def is_stalled(self) -> bool:
        """检查是否堵转.
        
        Returns:
            是否堵转
        """
        status = self.get_motor_status()
        return status.stall_detected or status.stall_protected

    def wait_for_position(self, timeout: float = 10.0, poll_interval: float = 0.1) -> bool:
        """等待电机到达目标位置.
        
        Args:
            timeout: 超时时间(秒)
            poll_interval: 轮询间隔(秒)
            
        Returns:
            是否到达目标位置
        """
        import time
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_position_reached():
                return True
            time.sleep(poll_interval)
        return False

    def __repr__(self) -> str:
        return f"EmmDevice(address={self.address})"

    def __str__(self) -> str:
        return f"Emm步进电机 (地址: {self.address})"
