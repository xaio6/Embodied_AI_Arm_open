# -*- coding: utf-8 -*-
"""
ZDT闭环驱动板模块化电机控制API
"""

import time
import logging
from typing import Optional, Dict, Any, Tuple, ClassVar

from .can_interface import SLCANInterface, create_can_interface
from .commands import (
    ZDTCommandBuilder, ZDTCommandParser, CommandResponse,
    MotorStatus, HomingStatus, HomingParameters, PIDParameters
)
from .constants import (
    FunctionCodes, StatusCodes, Parameters, DefaultValues
)
from .utils import (
    validate_motor_id, validate_speed, validate_position, validate_current,
    validate_acceleration, motor_speed_to_rpm, motor_position_to_degree,
    motor_position_error_to_degree, encoder_raw_to_degree, encoder_calibrated_to_degree,
    format_hex_data
)
from .exceptions import (
    ZDTMotorException, CommandException, ConditionNotMetException,
    MotorNotEnabledException, StallProtectionException, HomingInProgressException,
    TimeoutException, InvalidParameterException
)

# 导入各个功能模块
from .modules import (
    ControlActionsModule,
    HomingCommandsModule,
    TriggerActionsModule,
    ReadParametersModule,
    ModifyParametersModule
)


class ZDTMotorControllerModular:
    """ZDT电机控制器模块化API
    
    支持单电机和多电机场景：
    - 单电机：每个实例独立管理CAN接口
    - 多电机：多个实例共享同一个CAN接口，通过电机ID区分
    """
    
    # 类级别的共享CAN接口缓存 {接口标识: (接口实例, 引用计数)}
    _shared_interfaces: ClassVar[Dict[str, Tuple[SLCANInterface, int]]] = {}
    
    def __init__(self, motor_id: Optional[int] = None, interface_type: str = "slcan", 
                 shared_interface: bool = True, **kwargs):
        """
        初始化ZDT电机控制器
        
        Args:
            motor_id: 电机ID (0-255, 可选，可在连接时指定)
            interface_type: 接口类型 (默认为"slcan")
            shared_interface: 是否使用共享接口模式 (默认True，适合多电机)
            **kwargs: 接口参数 (例如: port='COM18', baudrate=500000)
        """
        self.motor_id = motor_id  # 现在可以为None
        self.interface_type = interface_type
        self.interface_kwargs = kwargs
        self.shared_interface = shared_interface
        self.can_interface: Optional[SLCANInterface] = None
        self.logger = logging.getLogger(__name__)
        
        # 生成接口标识符（用于共享接口）
        self._interface_key = self._generate_interface_key()
        self._owns_interface = False  # 标记是否拥有接口的所有权

        # 命令构建器和解析器
        self.command_builder = ZDTCommandBuilder()
        self.command_parser = ZDTCommandParser()
        
        # 缓存的状态信息
        self._last_motor_status: Optional[MotorStatus] = None
        self._last_homing_status: Optional[HomingStatus] = None
        
        # 初始化各个功能模块
        self.control_actions = ControlActionsModule(self)
        self.homing_commands = HomingCommandsModule(self)
        self.trigger_actions = TriggerActionsModule(self)
        self.read_parameters = ReadParametersModule(self)
        self.modify_parameters = ModifyParametersModule(self)
    
    def _generate_interface_key(self) -> str:
        """生成接口标识符"""
        # 基于接口类型和关键参数生成唯一标识
        key_parts = [self.interface_type]
        
        # 添加关键参数到key中
        if 'port' in self.interface_kwargs:
            key_parts.append(f"port={self.interface_kwargs['port']}")
        if 'baudrate' in self.interface_kwargs:
            key_parts.append(f"baudrate={self.interface_kwargs['baudrate']}")
            
        return "_".join(key_parts)
    
    def connect(self, motor_id: Optional[int] = None) -> None:
        """
        连接到电机
        
        Args:
            motor_id: 电机ID (0-255, 如果未在初始化时指定则必须在此指定)
        """
        # 如果提供了motor_id参数，则更新当前的motor_id
        if motor_id is not None:
            self.motor_id = motor_id
        
        # 确保motor_id已设置
        if self.motor_id is None:
            raise ValueError("必须指定motor_id，可以在初始化时或连接时指定")
        
        # 验证motor_id有效性
        validate_motor_id(self.motor_id)
        
        # 连接CAN接口
        if self.can_interface is None:
            if self.shared_interface:
                self._connect_shared_interface()
            else:
                self._connect_private_interface()
        
        self.logger.info(f"电机 {self.motor_id} 已连接")
    
    def _connect_shared_interface(self) -> None:
        """连接共享CAN接口"""
        if self._interface_key in self._shared_interfaces:
            # 使用现有的共享接口
            interface, ref_count = self._shared_interfaces[self._interface_key]
            self.can_interface = interface
            self._shared_interfaces[self._interface_key] = (interface, ref_count + 1)
            self.logger.debug(f"使用共享CAN接口: {self._interface_key} (引用计数: {ref_count + 1})")
        else:
            # 创建新的共享接口
            interface = create_can_interface(self.interface_type, **self.interface_kwargs)
            interface.connect()
            self.can_interface = interface
            self._shared_interfaces[self._interface_key] = (interface, 1)
            self._owns_interface = True
            self.logger.debug(f"创建新的共享CAN接口: {self._interface_key}")
    
    def _connect_private_interface(self) -> None:
        """连接私有CAN接口（单电机模式）"""
        self.can_interface = create_can_interface(self.interface_type, **self.interface_kwargs)
        self.can_interface.connect()
        self._owns_interface = True
        self.logger.debug(f"创建私有CAN接口: {self._interface_key}")
    
    def set_motor_id(self, motor_id: int) -> None:
        """
        设置电机ID (用于动态切换电机地址)
        
        Args:
            motor_id: 新的电机ID (0-255)
        """
        validate_motor_id(motor_id)
        self.motor_id = motor_id
    
    def disconnect(self) -> None:
        """断开电机连接"""
        if self.can_interface:
            if self.shared_interface and self._interface_key in self._shared_interfaces:
                # 处理共享接口
                interface, ref_count = self._shared_interfaces[self._interface_key]
                if ref_count > 1:
                    # 减少引用计数
                    self._shared_interfaces[self._interface_key] = (interface, ref_count - 1)
                    self.logger.debug(f"减少共享接口引用计数: {self._interface_key} (剩余: {ref_count - 1})")
                else:
                    # 最后一个引用，关闭接口
                    interface.disconnect()
                    del self._shared_interfaces[self._interface_key]
                    self.logger.debug(f"关闭共享CAN接口: {self._interface_key}")
            else:
                # 私有接口或拥有接口所有权时直接关闭
                if self._owns_interface:
                    self.can_interface.disconnect()
                    self.logger.debug(f"关闭私有CAN接口: {self._interface_key}")
            
            self.can_interface = None
            self._owns_interface = False
        
        self.logger.info(f"电机 {self.motor_id} 已断开连接")
    
    @classmethod
    def get_shared_interface_info(cls) -> Dict[str, int]:
        """获取当前共享接口信息 (调试用)
        
        Returns:
            Dict[str, int]: 接口标识 -> 引用计数
        """
        return {key: ref_count for key, (_, ref_count) in cls._shared_interfaces.items()}
    
    @classmethod
    def close_all_shared_interfaces(cls) -> None:
        """关闭所有共享接口 (清理用)"""
        for interface_key, (interface, ref_count) in list(cls._shared_interfaces.items()):
            try:
                interface.disconnect()
            except Exception as e:
                logging.getLogger(__name__).warning(f"关闭共享接口 {interface_key} 时出现警告: {e}")
        
        cls._shared_interfaces.clear()
        logging.getLogger(__name__).info("已关闭所有共享CAN接口")
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()
    
    def _send_command(self, command_data: list, expected_function_code: int,
                     timeout: float = 1.0) -> CommandResponse:
        """
        发送命令并处理响应
        
        Args:
            command_data: 命令数据
            expected_function_code: 期望的功能码
            timeout: 超时时间
            
        Returns:
            CommandResponse: 命令响应
        """
        # 确保已连接且motor_id已设置
        if self.can_interface is None:
            raise RuntimeError("CAN接口未连接，请先调用connect()")
        if self.motor_id is None:
            raise RuntimeError("motor_id未设置，请先设置电机ID")
        
        try:
            # 广播命令(motor_id=0)不期待响应
            if self.motor_id == 0:
                # 直接发送广播命令，不等待响应
                self.can_interface.send_message(self.motor_id, command_data)
                self.logger.debug(f"发送广播命令: {[hex(x) for x in command_data]}")
                
                # 返回成功响应（广播命令没有实际响应）
                return CommandResponse(
                    success=True,
                    status_code=0,
                    data=None,
                    error_message=None
                )
            else:
                # 普通命令，期待响应
                response_data = self.can_interface.send_command_and_receive_response(
                    self.motor_id, command_data, timeout
                )
                
                response = self.command_parser.parse_response(response_data, expected_function_code)
                
                if not response.success:
                    self.logger.warning(f"命令执行失败: {response.error_message}")
                    
                    # 根据状态码抛出特定异常
                    if response.status_code == StatusCodes.CONDITION_NOT_MET:
                        # 尝试获取更详细的错误信息
                        motor_status = self.read_parameters.get_motor_status()
                        if motor_status and not motor_status.enabled:
                            raise MotorNotEnabledException()
                        elif motor_status and motor_status.stall_protection:
                            raise StallProtectionException()
                        else:
                            raise ConditionNotMetException(response.error_message)
                    else:
                        raise CommandException(response.error_message, response.status_code)
                
                return response
        
        except TimeoutException:
            self.logger.error(f"电机 {self.motor_id} 通信超时")
            raise
        except Exception as e:
            self.logger.error(f"电机 {self.motor_id} 命令执行失败: {e}")
            raise

    # ========= 多电机命令（Y板） =========
    def multi_motor_command(self, per_motor_commands: list, expected_ack_motor_id: int = 1,
                            timeout: float = 1.0, wait_ack: bool = True, mode: str = None) -> CommandResponse:
        """
        发送多电机命令（Y板），一次性下发多条“地址+功能码+参数+6B”的指令。
        - per_motor_commands: List[List[int]]，每项为完整的“地址+功能码+参数+6B”。
        - expected_ack_motor_id: 期望确认的电机ID（运动类默认1）。
        - wait_ack: 是否等待确认（若设备Response=None/Reached导致不回确认，可设False）。
        - mode: 'control' 或 'read'（不传则自动判断）。禁止在一次调用中混合两类命令。
        """
        from .constants import FunctionCodes
        # 校验命令类型：仅允许 F5/F6/FB/FD（控制）或 0x36（读取实时位置），且不可混合
        allowed_control = {FunctionCodes.TORQUE_MODE, FunctionCodes.SPEED_MODE,
                           FunctionCodes.POSITION_MODE_DIRECT, FunctionCodes.POSITION_MODE_TRAPEZOID}
        allowed_read = {FunctionCodes.READ_REALTIME_POSITION}
        seen_control = False
        seen_read = False
        for i, cmd in enumerate(per_motor_commands):
            if not cmd or len(cmd) < 2:
                raise ValueError(f"第{i+1}条子命令无效，长度不足：{cmd}")
            func = cmd[1]  # 格式：地址 + 功能码 + ... + 6B
            if func in allowed_control:
                seen_control = True
            elif func in allowed_read:
                seen_read = True
            else:
                raise ValueError(f"第{i+1}条子命令包含不支持的功能码: 0x{func:02X}（仅允许F5/F6/FB/FD/36）")
        # 显式模式限制
        if mode is not None:
            m = mode.strip().lower()
            if m == 'control' and seen_read:
                raise ValueError("当前调用限定为控制类，但检测到读取类(0x36)命令")
            if m == 'read' and seen_control:
                raise ValueError("当前调用限定为读取类，但检测到控制类(F5/F6/FB/FD)命令")
        # 禁止混合
        if seen_control and seen_read:
            raise ValueError("多电机命令禁止将控制类(F5/F6/FB/FD)与读取类(0x36)混合，请拆成两次调用")
        # 组帧：地址(0x00) + 功能码(0xAA) + 长度 + 命令串 + 0x6B
        # 调用底层接口发送到0号地址，接收来自 expected_ack_motor_id 的响应
        if self.can_interface is None:
            raise ValueError("CAN接口未连接")
        # 仅构建 AA 帧体（AA + len + payload + 6B）
        frame_body = self.command_builder.build_y42_multi_motor_frame(per_motor_commands)
        # 发送时需要在前面加上地址(00)
        full_command = [FunctionCodes.Y42_MULTI_MOTOR] + frame_body[1:]  # 保持AA作为功能码位置
        if wait_ack:
            try:
                resp = self.can_interface.send_command_and_receive_response_from(
                    motor_id=0,
                    command_data=full_command,
                    expected_response_motor_id=expected_ack_motor_id,
                    timeout=timeout
                )
                return CommandResponse(success=True, status_code=0x02, data=resp)
            except Exception as e:
                # 可能由于Response=None/Reached导致不回确认，降级为不等待
                self.logger.warning(f"多电机命令等待确认超时/失败，降级为不等待确认: {e}")
                self.can_interface.send_command_no_response(0, full_command)
                return CommandResponse(success=True, status_code=0x02, data=None)
        else:
            self.can_interface.send_command_no_response(0, full_command)
            return CommandResponse(success=True, status_code=0x02, data=None)
    
    def send_broadcast_command(self, command_data: list) -> None:
        """
        发送广播命令（不期待响应）
        
        Args:
            command_data: 命令数据
        """
        if self.can_interface is None:
            raise RuntimeError("CAN接口未连接，请先调用connect()")
        
        # 直接发送广播命令到ID=0
        self.can_interface.send_message(0, command_data)
        self.logger.debug(f"发送广播命令: {[hex(x) for x in command_data]}")


