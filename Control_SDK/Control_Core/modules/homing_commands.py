# -*- coding: utf-8 -*-
"""
原点回零命令模块
包含电机回零相关的所有功能
"""

import time
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..motor_controller_modular import ZDTMotorControllerModular

from ..commands import HomingStatus


class HomingCommandsModule:
    """原点回零命令模块"""
    
    def __init__(self, controller: 'ZDTMotorControllerModular'):
        self.controller = controller
        self.logger = logging.getLogger(__name__)
    
    def set_zero_position(self, save_to_chip: bool = True) -> None:
        """
        设置当前位置为零点
        
        Args:
            save_to_chip: 是否保存到芯片
        """
        from ..constants import FunctionCodes
        command = self.controller.command_builder.set_zero_position(save_to_chip)
        self.controller._send_command(command, FunctionCodes.SET_ZERO_POSITION)
        self.logger.info(f"电机 {self.controller.motor_id} 设置零点位置")
    
    def start_homing(self, homing_mode: int = None, multi_sync: bool = False) -> None:
        """
        开始回零
        
        Args:
            homing_mode: 回零模式 (默认使用最近回零模式)
            multi_sync: 是否启用多机同步
        """
        from ..constants import FunctionCodes, Parameters
        
        if homing_mode is None:
            homing_mode = Parameters.HOMING_MODE_NEAREST
            
        command = self.controller.command_builder.trigger_homing(homing_mode, multi_sync)
        self.controller._send_command(command, FunctionCodes.TRIGGER_HOMING)
        self.logger.info(f"电机 {self.controller.motor_id} 开始回零")
    
    def stop_homing(self) -> None:
        """强制停止回零"""
        from ..constants import FunctionCodes
        command = self.controller.command_builder.force_stop_homing()
        self.controller._send_command(command, FunctionCodes.FORCE_STOP_HOMING)
        self.logger.info(f"电机 {self.controller.motor_id} 停止回零")
    
    def get_homing_status(self) -> HomingStatus:
        """获取回零状态"""
        from ..constants import FunctionCodes
        from ..exceptions import CommandException
        
        command = self.controller.command_builder.read_homing_status()
        response = self.controller._send_command(command, FunctionCodes.READ_HOMING_STATUS)
        
        if response.data and len(response.data) >= 1:
            status = self.controller.command_parser.parse_homing_status(response.data[0])
            self.controller._last_homing_status = status
            return status
        else:
            raise CommandException("回零状态数据无效")
    
    def wait_for_homing_complete(self, timeout: float = 30.0, check_interval: float = 0.5) -> bool:
        """
        等待回零完成
        
        Args:
            timeout: 超时时间 (秒)
            check_interval: 检查间隔 (秒)
            
        Returns:
            bool: 回零是否成功完成
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_homing_status()
            
            if not status.homing_in_progress:
                if status.homing_failed:
                    self.logger.error(f"电机 {self.controller.motor_id} 回零失败")
                    return False
                else:
                    self.logger.info(f"电机 {self.controller.motor_id} 回零完成")
                    return True
            
            time.sleep(check_interval)
        
        self.logger.warning(f"电机 {self.controller.motor_id} 回零超时")
        return False
    
    def is_homing_in_progress(self) -> bool:
        """检查是否正在回零"""
        try:
            status = self.get_homing_status()
            return status.homing_in_progress
        except:
            return False
    
    def is_homing_failed(self) -> bool:
        """检查回零是否失败"""
        try:
            status = self.get_homing_status()
            return status.homing_failed
        except:
            return False
    
    def is_encoder_ready(self) -> bool:
        """检查编码器是否就绪"""
        try:
            status = self.get_homing_status()
            return status.encoder_ready
        except:
            return False 