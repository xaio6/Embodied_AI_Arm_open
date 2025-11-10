# -*- coding: utf-8 -*-
"""
ZDT闭环驱动板常量定义
"""

# 通信相关常量
DEFAULT_CAN_BAUDRATE = 500000  # 默认CAN波特率 500K
CHECKSUM_BYTE = 0x6B          # 固定校验字节
DEFAULT_TIMEOUT = 1.0         # 默认超时时间(秒)

# 命令功能码
class FunctionCodes:
    """功能码定义"""
    # 控制动作命令
    MOTOR_ENABLE = 0xF3         # 电机使能控制
    TORQUE_MODE = 0xF5          # 力矩模式控制
    SPEED_MODE = 0xF6           # 速度模式控制
    POSITION_MODE_DIRECT = 0xFB # 直通限速位置模式控制
    POSITION_MODE_TRAPEZOID = 0xFD # 梯形曲线位置模式控制
    IMMEDIATE_STOP = 0xFE       # 立即停止
    MULTI_SYNC_MOTION = 0xFF    # 多机同步运动
    Y42_MULTI_MOTOR = 0xAA      # Y42 多电机命令（Y板）
    
    # 原点回零命令
    SET_ZERO_POSITION = 0x93    # 设置单圈回零的零点位置
    TRIGGER_HOMING = 0x9A       # 触发回零
    FORCE_STOP_HOMING = 0x9C    # 强制中断并退出回零操作
    READ_HOMING_PARAMS = 0x22   # 读取原点回零参数
    MODIFY_HOMING_PARAMS = 0x4C # 修改原点回零参数
    READ_HOMING_STATUS = 0x3B   # 读取回零状态标志位
    
    # 触发动作命令
    TRIGGER_ENCODER_CALIBRATION = 0x06  # 触发编码器校准
    CLEAR_POSITION = 0x0A       # 将当前的位置角度清零
    RELEASE_STALL_PROTECTION = 0x0E     # 解除堵转保护
    FACTORY_RESET = 0x0F        # 恢复出厂设置
    
    # 读取参数命令
    READ_VERSION = 0x1F         # 读取固件版本和硬件版本
    READ_RESISTANCE_INDUCTANCE = 0x20   # 读取相电阻和相电感
    READ_PID_PARAMS = 0x21      # 读取速度环和位置环PID参数
    READ_BUS_VOLTAGE = 0x24     # 读取总线电压
    READ_BUS_CURRENT = 0x26     # 读取总线平均电流
    READ_PHASE_CURRENT = 0x27   # 读取相电流
    READ_ENCODER_RAW = 0x29     # 读取编码器原始值
    READ_PULSE_COUNT = 0x30     # 读取实时脉冲数
    READ_ENCODER_CALIBRATED = 0x31      # 读取经过线性化校准后的编码器值
    READ_INPUT_PULSE = 0x32     # 读取输入脉冲数
    READ_TARGET_POSITION = 0x33 # 读取电机目标位置
    READ_REALTIME_TARGET_POSITION = 0x34 # 读取电机实时设定的目标位置
    READ_REALTIME_SPEED = 0x35  # 读取电机实时转速
    READ_REALTIME_POSITION = 0x36       # 读取电机实时位置
    READ_POSITION_ERROR = 0x37  # 读取电机位置误差
    READ_TEMPERATURE = 0x39     # 读取驱动器实时温度
    READ_MOTOR_STATUS = 0x3A    # 读取电机状态标志位
    
    # 新增的综合参数命令
    READ_DRIVE_PARAMETERS = 0x42    # 读取驱动参数
    READ_SYSTEM_STATUS = 0x43       # 读取系统状态参数
    MODIFY_DRIVE_PARAMETERS = 0x48  # 修改驱动参数
    
    # 修改参数命令
    MODIFY_SUBDIVISION = 0x84   # 修改细分
    MODIFY_ID_ADDRESS = 0xAE    # 修改ID地址
    MODIFY_PID_PARAMS = 0x4A    # 修改速度环和位置环PID参数

# 辅助码定义
class AuxCodes:
    """辅助码定义"""
    MOTOR_ENABLE_AUX = 0xAB
    SET_ZERO_POSITION_AUX = 0x88
    FORCE_STOP_HOMING_AUX = 0x48
    IMMEDIATE_STOP_AUX = 0x98
    MULTI_SYNC_MOTION_AUX = 0x66
    TRIGGER_ENCODER_CALIBRATION_AUX = 0x45
    CLEAR_POSITION_AUX = 0x6D
    RELEASE_STALL_PROTECTION_AUX = 0x52
    FACTORY_RESET_AUX = 0x5F
    MODIFY_HOMING_PARAMS_AUX = 0xAE
    MODIFY_SUBDIVISION_AUX = 0x8A
    MODIFY_ID_ADDRESS_AUX = 0x4B
    MODIFY_PID_PARAMS_AUX = 0xC3
    # 新增辅助码
    READ_DRIVE_PARAMETERS_AUX = 0x6C    # 读取驱动参数辅助码
    READ_SYSTEM_STATUS_AUX = 0x7A       # 读取系统状态参数辅助码
    MODIFY_DRIVE_PARAMETERS_AUX = 0xD1  # 修改驱动参数辅助码

# 状态码定义
class StatusCodes:
    """命令返回状态码"""
    DATA_RESPONSE = 0x00        # 数据响应（读取命令的正常响应）
    STATUS_RESPONSE = 0x01      # 状态响应（状态查询的正常响应）
    SUCCESS = 0x02              # 命令执行成功
    MOTOR_ENABLED = 0x03        # 电机已使能状态响应
    
    # 新增的状态码
    UNKNOWN_0x0B = 0x0B         # 未知状态码0x0B
    UNKNOWN_0x2C = 0x2C         # 未知状态码0x2C
    UNKNOWN_0x2E = 0x2E         # 未知状态码0x2E
    UNKNOWN_0x34 = 0x34         # 未知状态码0x34
    
    CONDITION_NOT_MET = 0xE2    # 条件不满足
    COMMAND_ERROR = 0xEE        # 错误命令

# 电机状态标志位
class MotorStatusFlags:
    """电机状态标志位掩码"""
    ENABLED = 0x01              # 电机使能状态
    IN_POSITION = 0x02          # 电机到位标志
    STALLED = 0x04              # 电机堵转标志
    STALL_PROTECTION = 0x08     # 电机堵转保护标志

# 回零状态标志位
class HomingStatusFlags:
    """回零状态标志位掩码"""
    ENCODER_READY = 0x01        # 编码器就绪状态
    CALIBRATION_TABLE_READY = 0x02      # 校准表就绪状态
    HOMING_IN_PROGRESS = 0x04   # 正在回零标志
    HOMING_FAILED = 0x08        # 回零失败标志
    POSITION_PRECISION_HIGH = 0x80      # 通讯控制位置角度精度选项

# 参数常量
class Parameters:
    """参数相关常量"""
    # 方向
    DIRECTION_POSITIVE = 0x00   # 正方向
    DIRECTION_NEGATIVE = 0x01   # 负方向
    
    # 位置模式
    POSITION_RELATIVE = 0x00    # 相对位置
    POSITION_ABSOLUTE = 0x01    # 绝对位置
    
    # 多机同步
    SYNC_DISABLED = 0x00        # 不启用多机同步
    SYNC_ENABLED = 0x01         # 启用多机同步
    
    # 存储标志
    NO_SAVE = 0x00              # 不保存参数
    SAVE = 0x01                 # 保存参数到芯片
    
    # 回零模式（与新协议一致）
    HOMING_MODE_NEAREST = 0x00              # 单圈就近回零
    HOMING_MODE_DIRECTIONAL = 0x01          # 单圈方向回零（方向由回零参数决定）
    HOMING_MODE_INFINITE_COLLISION = 0x02   # 无限位碰撞回零
    HOMING_MODE_LIMIT_SWITCH = 0x03         # 限位回零
    HOMING_MODE_ABSOLUTE_ZERO = 0x04        # 回到绝对位置坐标零点
    HOMING_MODE_LAST_POWER_DOWN = 0x05      # 回到上次掉电位置角度
    
    # 回零方向
    HOMING_DIR_CW = 0x00        # 顺时针回零
    HOMING_DIR_CCW = 0x01       # 逆时针回零
    
    # 细分设置
    SUBDIVISION_256 = 0x00      # 256细分
    
    # 数据转换倍数
    SPEED_SCALE = 10            # 速度数据放大倍数
    POSITION_SCALE = 10         # 位置数据放大倍数
    POSITION_ERROR_SCALE = 100  # 位置误差数据放大倍数
    ENCODER_RAW_MAX = 16383     # 编码器原始值最大值(0-16383表示0-360°)
    ENCODER_CALIBRATED_MAX = 65535  # 校准后编码器值最大值

# 默认参数值
class DefaultValues:
    """默认参数值"""
    DEFAULT_SPEED = 1000        # 默认速度 (RPM)
    DEFAULT_ACCELERATION = 500  # 默认加速度 (RPM/s)
    DEFAULT_CURRENT = 500       # 默认电流 (mA)
    DEFAULT_CURRENT_SLOPE = 1000 # 默认电流斜率 (mA/s)
    
    # 回零参数默认值
    DEFAULT_HOMING_SPEED = 30           # 默认回零速度 (RPM)
    DEFAULT_HOMING_TIMEOUT = 10000      # 默认回零超时时间 (ms)
    DEFAULT_COLLISION_DETECTION_SPEED = 4000    # 默认碰撞检测转速 (RPM)
    DEFAULT_COLLISION_DETECTION_CURRENT = 800   # 默认碰撞检测电流 (mA)
    DEFAULT_COLLISION_DETECTION_TIME = 60       # 默认碰撞检测时间 (ms) 