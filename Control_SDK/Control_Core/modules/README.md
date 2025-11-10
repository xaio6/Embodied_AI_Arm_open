# ZDT电机控制器模块化组件

本目录包含了ZDT电机控制器的模块化组件，每个模块负责特定的功能领域。

## 目录结构

```
Control_Core/
├── modules/
│   ├── control_actions.py      # 控制动作模块
│   ├── homing_commands.py      # 回零命令模块
│   ├── trigger_actions.py      # 触发动作模块
│   ├── read_parameters.py      # 参数读取模块
│   ├── modify_parameters.py    # 参数修改模块
│   └── __init__.py            # 模块初始化
├── motor_controller_modular.py # 模块化控制器主类
├── commands.py                 # 命令构建器和解析器
├── can_interface.py           # CAN接口类
├── constants.py               # 常量定义
├── utils.py                   # 工具函数
└── exceptions.py              # 异常类定义
```

## 功能模块说明

### 1. 控制动作模块 (ControlActionsModule)

提供电机基本控制功能：

```python
# 使能电机
motor.control_actions.enable()

# 速度模式控制
motor.control_actions.set_speed(speed=100.0, acceleration=1000)

# 位置模式控制
motor.control_actions.move_to_position(position=90.0, speed=500.0)

# 梯形曲线位置模式
motor.control_actions.move_to_position_trapezoid(
    position=180.0, max_speed=500.0, acceleration=1000, deceleration=1000
)

# 力矩模式控制
motor.control_actions.set_torque(current=500, current_slope=1000)

# 停止电机
motor.control_actions.stop()
```

### 2. 参数读取模块 (ReadParametersModule)

提供各种参数的读取功能：

```python
# 读取基本状态
status = motor.read_parameters.get_motor_status()
position = motor.read_parameters.get_position()
speed = motor.read_parameters.get_speed()
temperature = motor.read_parameters.get_temperature()

# 读取电气参数
voltage = motor.read_parameters.get_bus_voltage()
current = motor.read_parameters.get_current()

# 读取版本信息
version = motor.read_parameters.get_version()

# 读取PID参数
pid_params = motor.read_parameters.get_pid_parameters()

# **新功能** 读取驱动参数
drive_params = motor.read_parameters.get_drive_parameters()
print(f"控制模式: {drive_params.control_mode}")
print(f"最大电流: {drive_params.closed_loop_max_current}mA")
print(f"最大转速: {drive_params.max_speed_limit}RPM")

# **新功能** 读取系统状态参数
system_status = motor.read_parameters.get_system_status()
print(f"总线电压: {system_status.bus_voltage:.2f}V")
print(f"实时位置: {system_status.realtime_position:.2f}度")
print(f"电机使能: {system_status.motor_enabled}")
```

### 3. 参数修改模块 (ModifyParametersModule)

提供参数修改和设置功能：

```python
# **新功能** 修改控制模式
motor.modify_parameters.modify_control_mode(control_mode=1, save_to_chip=True)

# **新功能** 修改电流限制
motor.modify_parameters.modify_current_limits(
    open_loop_current=1200,
    closed_loop_max_current=2000,
    save_to_chip=True
)

# **新功能** 修改速度限制
motor.modify_parameters.modify_speed_limit(max_speed_limit=3000, save_to_chip=True)

# **新功能** 修改堵转保护设置
motor.modify_parameters.modify_stall_protection(
    enabled=True,
    speed_threshold=8,
    current_threshold=2000,
    time_threshold=2000,
    save_to_chip=True
)

# **新功能** 修改通讯设置
motor.modify_parameters.modify_communication_settings(
    uart_baudrate=5,  # 115200
    can_baudrate=2,   # 500K
    save_to_chip=True
)

# **新功能** 创建并应用自定义驱动参数
from Control_Core import DriveParameters

custom_params = DriveParameters(
    lock_enabled=False,
    control_mode=1,
    pulse_port_function=1,
    serial_port_function=2,
    enable_pin_mode=2,
    motor_direction=0,
    subdivision=16,
    subdivision_interpolation=True,
    auto_screen_off=False,
    lpf_intensity=0,
    open_loop_current=1200,
    closed_loop_max_current=2200,
    max_speed_limit=3000,
    current_loop_bandwidth=1000,
    uart_baudrate=5,
    can_baudrate=7,
    checksum_mode=0,
    response_mode=1,
    position_precision=False,
    stall_protection_enabled=True,
    stall_protection_speed=8,
    stall_protection_current=2000,
    stall_protection_time=2000,
    position_arrival_window=3
)

motor.modify_parameters.modify_drive_parameters(custom_params, save_to_chip=True)
```

### 4. 回零功能模块 (HomingCommandsModule)

提供回零相关功能：

```python
# 触发回零
motor.homing_commands.trigger_homing(homing_mode=0)  # 就近回零

# 读取回零状态
status = motor.homing_commands.get_homing_status()

# 设置零点位置
motor.homing_commands.set_zero_position(save_to_chip=True)

# 修改回零参数
motor.homing_commands.modify_homing_parameters(
    mode=0, direction=0, speed=30, timeout=10000,
    collision_detection_speed=300, collision_detection_current=800,
    collision_detection_time=60, auto_homing_enabled=False,
    save_to_chip=True
)
```

### 5. 触发动作模块 (TriggerActionsModule)

提供各种触发动作：

```python
# 编码器校准
motor.trigger_actions.trigger_encoder_calibration()
    
# 清零位置
    motor.trigger_actions.clear_position()
    
# 解除堵转保护
motor.trigger_actions.release_stall_protection()

# 恢复出厂设置
motor.trigger_actions.factory_reset()
```

## 新增数据结构

### DriveParameters 驱动参数

包含完整的驱动器配置参数：

```python
from Control_Core import DriveParameters

# 参数说明
params = DriveParameters(
    lock_enabled=False,                     # 锁定按键菜单
    control_mode=1,                         # 控制模式 (0=开环, 1=闭环FOC)
    pulse_port_function=1,                  # 脉冲端口复用功能
    serial_port_function=2,                 # 通讯端口复用功能
    enable_pin_mode=2,                      # En引脚有效电平
    motor_direction=0,                      # 电机旋转正方向
    subdivision=16,                         # 细分设置
    subdivision_interpolation=True,         # 细分插补功能
    auto_screen_off=False,                  # 自动熄屏功能
    lpf_intensity=0,                        # 低通滤波器强度
    open_loop_current=1200,                 # 开环模式工作电流(mA)
    closed_loop_max_current=2200,           # 闭环模式最大电流(mA)
    max_speed_limit=3000,                   # 闭环模式最大转速(RPM)
    current_loop_bandwidth=1000,            # 电流环带宽(rad/s)
    uart_baudrate=5,                        # 串口波特率选项
    can_baudrate=7,                         # CAN通讯速率选项
    checksum_mode=0,                        # 通讯校验方式
    response_mode=1,                        # 控制命令应答模式
    position_precision=False,               # 通讯控制输入角度精确度
    stall_protection_enabled=True,          # 堵转保护功能
    stall_protection_speed=8,               # 堵转保护转速阈值(RPM)
    stall_protection_current=2000,          # 堵转保护电流阈值(mA)
    stall_protection_time=2000,             # 堵转保护检测时间阈值(ms)
    position_arrival_window=3               # 位置到达窗口(0.1度单位)
)
```

### SystemStatus 系统状态

包含完整的系统状态信息：

```python
from Control_Core import SystemStatus

# 通过读取获得系统状态
status = motor.read_parameters.get_system_status()

# 访问状态信息
print(f"总线电压: {status.bus_voltage}V")
print(f"总线电流: {status.bus_current}A")
print(f"相电流: {status.phase_current}A")
print(f"编码器原始值: {status.encoder_raw_value}")
print(f"编码器校准值: {status.encoder_calibrated_value}")
print(f"目标位置: {status.target_position}度")
print(f"实时转速: {status.realtime_speed}RPM")
print(f"实时位置: {status.realtime_position}度")
print(f"位置误差: {status.position_error}度")
print(f"温度: {status.temperature}°C")

# 状态标志位
print(f"编码器就绪: {status.encoder_ready}")
print(f"电机使能: {status.motor_enabled}")
print(f"电机到位: {status.motor_in_position}")
print(f"堵转保护触发: {status.stall_protection_triggered}")
```

## 错误处理

所有模块都提供完善的错误处理：

```python
from Control_Core import CommandException

try:
    # 执行操作
    params = motor.read_parameters.get_drive_parameters()
except CommandException as e:
    print(f"命令执行失败: {e}")
except Exception as e:
    print(f"其他错误: {e}")
```

## 最佳实践

1. **参数修改后验证**：修改参数后建议重新读取验证
2. **保存到芯片**：重要参数修改建议保存到芯片
3. **错误处理**：始终使用try-except处理可能的异常
4. **状态检查**：执行关键操作前检查电机状态
5. **资源清理**：使用完毕后正确断开连接

```python
# 完整示例
from Control_Core import ZDTMotorController

motor = ZDTMotorController(motor_id=1, interface_type="slcan", port="COM18", baudrate=500000)

try:
    # 连接电机
    motor.connect()
    
    # 读取当前驱动参数
    current_params = motor.read_parameters.get_drive_parameters()
    print(f"当前控制模式: {current_params.control_mode}")
    
    # 修改参数
    motor.modify_parameters.modify_current_limits(
        closed_loop_max_current=1500, save_to_chip=True
    )
    
    # 验证修改
    updated_params = motor.read_parameters.get_drive_parameters()
    print(f"修改后最大电流: {updated_params.closed_loop_max_current}mA")
    
    # 读取系统状态
    system_status = motor.read_parameters.get_system_status()
    print(f"当前位置: {system_status.realtime_position:.2f}度")
    
finally:
    # 断开连接
    motor.disconnect()
``` 