# -*- coding: utf-8 -*-
"""
ZDT闭环驱动板Python SDK

这是一个用于控制ZDT闭环驱动板的Python库，支持通过USB转CAN接口进行通信。

主要功能：
- 电机使能/失能控制
- 力矩模式、速度模式、位置模式控制
- 原点回零功能
- 实时状态监控
- 多机同步控制

模块化使用示例：
```python
from Control_Core import ZDTMotorController

# 使用模块化控制器
with ZDTMotorController(motor_id=1, interface_type="slcan", port="COM18") as motor:
    # 通过模块访问功能
    motor.control_actions.enable()
    motor.control_actions.move_to_position(360.0)
    
    # 读取参数
    position = motor.read_parameters.get_position()
    status = motor.read_parameters.get_motor_status()
    
    # 回零操作
    motor.homing_commands.start_homing()
    motor.homing_commands.wait_for_homing_complete()
```
"""

import logging
from typing import Optional

__version__ = "1.0.0"
__author__ = "ZDT SDK Team"
__email__ = "support@zdt.com"

# 导入主要类和函数
from .motor_controller_modular import ZDTMotorControllerModular as ZDTMotorController
from .driver_manager import DriverManager
from .base import BaseMotorController, BaseCommandBuilder, BaseCommandParser

# 注册默认的ZDT驱动
from .commands import ZDTCommandBuilder, ZDTCommandParser
DriverManager.register_driver("zdt", ZDTMotorController, ZDTCommandBuilder, ZDTCommandParser)

from .can_interface import (
    SLCANInterface, create_can_interface
)
from .commands import (
    ZDTCommandBuilder, ZDTCommandParser,
    CommandResponse, MotorStatus, HomingStatus, PIDParameters, HomingParameters,
    DriveParameters, SystemStatus
)
from .constants import (
    FunctionCodes, AuxCodes, StatusCodes, Parameters,
    MotorStatusFlags, HomingStatusFlags, DefaultValues
)
from .exceptions import (
    ZDTMotorException, CommunicationException, CANInterfaceException,
    CommandException, ConditionNotMetException, MotorNotEnabledException,
    StallProtectionException, HomingInProgressException, TimeoutException,
    InvalidParameterException, DeviceNotFoundException, ChecksumException,
    InvalidResponseException
)
from .utils import (
    rpm_to_motor_speed, motor_speed_to_rpm,
    degree_to_motor_position, motor_position_to_degree,
    encoder_raw_to_degree, encoder_calibrated_to_degree,
    format_hex_data, validate_motor_id, validate_speed,
    validate_position, validate_current, validate_acceleration
)

# 导入模块化组件
from .modules import (
    ControlActionsModule,
    HomingCommandsModule,
    TriggerActionsModule,
    ReadParametersModule,
    ModifyParametersModule
)

# 定义导出的公共接口
__all__ = [
    # 主要控制类
    "ZDTMotorController",  # 模块化版本
    
    # 模块化组件
    "ControlActionsModule",
    "HomingCommandsModule", 
    "TriggerActionsModule",
    "ReadParametersModule",
    "ModifyParametersModule",
    
    # CAN接口类
    "SLCANInterface",
    "create_can_interface",
    
    # 命令类
    "ZDTCommandBuilder",
    "ZDTCommandParser",
    
    # 数据结构
    "CommandResponse",
    "MotorStatus",
    "HomingStatus", 
    "HomingParameters",
    "PIDParameters",
    "DriveParameters",
    "SystemStatus",
    
    # 常量类
    "FunctionCodes",
    "AuxCodes",
    "StatusCodes",
    "Parameters",
    "MotorStatusFlags",
    "HomingStatusFlags",
    "DefaultValues",
    
    # 异常类
    "ZDTMotorException",
    "CommunicationException",
    "CANInterfaceException",
    "CommandException",
    "ConditionNotMetException",
    "MotorNotEnabledException",
    "StallProtectionException",
    "HomingInProgressException",
    "TimeoutException",
    "InvalidParameterException",
    "DeviceNotFoundException",
    "ChecksumException",
    "InvalidResponseException",
    
    # 工具函数
    "rpm_to_motor_speed",
    "motor_speed_to_rpm",
    "degree_to_motor_position", 
    "motor_position_to_degree",
    "encoder_raw_to_degree",
    "encoder_calibrated_to_degree",
    "format_hex_data",
    "validate_motor_id",
    "validate_speed",
    "validate_position",
    "validate_current",
    "validate_acceleration",
    
    # 便捷函数
    "create_motor_controller",
    "setup_logging"
]


def create_motor_controller(motor_id: Optional[int] = None, interface_type: str = "slcan", 
                           driver_name: str = "zdt", **kwargs) -> BaseMotorController:
    """
    创建电机控制器的便捷函数
    
    Args:
        motor_id: 电机ID (0-255, 可选，可在连接时指定)
        interface_type: CAN接口类型 (默认为"slcan")
        driver_name: 驱动名称 (默认为"zdt")
        **kwargs: 其他参数
        
    Returns:
        BaseMotorController: 电机控制器实例
    """
    controller_cls = DriverManager.get_controller_class(driver_name)
    return controller_cls(motor_id, interface_type=interface_type, **kwargs)


def setup_logging(level=logging.INFO):
    """
    设置日志配置
    
    Args:
        level: 日志级别
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def get_version() -> str:
    """获取SDK版本号"""
    return __version__


def get_supported_interfaces() -> list:
    """获取支持的CAN接口类型"""
    return ["slcan"]


# 打印欢迎信息
def print_welcome():
    """打印SDK欢迎信息"""
    print(f"""
    ========================================
    ZDT闭环驱动板 Python SDK v{__version__}
    ========================================
    
    支持的接口类型: {', '.join(get_supported_interfaces())}
    
    快速开始:
    1. 安装依赖: pip install python-can pyserial
    2. 创建控制器: motor = ZDTMotorController(motor_id=1)
    3. 连接并控制: 
       with motor:
           motor.control_actions.enable()
           motor.control_actions.move_to_position(360)
    
    模块化使用:
    - motor.control_actions: 控制动作命令
    - motor.homing_commands: 原点回零命令  
    - motor.trigger_actions: 触发动作命令
    - motor.read_parameters: 读取参数命令
    - motor.modify_parameters: 修改参数命令
    
    文档和示例请查看 examples/ 文件夹
    ========================================
    """)


# 版本检查
def check_dependencies():
    """检查依赖包是否安装"""
    try:
        import can
        print(f"✓ python-can 已安装 (版本: {can.__version__})")
    except ImportError:
        print("✗ python-can 未安装，请运行: pip install python-can")
    
    try:
        import serial
        print(f"✓ pyserial 已安装 (版本: {serial.__version__})")
    except ImportError:
        print("✗ pyserial 未安装，请运行: pip install pyserial")


# 自动检查依赖（可选）
# check_dependencies() 