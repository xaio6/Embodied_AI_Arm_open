# -*- coding: utf-8 -*-
"""
修改参数命令模块
包含各种参数设置和修改功能
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..motor_controller_modular import ZDTMotorControllerModular

from ..exceptions import CommandException


class ModifyParametersModule:
    """修改参数命令模块"""
    
    def __init__(self, controller: 'ZDTMotorControllerModular'):
        self.controller = controller
        self.logger = logging.getLogger(__name__)
    
    # ========== PID参数设置 ==========
    
    def set_pid_parameters(self, trapezoid_position_kp: int = None, 
                          direct_position_kp: int = None,
                          speed_kp: int = None, 
                          speed_ki: int = None) -> None:
        """
        设置PID参数
        
        Args:
            trapezoid_position_kp: 梯形曲线位置模式位置环Kp
            direct_position_kp: 直通限速位置模式位置环Kp
            speed_kp: 速度环Kp
            speed_ki: 速度环Ki
        """
        # 注意：这个功能需要根据实际协议实现
        self.logger.info(f"电机 {self.controller.motor_id} 设置PID参数")
        # TODO: 实现PID参数设置的具体命令
        
        if trapezoid_position_kp is not None:
            self.logger.info(f"设置梯形位置环Kp: {trapezoid_position_kp}")
        if direct_position_kp is not None:
            self.logger.info(f"设置直通位置环Kp: {direct_position_kp}")
        if speed_kp is not None:
            self.logger.info(f"设置速度环Kp: {speed_kp}")
        if speed_ki is not None:
            self.logger.info(f"设置速度环Ki: {speed_ki}")
    
    # ========== 电机参数设置 ==========
    
    def set_motor_id(self, new_motor_id: int) -> None:
        """
        设置电机ID
        
        Args:
            new_motor_id: 新的电机ID (1-255)
        """
        if not (1 <= new_motor_id <= 255):
            raise ValueError("电机ID必须在1-255范围内")
        from ..constants import FunctionCodes
        # 构建命令（默认保存，避免误改；如需掉电保存可扩展参数）
        command = self.controller.command_builder.modify_motor_id(new_motor_id)
        # 下发命令
        resp = self.controller._send_command(command, FunctionCodes.MODIFY_ID_ADDRESS)
        if resp and resp.success:
            self.logger.info(f"电机 {self.controller.motor_id} 修改ID命令下发成功，目标新ID: {new_motor_id}")
        else:
            raise CommandException(f"修改电机ID失败: {getattr(resp, 'error_message', '未知错误')}")
    
    def set_baudrate(self, baudrate: int) -> None:
        """
        设置通信波特率
        
        Args:
            baudrate: 波特率 (例如: 500000, 1000000)
        """
        valid_baudrates = [125000, 250000, 500000, 1000000]
        if baudrate not in valid_baudrates:
            raise ValueError(f"波特率必须是以下值之一: {valid_baudrates}")
        
        # 注意：这个功能需要根据实际协议实现
        self.logger.info(f"电机 {self.controller.motor_id} 设置波特率: {baudrate}")
        # TODO: 实现设置波特率的具体命令
    
    def set_acceleration_limits(self, max_acceleration: int) -> None:
        """
        设置加速度限制
        
        Args:
            max_acceleration: 最大加速度 (RPM/s)
        """
        # 注意：这个功能需要根据实际协议实现
        self.logger.info(f"电机 {self.controller.motor_id} 设置最大加速度: {max_acceleration}")
        # TODO: 实现设置加速度限制的具体命令
    
    def set_speed_limits(self, max_speed: float) -> None:
        """
        设置速度限制
        
        Args:
            max_speed: 最大速度 (RPM)
        """
        # 注意：这个功能需要根据实际协议实现
        self.logger.info(f"电机 {self.controller.motor_id} 设置最大速度: {max_speed}")
        # TODO: 实现设置速度限制的具体命令
    
    def set_current_limits(self, max_current: int) -> None:
        """
        设置电流限制
        
        Args:
            max_current: 最大电流 (mA)
        """
        # 注意：这个功能需要根据实际协议实现
        self.logger.info(f"电机 {self.controller.motor_id} 设置最大电流: {max_current}")
        # TODO: 实现设置电流限制的具体命令
    
    # ========== 回零参数设置 ==========
    
    def set_homing_parameters(self, homing_speed: float = None,
                             homing_current: int = None,
                             homing_timeout: float = None) -> None:
        """
        设置回零参数
        
        Args:
            homing_speed: 回零速度 (RPM)
            homing_current: 回零电流 (mA)
            homing_timeout: 回零超时时间 (秒)
        """
        # 注意：这个功能需要根据实际协议实现
        self.logger.info(f"电机 {self.controller.motor_id} 设置回零参数")
        # TODO: 实现设置回零参数的具体命令
        
        if homing_speed is not None:
            self.logger.info(f"设置回零速度: {homing_speed}")
        if homing_current is not None:
            self.logger.info(f"设置回零电流: {homing_current}")
        if homing_timeout is not None:
            self.logger.info(f"设置回零超时: {homing_timeout}")
    
    # ========== 编码器参数设置 ==========
    
    def set_encoder_parameters(self, encoder_resolution: int = None,
                              encoder_direction: int = None) -> None:
        """
        设置编码器参数
        
        Args:
            encoder_resolution: 编码器分辨率
            encoder_direction: 编码器方向 (0: 正向, 1: 反向)
        """
        # 注意：这个功能需要根据实际协议实现
        self.logger.info(f"电机 {self.controller.motor_id} 设置编码器参数")
        # TODO: 实现设置编码器参数的具体命令
        
        if encoder_resolution is not None:
            self.logger.info(f"设置编码器分辨率: {encoder_resolution}")
        if encoder_direction is not None:
            self.logger.info(f"设置编码器方向: {encoder_direction}")
    
    # ========== 保存参数 ==========
    
    def save_parameters_to_flash(self) -> None:
        """保存所有参数到Flash存储器"""
        # 注意：这个功能需要根据实际协议实现
        self.logger.info(f"电机 {self.controller.motor_id} 保存参数到Flash")
        # TODO: 实现保存参数到Flash的具体命令
    
    def restore_default_parameters(self) -> None:
        """恢复默认参数"""
        # 注意：这个功能需要根据实际协议实现
        self.logger.info(f"电机 {self.controller.motor_id} 恢复默认参数")
        # TODO: 实现恢复默认参数的具体命令 
    
    def modify_drive_parameters(self, params, save_to_chip: bool = True):
        """
        修改驱动参数
        
        Args:
            params: 驱动参数结构
            save_to_chip: 是否保存到芯片
            
        Returns:
            CommandResponse: 命令响应
        """
        from ..constants import FunctionCodes
        from ..commands import DriveParameters
        
        command = self.controller.command_builder.modify_drive_parameters(params, save_to_chip)
        response = self.controller._send_command(command, FunctionCodes.MODIFY_DRIVE_PARAMETERS)
        
        if response.success:
            self.logger.info(f"电机 {self.controller.motor_id} 驱动参数修改成功")
            if save_to_chip:
                self.logger.info("参数已保存到芯片")
        else:
            self.logger.error(f"修改驱动参数失败: {response.error_message}")
        
        return response
    
    def set_drive_parameters(self, params, save_to_chip: bool = True):
        """
        设置驱动参数 (modify_drive_parameters的便捷方法)
        
        Args:
            params: 驱动参数结构
            save_to_chip: 是否保存到芯片
            
        Returns:
            CommandResponse: 命令响应
        """
        return self.modify_drive_parameters(params, save_to_chip)
    
    def create_default_drive_parameters(self):
        """
        创建默认的驱动参数
        
        Returns:
            DriveParameters: 默认驱动参数
        """
        from ..commands import DriveParameters
        
        return DriveParameters(
            lock_enabled=False,                     # 锁定按键菜单关闭
            control_mode=1,                         # FOC矢量闭环控制模式
            pulse_port_function=1,                  # 脉冲端口使能脉冲输入控制
            serial_port_function=2,                 # 通讯端口使能串口通讯
            enable_pin_mode=2,                      # En引脚一直有效
            motor_direction=0,                      # 电机顺时针方向
            subdivision=16,                         # 16细分
            subdivision_interpolation=True,         # 使能细分插补
            auto_screen_off=False,                  # 关闭自动熄屏功能
            lpf_intensity=0,                        # 默认强度低通滤波器
            open_loop_current=1200,                 # 开环模式工作电流1200mA
            closed_loop_max_current=2200,           # 闭环模式最大电流2200mA
            max_speed_limit=3000,                   # 闭环模式最大转速3000RPM
            current_loop_bandwidth=1000,            # 电流环带宽1000rad/s
            uart_baudrate=5,                        # 串口波特率115200 (选项5)
            can_baudrate=7,                         # CAN通讯速率500000 (选项7)
            checksum_mode=0,                        # 通讯校验方式0x6B
            response_mode=1,                        # 控制命令应答模式只返回确认收到命令
            position_precision=False,               # 通讯控制输入角度精确度关闭
            stall_protection_enabled=True,          # 使能堵转保护
            stall_protection_speed=8,               # 堵转保护转速阈值8RPM
            stall_protection_current=2000,          # 堵转保护电流阈值2000mA
            stall_protection_time=2000,             # 堵转保护检测时间阈值2000ms
            position_arrival_window=3               # 位置到达窗口0.3度
        )
    
    def create_open_loop_drive_parameters(self):
        """
        创建开环模式的驱动参数配置
        
        Returns:
            DriveParameters: 开环模式驱动参数
        """
        from ..commands import DriveParameters
        
        return DriveParameters(
            lock_enabled=False,                     # 锁定按键菜单关闭
            control_mode=0,                         # 开环控制模式
            pulse_port_function=1,                  # 脉冲端口使能脉冲输入控制
            serial_port_function=2,                 # 通讯端口使能串口通讯
            enable_pin_mode=2,                      # En引脚一直有效
            motor_direction=0,                      # 电机顺时针方向
            subdivision=16,                         # 16细分
            subdivision_interpolation=False,        # 开环模式通常不启用插补
            auto_screen_off=False,                  # 关闭自动熄屏功能
            lpf_intensity=0,                        # 默认强度低通滤波器
            open_loop_current=1500,                 # 开环模式需要更高的工作电流
            closed_loop_max_current=2000,           # 闭环模式最大电流（不常用）
            max_speed_limit=1500,                   # 开环模式转速限制较低
            current_loop_bandwidth=500,             # 较低的电流环带宽
            uart_baudrate=5,                        # 串口波特率115200
            can_baudrate=7,                         # CAN通讯速率500000
            checksum_mode=0,                        # 通讯校验方式0x6B
            response_mode=1,                        # 控制命令应答模式
            position_precision=False,               # 角度精确度关闭
            stall_protection_enabled=False,         # 开环模式通常不启用堵转保护
            stall_protection_speed=5,               # 较低的堵转检测速度
            stall_protection_current=1200,          # 堵转保护电流阈值
            stall_protection_time=2000,             # 堵转保护时间阈值
            position_arrival_window=10              # 较大的位置到达窗口（1.0度）
        )
    
    def create_high_precision_drive_parameters(self):
        """
        创建高精度模式的驱动参数配置
        
        Returns:
            DriveParameters: 高精度模式驱动参数
        """
        from ..commands import DriveParameters
        
        return DriveParameters(
            lock_enabled=False,                     # 锁定按键菜单关闭
            control_mode=1,                         # FOC矢量闭环控制模式
            pulse_port_function=1,                  # 脉冲端口使能脉冲输入控制
            serial_port_function=2,                 # 通讯端口使能串口通讯
            enable_pin_mode=2,                      # En引脚一直有效
            motor_direction=0,                      # 电机顺时针方向
            subdivision=256,                        # 最高细分（256细分）
            subdivision_interpolation=True,         # 使能细分插补
            auto_screen_off=False,                  # 关闭自动熄屏功能
            lpf_intensity=2,                        # 更强的低通滤波器
            open_loop_current=1000,                 # 较低的开环电流
            closed_loop_max_current=1800,           # 适中的闭环最大电流
            max_speed_limit=2000,                   # 适中的最大转速
            current_loop_bandwidth=1500,            # 较高的电流环带宽
            uart_baudrate=5,                        # 串口波特率115200
            can_baudrate=7,                         # CAN通讯速率500000
            checksum_mode=0,                        # 通讯校验方式0x6B
            response_mode=1,                        # 控制命令应答模式
            position_precision=True,                # 启用高精度角度控制
            stall_protection_enabled=True,          # 使能堵转保护
            stall_protection_speed=5,               # 较低的堵转检测速度
            stall_protection_current=1600,          # 堵转保护电流阈值
            stall_protection_time=1500,             # 较短的堵转保护时间
            position_arrival_window=1               # 高精度位置到达窗口（0.1度）
        )
    
    def validate_drive_parameters(self, params) -> None:
        """
        验证驱动参数的有效性
        
        Args:
            params: 驱动参数结构
            
        Raises:
            ValueError: 当参数无效时
        """
        from ..commands import DriveParameters
        
        if not isinstance(params, DriveParameters):
            raise ValueError("参数必须是DriveParameters类型")
        
        # 控制模式验证
        if params.control_mode not in [0, 1]:
            raise ValueError(f"控制模式必须是0(开环)或1(闭环FOC)，当前值: {params.control_mode}")
        
        # 细分验证
        valid_subdivisions = [0, 1, 2, 4, 5, 8, 10, 16, 20, 25, 32, 40, 50, 64, 80, 100, 125, 128, 160, 200, 250, 256]
        if params.subdivision not in valid_subdivisions:
            raise ValueError(f"无效的细分值: {params.subdivision}，有效值: {valid_subdivisions}")
        
        # 电流范围验证
        if not (100 <= params.open_loop_current <= 3000):
            raise ValueError(f"开环电流应在100-3000mA范围内，当前值: {params.open_loop_current}")
        
        if not (100 <= params.closed_loop_max_current <= 3000):
            raise ValueError(f"闭环最大电流应在100-3000mA范围内，当前值: {params.closed_loop_max_current}")
        
        # 速度范围验证
        if not (100 <= params.max_speed_limit <= 6000):
            raise ValueError(f"最大转速应在100-6000RPM范围内，当前值: {params.max_speed_limit}")
        
        # 堵转保护参数验证
        if params.stall_protection_enabled:
            if not (1 <= params.stall_protection_speed <= 100):
                raise ValueError(f"堵转保护转速阈值应在1-100RPM范围内，当前值: {params.stall_protection_speed}")
            
            if not (100 <= params.stall_protection_current <= 3000):
                raise ValueError(f"堵转保护电流阈值应在100-3000mA范围内，当前值: {params.stall_protection_current}")
            
            if not (100 <= params.stall_protection_time <= 5000):
                raise ValueError(f"堵转保护时间应在100-5000ms范围内，当前值: {params.stall_protection_time}")
        
        # 位置到达窗口验证
        if not (1 <= params.position_arrival_window <= 100):
            raise ValueError(f"位置到达窗口应在1-100范围内(0.1-10.0度)，当前值: {params.position_arrival_window}")
        
        self.logger.info("驱动参数验证通过")
    
    def get_baudrate_options(self) -> dict:
        """
        获取波特率选项说明
        
        Returns:
            dict: 波特率选项映射
        """
        return {
            'uart': {
                0: '4800',
                1: '9600', 
                2: '19200',
                3: '38400',
                4: '57600',
                5: '115200',
                6: '230400',
                7: '460800'
            },
            'can': {
                0: '125K',
                1: '250K',
                2: '500K', 
                3: '1M',
                4: '2M',
                5: '4M',
                6: '5M',
                7: '8M'
            }
        }
    
    def modify_drive_parameters_with_validation(self, params, save_to_chip: bool = True):
        """
        修改驱动参数（带参数验证）
        
        Args:
            params: 驱动参数结构
            save_to_chip: 是否保存到芯片
            
        Returns:
            CommandResponse: 命令响应
        """
        # 先验证参数
        self.validate_drive_parameters(params)
        
        # 执行修改
        return self.modify_drive_parameters(params, save_to_chip)
    
    def modify_control_mode(self, control_mode: int, save_to_chip: bool = True) -> None:
        """
        修改控制模式
        
        Args:
            control_mode: 控制模式 (0=开环, 1=闭环FOC)
            save_to_chip: 是否保存到芯片
        """
        # 读取当前参数
        try:
            current_params = self.controller.read_parameters.get_drive_parameters()
        except Exception as e:
            self.logger.warning(f"读取当前参数失败，使用默认参数: {e}")
            current_params = self.create_default_drive_parameters()
        
        # 修改控制模式
        current_params.control_mode = control_mode
        
        # 应用修改
        self.modify_drive_parameters(current_params, save_to_chip)
        self.logger.info(f"控制模式已修改为: {control_mode}")
    
    def modify_current_limits(self, open_loop_current: int = None, 
                             closed_loop_max_current: int = None, 
                             save_to_chip: bool = True) -> None:
        """
        修改电流限制
        
        Args:
            open_loop_current: 开环模式工作电流 (mA)
            closed_loop_max_current: 闭环模式最大电流 (mA)
            save_to_chip: 是否保存到芯片
        """
        # 读取当前参数
        try:
            current_params = self.controller.read_parameters.get_drive_parameters()
        except Exception as e:
            self.logger.warning(f"读取当前参数失败，使用默认参数: {e}")
            current_params = self.create_default_drive_parameters()
        
        # 修改电流限制
        if open_loop_current is not None:
            current_params.open_loop_current = open_loop_current
            self.logger.info(f"开环模式工作电流设置为: {open_loop_current}mA")
        
        if closed_loop_max_current is not None:
            current_params.closed_loop_max_current = closed_loop_max_current
            self.logger.info(f"闭环模式最大电流设置为: {closed_loop_max_current}mA")
        
        # 应用修改
        self.modify_drive_parameters(current_params, save_to_chip)
    
    def modify_speed_limit(self, max_speed_limit: int, save_to_chip: bool = True) -> None:
        """
        修改速度限制
        
        Args:
            max_speed_limit: 最大速度限制 (RPM)
            save_to_chip: 是否保存到芯片
        """
        # 读取当前参数
        try:
            current_params = self.controller.read_parameters.get_drive_parameters()
        except Exception as e:
            self.logger.warning(f"读取当前参数失败，使用默认参数: {e}")
            current_params = self.create_default_drive_parameters()
        
        # 修改速度限制
        current_params.max_speed_limit = max_speed_limit
        
        # 应用修改
        self.modify_drive_parameters(current_params, save_to_chip)
        self.logger.info(f"最大速度限制已设置为: {max_speed_limit}RPM")
    
    def modify_stall_protection(self, enabled: bool, speed_threshold: int = None,
                               current_threshold: int = None, time_threshold: int = None,
                               save_to_chip: bool = True) -> None:
        """
        修改堵转保护参数
        
        Args:
            enabled: 是否启用堵转保护
            speed_threshold: 堵转保护转速阈值 (RPM)
            current_threshold: 堵转保护电流阈值 (mA)
            time_threshold: 堵转保护检测时间阈值 (ms)
            save_to_chip: 是否保存到芯片
        """
        # 读取当前参数
        try:
            current_params = self.controller.read_parameters.get_drive_parameters()
        except Exception as e:
            self.logger.warning(f"读取当前参数失败，使用默认参数: {e}")
            current_params = self.create_default_drive_parameters()
        
        # 修改堵转保护参数
        current_params.stall_protection_enabled = enabled
        
        if speed_threshold is not None:
            current_params.stall_protection_speed = speed_threshold
        
        if current_threshold is not None:
            current_params.stall_protection_current = current_threshold
        
        if time_threshold is not None:
            current_params.stall_protection_time = time_threshold
        
        # 应用修改
        self.modify_drive_parameters(current_params, save_to_chip)
        self.logger.info(f"堵转保护已{'启用' if enabled else '禁用'}")
    
    def modify_communication_settings(self, uart_baudrate: int = None, 
                                     can_baudrate: int = None,
                                     save_to_chip: bool = True) -> None:
        """
        修改通讯设置
        
        Args:
            uart_baudrate: 串口波特率选项 (0-7对应不同波特率)
            can_baudrate: CAN通讯速率选项 (0-7对应不同速率)
            save_to_chip: 是否保存到芯片
        """
        # 读取当前参数
        try:
            current_params = self.controller.read_parameters.get_drive_parameters()
        except Exception as e:
            self.logger.warning(f"读取当前参数失败，使用默认参数: {e}")
            current_params = self.create_default_drive_parameters()
        
        # 修改通讯设置
        if uart_baudrate is not None:
            current_params.uart_baudrate = uart_baudrate
            self.logger.info(f"串口波特率选项设置为: {uart_baudrate}")
        
        if can_baudrate is not None:
            current_params.can_baudrate = can_baudrate
            self.logger.info(f"CAN通讯速率选项设置为: {can_baudrate}")
        
        # 应用修改
        self.modify_drive_parameters(current_params, save_to_chip) 