# -*- coding: utf-8 -*-
"""
控制动作命令模块
包含电机的基础控制和运动控制功能
"""

import time
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..motor_controller_modular import ZDTMotorControllerModular

from ..constants import DefaultValues
from ..utils import validate_speed, validate_position, validate_current, validate_acceleration
from ..constants import FunctionCodes, Parameters


class ControlActionsModule:
    """控制动作命令模块"""
    
    def __init__(self, controller: 'ZDTMotorControllerModular'):
        self.controller = controller
        self.logger = logging.getLogger(__name__)
    
    # ========== 基础控制命令 ==========
    
    def enable(self, multi_sync: bool = False) -> None:
        """
        使能电机
        
        Args:
            multi_sync: 是否启用多机同步
        """
         
        command = self.controller.command_builder.motor_enable(True, multi_sync)
        self.controller._send_command(command, FunctionCodes.MOTOR_ENABLE)
        self.logger.info(f"电机 {self.controller.motor_id} 已使能")
    
    def disable(self, multi_sync: bool = False) -> None:
        """
        失能电机
        
        Args:
            multi_sync: 是否启用多机同步
        """
         
        command = self.controller.command_builder.motor_enable(False, multi_sync)
        self.controller._send_command(command, FunctionCodes.MOTOR_ENABLE)
        self.logger.info(f"电机 {self.controller.motor_id} 已失能")
    
    def stop(self, multi_sync: bool = False) -> None:
        """
        立即停止电机
        
        Args:
            multi_sync: 是否启用多机同步
        """
         
        command = self.controller.command_builder.immediate_stop(multi_sync)
        self.controller._send_command(command, FunctionCodes.IMMEDIATE_STOP)
        self.logger.info(f"电机 {self.controller.motor_id} 已停止")
    
    def sync_motion(self) -> None:
        """触发多机同步运动"""
         
        command = self.controller.command_builder.multi_sync_motion()
        self.controller._send_command(command, FunctionCodes.MULTI_SYNC_MOTION)
        self.logger.info("触发多机同步运动")
    
    # ========== 运动控制命令 ==========
    
    def set_torque(self, current: int, current_slope: int = DefaultValues.DEFAULT_CURRENT_SLOPE,
                   multi_sync: bool = False) -> None:
        """
        设置力矩模式
        
        Args:
            current: 目标电流 (mA, 可以为负数)
            current_slope: 电流斜率 (mA/s)
            multi_sync: 是否启用多机同步
        """
        
        validate_current(abs(current))
        validate_current(current_slope)
        
        direction = Parameters.DIRECTION_NEGATIVE if current < 0 else Parameters.DIRECTION_POSITIVE
        command = self.controller.command_builder.torque_mode(abs(current), current_slope, direction, multi_sync)
        self.controller._send_command(command, FunctionCodes.TORQUE_MODE)
        self.logger.info(f"电机 {self.controller.motor_id} 设置力矩模式: {current}mA")
    
    def set_speed(self, speed: float, acceleration: int = DefaultValues.DEFAULT_ACCELERATION,
                  multi_sync: bool = False) -> None:
        """
        设置速度模式
        
        Args:
            speed: 目标速度 (RPM, 可以为负数)
            acceleration: 加速度 (RPM/s)
            multi_sync: 是否启用多机同步
        """
         
        
        validate_speed(speed)
        validate_acceleration(acceleration)
        
        command = self.controller.command_builder.speed_mode(speed, acceleration, multi_sync)
        self.controller._send_command(command, FunctionCodes.SPEED_MODE)
        self.logger.info(f"电机 {self.controller.motor_id} 设置速度模式: {speed}RPM")
    
    def move_to_position(self, position: float, speed: float = DefaultValues.DEFAULT_SPEED,
                        is_absolute: bool = False, multi_sync: bool = False, 
                        timeout: float = 1.0) -> None:
        """
        直通限速位置模式运动
        
        Args:
            position: 目标位置 (度, 可以为负数)
            speed: 运动速度 (RPM)
            is_absolute: 是否为绝对位置
            multi_sync: 是否启用多机同步
            timeout: 命令确认超时时间 (秒, 对于大位置值建议增加)
        """
         
        
        validate_position(position)
        validate_speed(speed)
        
        command = self.controller.command_builder.position_mode_direct(position, speed, is_absolute, multi_sync)
        self.controller._send_command(command, FunctionCodes.POSITION_MODE_DIRECT, timeout)
        
        pos_type = "绝对" if is_absolute else "相对"
        self.logger.info(f"电机 {self.controller.motor_id} 开始{pos_type}位置运动: {position}度")
    
    def move_to_position_trapezoid(self, position: float, max_speed: float = DefaultValues.DEFAULT_SPEED,
                                  acceleration: int = DefaultValues.DEFAULT_ACCELERATION,
                                  deceleration: int = DefaultValues.DEFAULT_ACCELERATION,
                                  is_absolute: bool = False, multi_sync: bool = False,
                                  timeout: float = 1.0) -> None:
        """
        梯形曲线位置模式运动
        
        Args:
            position: 目标位置 (度, 可以为负数)
            max_speed: 最大速度 (RPM)
            acceleration: 加速度 (RPM/s)
            deceleration: 减速度 (RPM/s)  
            is_absolute: 是否为绝对位置
            multi_sync: 是否启用多机同步
            timeout: 命令确认超时时间 (秒, 对于大位置值建议增加)
        """
         
        
        validate_position(position)
        validate_speed(max_speed)
        validate_acceleration(acceleration)
        validate_acceleration(deceleration)
        
        command = self.controller.command_builder.position_mode_trapezoid(
            position, max_speed, acceleration, deceleration, is_absolute, multi_sync
        )
        self.controller._send_command(command, FunctionCodes.POSITION_MODE_TRAPEZOID, timeout)
        
        pos_type = "绝对" if is_absolute else "相对"
        self.logger.info(f"电机 {self.controller.motor_id} 开始梯形{pos_type}位置运动: {position}度")
    
    # ========== 便捷方法 ==========
    
    def is_enabled(self) -> bool:
        """检查电机是否使能"""
        try:
            status = self.controller.read_parameters.get_motor_status()
            return status.enabled
        except:
            return False
    
    def is_in_position(self) -> bool:
        """检查电机是否到位"""
        try:
            status = self.controller.read_parameters.get_motor_status()
            return status.in_position
        except:
            return False
    
    def is_stalled(self) -> bool:
        """检查电机是否堵转"""
        try:
            status = self.controller.read_parameters.get_motor_status()
            return status.stalled
        except:
            return False
    
    def wait_for_position(self, timeout: float = 10.0, check_interval: float = 0.1) -> bool:
        """
        等待电机到位
        
        Args:
            timeout: 超时时间 (秒)
            check_interval: 检查间隔 (秒)
            
        Returns:
            bool: 是否到位
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.is_in_position():
                return True
            time.sleep(check_interval)
        
        return False
    
    # ========== 回零控制命令 ==========
    
    def trigger_homing(self, homing_mode: int = 0, multi_sync: bool = False) -> None:
        """
        触发回零
        
        Args:
            homing_mode: 回零模式 (0=就近回零, 1=方向回零, 2=无限位碰撞回零, 3=限位回零, 4=绝对零点, 5=上次掉电位置)
            multi_sync: 是否启用多机同步
        """
         
        command = self.controller.command_builder.trigger_homing(homing_mode, multi_sync)
        self.controller._send_command(command, FunctionCodes.TRIGGER_HOMING)
        mode_names = {
            0: "就近回零",
            1: "方向回零",
            2: "无限位碰撞回零",
            3: "限位回零",
            4: "回到绝对位置坐标零点",
            5: "回到上次掉电位置角度",
        }
        mode_name = mode_names.get(homing_mode, f"模式{homing_mode}")
        self.logger.info(f"电机 {self.controller.motor_id} 开始{mode_name}")
    
    def force_stop_homing(self) -> None:
        """强制停止回零"""
         
        command = self.controller.command_builder.force_stop_homing()
        self.controller._send_command(command, FunctionCodes.FORCE_STOP_HOMING)
        self.logger.info(f"电机 {self.controller.motor_id} 强制停止回零")
    
    def set_zero_position(self, save_to_chip: bool = True) -> None:
        """
        设置当前位置为零点
        
        Args:
            save_to_chip: 是否保存到芯片
        """
         
        command = self.controller.command_builder.set_zero_position(save_to_chip)
        self.controller._send_command(command, FunctionCodes.SET_ZERO_POSITION)
        save_info = "已保存到芯片" if save_to_chip else "未保存到芯片"
        self.logger.info(f"电机 {self.controller.motor_id} 设置零点位置 ({save_info})")
    
    def trigger_encoder_calibration(self) -> None:
        """触发编码器校准"""
         
        command = self.controller.command_builder.trigger_encoder_calibration()
        self.controller._send_command(command, FunctionCodes.TRIGGER_ENCODER_CALIBRATION)
        self.logger.info(f"电机 {self.controller.motor_id} 开始编码器校准")
    
    def modify_homing_parameters(self, mode: int = 0, direction: int = 0, speed: int = 30,
                                timeout: int = 10000, collision_detection_speed: int = 300,
                                collision_detection_current: int = 800, collision_detection_time: int = 60,
                                auto_homing_enabled: bool = False, save_to_chip: bool = True) -> None:
        """
        修改回零参数
        
        Args:
            mode: 回零模式 (0=就近回零)
            direction: 回零方向 (0=顺时针, 1=逆时针)
            speed: 回零速度 (RPM)
            timeout: 回零超时时间 (ms)
            collision_detection_speed: 碰撞检测速度 (RPM)
            collision_detection_current: 碰撞检测电流 (mA)
            collision_detection_time: 碰撞检测时间 (ms)
            auto_homing_enabled: 是否启用上电自动回零
            save_to_chip: 是否保存到芯片
        """
         
        from ..commands import HomingParameters
        
        params = HomingParameters(
            mode=mode,
            direction=direction,
            speed=speed,
            timeout=timeout,
            collision_detection_speed=collision_detection_speed,
            collision_detection_current=collision_detection_current,
            collision_detection_time=collision_detection_time,
            auto_homing_enabled=auto_homing_enabled
        )
        
        command = self.controller.command_builder.modify_homing_parameters(params, save_to_chip)
        self.controller._send_command(command, FunctionCodes.MODIFY_HOMING_PARAMS)
        
        