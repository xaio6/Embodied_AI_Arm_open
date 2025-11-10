# -*- coding: utf-8 -*-
"""
触发动作命令模块
包含各种工具和触发类命令
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..motor_controller_modular import ZDTMotorControllerModular


class TriggerActionsModule:
    """触发动作命令模块"""
    
    def __init__(self, controller: 'ZDTMotorControllerModular'):
        self.controller = controller
        self.logger = logging.getLogger(__name__)
    
    def clear_position(self) -> None:
        """清零当前位置"""
        from ..constants import FunctionCodes
        command = self.controller.command_builder.clear_position()
        self.controller._send_command(command, FunctionCodes.CLEAR_POSITION)
        self.logger.info(f"电机 {self.controller.motor_id} 位置已清零")
    
    def release_stall_protection(self) -> None:
        """解除堵转保护"""
        from ..constants import FunctionCodes
        command = self.controller.command_builder.release_stall_protection()
        self.controller._send_command(command, FunctionCodes.RELEASE_STALL_PROTECTION)
        self.logger.info(f"电机 {self.controller.motor_id} 已解除堵转保护")
    
    def trigger_encoder_calibration(self) -> None:
        """触发编码器校准"""
        from ..constants import FunctionCodes
        command = self.controller.command_builder.trigger_encoder_calibration()
        self.controller._send_command(command, FunctionCodes.TRIGGER_ENCODER_CALIBRATION)
        self.logger.info(f"电机 {self.controller.motor_id} 开始编码器校准")
    
    def save_parameters_to_chip(self) -> None:
        """保存参数到芯片 (如果支持)"""
        # 注意：这个功能可能需要根据实际协议添加
        self.logger.info(f"电机 {self.controller.motor_id} 保存参数到芯片")
        # TODO: 实现保存参数到芯片的具体命令
    
    def reset_motor(self) -> None:
        """重置电机 (如果支持)"""
        # 注意：这个功能可能需要根据实际协议添加
        self.logger.info(f"电机 {self.controller.motor_id} 重置")
        # TODO: 实现重置电机的具体命令
    
    def emergency_stop(self) -> None:
        """紧急停止 (立即停止所有运动)"""
        try:
            # 使用现有的停止命令
            self.controller.control_actions.stop()
            # 如果电机使能，则失能
            if self.controller.control_actions.is_enabled():
                self.controller.control_actions.disable()
            self.logger.info(f"电机 {self.controller.motor_id} 紧急停止完成")
        except Exception as e:
            self.logger.error(f"电机 {self.controller.motor_id} 紧急停止失败: {e}")
            raise 