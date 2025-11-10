# ZDT闭环驱动板Python SDK

这是一个用于控制ZDT闭环驱动板的Python SDK，支持通过SLCAN接口进行CAN通信。

注意：获取全部状态的接口可能存在问题

## 特性

- 🚀 **简单易用的API** - 提供直观的高级接口
- 🔧 **完整的功能支持** - 支持所有ZDT驱动板功能
- 🔄 **多种控制模式** - 力矩模式、速度模式、位置模式
- 📡 **SLCAN通信** - 通过串口发送CAN帧，支持CANable等设备
- 🎯 **精确控制** - 支持梯形曲线运动规划
- 🏠 **回零功能** - 完整的原点回零支持
- 🔗 **多机同步控制** - 支持真正的多电机同步运动，基于官方上位机同步机制
- 🛡️ **错误处理** - 完善的异常处理机制
- 📊 **实时监控** - 实时状态和参数监控
- 🧪 **交互式测试** - 内置多种测试工具

## 硬件要求

- 闭环驱动板
- CANable、CANtact或其他SLCAN兼容的USB转CAN设备
- CAN总线速率设置为500K

## 安装

### 1. 安装依赖

```bash
pip install pyserial
```

### 2. 下载SDK
将`Control_Core`文件夹复制到您的项目目录中。

## 快速开始

### 基础控制示例

```python
from Control_Core import ZDTMotorController

# 创建电机控制器 (默认COM18, 500000波特率, 电机ID=1)
with ZDTMotorController() as motor:
    # 使能电机
    motor.enable()
    
    # 位置控制
    motor.move_to_position(90.0, speed=200)
    motor.wait_for_position()
    
    # 速度控制
    motor.set_speed(100)
    
    # 获取状态
    position = motor.get_position()
    speed = motor.get_speed()
    print(f"位置: {position:.2f}度, 速度: {speed:.2f}RPM")
```

### 多机同步控制示例

```python
from Control_Core import ZDTMotorController

# 广播控制器（统一触发或统一控制）
broadcast = ZDTMotorController(motor_id=0, port='COM18')

# 多电机
a = ZDTMotorController(motor_id=1, port='COM18')
b = ZDTMotorController(motor_id=2, port='COM18')

broadcast.connect()
a.can_interface = broadcast.can_interface
b.can_interface = broadcast.can_interface

a.control_actions.enable()
b.control_actions.enable()

# 使用同步标志：先缓存不执行
a.control_actions.move_to_position(position=-3600, speed=1000, multi_sync=True)
b.control_actions.move_to_position_trapezoid(position=7200, max_speed=1000, acceleration=2000, deceleration=2000, multi_sync=True)

# 统一触发同时开始
broadcast.control_actions.sync_motion()
```

## 测试工具

### 1. 单电机交互式测试工具

```bash
python test_interactive.py
```

功能包括：
- 📡 连接管理（自动或手动配置）
- 🔋 基础控制（使能、失能、停止）
- 📊 状态读取（位置、速度、温度等）
- 🏃 运动控制（速度、位置、力矩模式）
- 🏠 回零功能（触发回零、参数设置）
- 🔧 工具功能（位置清零、解除堵转保护）
- 📝 日志级别设置

### 2. 多机同步控制测试工具

```bash
python test_multi_motor_sync.py
```

**核心特性**：
- 🔄 **真正的多机同步控制** - 基于官方上位机同步机制
- 📡 **CAN总线共享** - 多个电机共享一个CAN接口
- 🎯 **同步运动配置** - 支持直通位置、梯形位置、速度模式同步
- 📊 **实时监控** - 串行状态读取，避免通信冲突
- 🔍 **诊断工具** - 基础CAN诊断、分步连接测试
- 🚀 **快速测试** - 一键执行示例同步运动

**主要功能**：
- 连接管理（配置电机、CAN诊断、分步测试）
- 状态监控（显示状态、实时监控、简化检查）
- 基础控制（单电机控制、批量使能/失能）
- **多机同步控制**（配置同步运动、执行同步运动）
- 广播控制（广播命令测试）
- 回零功能（多电机回零）
- 工具功能（日志设置、报告导出）

## API文档

### 主要类

#### ZDTMotorController
主要的电机控制器类，提供所有控制功能。

```python
motor = ZDTMotorController(
    motor_id=1,                    # 电机ID (0=广播, 1-255=单机)
    interface_type="slcan",        # 接口类型（默认slcan）
    port="COM18",                  # 串口号
    baudrate=500000                # 串口波特率
)
```

### 基础控制方法

连接/控制器

| 方法 | 说明 |
|------|------|
| `connect(motor_id=None)` | 连接 CAN 接口并绑定电机 ID（未在构造中提供时需在此指定） |
| `disconnect()` | 断开连接并释放共享/私有接口资源 |
| `set_motor_id(motor_id)` | 动态切换当前控制的电机地址（0=广播，1-255=单机） |
| `send_broadcast_command(command_data)` | 以广播地址(0)下发命令，不等待响应 |
| `multi_motor_command(per_motor_commands, expected_ack_motor_id=1, timeout=1.0, wait_ack=True, mode=None)` | Y 板专用 Y42 聚合多机命令；单次调用仅允许控制类(F5/F6/FB/FD)或读取类(0x36)之一，禁止混合 |
| `control_actions.sync_motion()` | 触发多机同步运动（X 板用于带同步标志命令的统一启动） |

基础控制（ControlActionsModule / TriggerActionsModule）

| 方法 | 说明 |
|------|------|
| `enable(multi_sync=False)` | 使能电机（可带多机同步标志） |
| `disable(multi_sync=False)` | 失能电机（可带多机同步标志） |
| `stop(multi_sync=False)` | 立即停止（可带多机同步标志） |
| `emergency_stop()` | 紧急停止（先停再失能，确保安全） |
| `clear_position()` | 将当前机械角度清零为 0° |
| `release_stall_protection()` | 解除堵转保护状态 |
| `trigger_encoder_calibration()` | 触发编码器校准流程 |

运动控制（ControlActionsModule）

| 方法 | 说明 |
|------|------|
| `set_torque(current, current_slope=DEFAULT_CURRENT_SLOPE, multi_sync=False)` | 力矩模式，单位 mA，支持正负方向；`current_slope` 为电流斜率 |
| `set_speed(speed, acceleration=DEFAULT_ACCELERATION, multi_sync=False)` | 速度模式，速度单位 RPM（可正负），加速度单位 RPM/s |
| `move_to_position(position, speed=DEFAULT_SPEED, is_absolute=False, multi_sync=False, timeout=1.0)` | 直通限速位置模式，位置单位度；`is_absolute=True` 为绝对位置，默认相对 |
| `move_to_position_trapezoid(position, max_speed=DEFAULT_SPEED, acceleration=DEFAULT_ACCELERATION, deceleration=DEFAULT_ACCELERATION, is_absolute=False, multi_sync=False, timeout=1.0)` | 梯形曲线位置模式，含独立加减速度限制 |

回零（HomingCommandsModule / ControlActionsModule）

| 方法 | 说明 |
|------|------|
| `start_homing(homing_mode=None, multi_sync=False)` | 开始回零；不指定则就近回零（见 `Parameters.HOMING_MODE_*`） |
| `force_stop_homing()` / `stop_homing()` | 强制停止回零流程 |
| `set_zero_position(save_to_chip=True)` | 将当前位置设为零点，可选择保存至芯片 |
| `modify_homing_parameters(...)` | 修改回零参数（模式、方向、速度、超时、碰撞检测、是否自启等） |
| `get_homing_status() -> HomingStatus` | 获取回零状态标志（编码器就绪、是否在回零、是否失败等） |
| `wait_for_homing_complete(timeout=30.0, check_interval=0.5) -> bool` | 阻塞等待回零完成/失败 |
| `is_homing_in_progress() -> bool` / `is_homing_failed() -> bool` / `is_encoder_ready() -> bool` | 回零便利查询 |

读取与监控（ReadParametersModule）

| 方法 | 说明 |
|------|------|
| `get_motor_status() -> MotorStatus` | 基本状态（使能/到位/堵转/堵转保护） |
| `get_position() -> float` | 实时位置（度） |
| `get_speed() -> float` | 实时转速（RPM） |
| `get_position_error() -> float` | 位置误差（度） |
| `get_temperature() -> float` | 驱动器温度（°C） |
| `get_bus_voltage() -> float` | 总线电压（V） |
| `get_current() -> float` | 相电流（A） |
| `get_bus_current() -> float` | 总线平均电流（A） |
| `get_version() -> Dict` | 固件/硬件版本（解析成人类可读） |
| `get_resistance_inductance() -> Dict` | 相电阻/相电感（含原始单位与换算） |
| `get_target_position() -> float` | 目标位置（度） |
| `get_realtime_target_position() -> float` | 实时设定目标位置（度） |
| `get_encoder_raw() -> float` | 编码器原始度数（0-16383→0-360°） |
| `get_encoder_calibrated() -> float` | 线性化后编码器度数（0-65535→0-360°） |
| `get_pulse_count() -> int` | 实时脉冲数 |
| `get_input_pulse() -> int` | 输入脉冲数 |
| `get_status_info() -> Dict` | 汇总常用状态信息（容错聚合） |
| `get_drive_parameters() -> DriveParameters` | 驱动配置全集（新增） |
| `get_system_status() -> SystemStatus` | 系统状态全集（含标志位展开，新增） |

参数修改（ModifyParametersModule）

| 方法 | 说明 |
|------|------|
| `modify_drive_parameters(params, save_to_chip=True)` / `set_drive_parameters(params, save_to_chip=True)` | 应用驱动参数（可选择保存至芯片） |
| `modify_drive_parameters_with_validation(params, save_to_chip=True)` | 带参数校验的驱动参数应用 |
| `create_default_drive_parameters()` / `create_open_loop_drive_parameters()` / `create_high_precision_drive_parameters()` | 提供常用预设，返回 `DriveParameters` |
| `modify_control_mode(control_mode, save_to_chip=True)` | 修改控制模式（0=开环，1=闭环FOC） |
| `modify_current_limits(open_loop_current=None, closed_loop_max_current=None, save_to_chip=True)` | 修改开环/闭环电流限制（mA） |
| `modify_speed_limit(max_speed_limit, save_to_chip=True)` | 修改最大转速限制（RPM） |
| `modify_stall_protection(enabled, speed_threshold=None, current_threshold=None, time_threshold=None, save_to_chip=True)` | 修改堵转保护启用与阈值 |
| `modify_communication_settings(uart_baudrate=None, can_baudrate=None, save_to_chip=True)` | 修改 UART/CAN 速率选项 |
| `validate_drive_parameters(params)` | 对 `DriveParameters` 进行范围/一致性检查 |
| `get_baudrate_options() -> dict` | UART/CAN 速率选项映射表 |
| `set_pid_parameters(...)` | 设置 PID（占位；当前以日志提示为主） |
| `set_baudrate(baudrate)` / `set_acceleration_limits(max_acceleration)` / `set_speed_limits(max_speed)` / `set_current_limits(max_current)` / `set_homing_parameters(...)` / `set_encoder_parameters(...)` | 兼容占位接口（日志提示为主，协议按后续实现） |

> 板型提示：X 板不支持 `multi_motor_command`，应使用各命令 `multi_sync=True` 并最终以 `sync_motion()` 同步启动；Y 板支持 `multi_motor_command` 聚合，但控制类与读取类命令不得混在同一调用中。

### 状态查询方法

| 方法 | 说明 |
|------|------|
| `get_position()` | 获取当前位置(度) |
| `get_speed()` | 获取当前转速(RPM) |
| `get_temperature()` | 获取驱动器温度(°C) |
| `get_bus_voltage()` | 获取总线电压(V) |
| `get_current()` | 获取相电流(A) |
| `get_motor_status()` | 获取电机状态 |
| `get_status_info()` | 获取完整状态信息 |
| `get_drive_parameters()` | 获取驱动参数（新增） |
| `get_system_status()` | 获取完整系统状态（新增） |

### 回零控制方法

| 方法 | 说明 |
|------|------|
| `set_zero_position()` | 设置当前位置为零点 |
| `start_homing()` | 开始回零 |
| `stop_homing()` | 停止回零 |
| `wait_for_homing_complete()` | 等待回零完成 |

#### Y 板新增回零模式与参数

- 新增模式（API 传参）：
  - `homing_mode=4` 回到绝对位置坐标零点
  - `homing_mode=5` 回到上次掉电位置角度
- 同步控制（API 传参）：
  - `multi_sync=False` 立即执行该命令
  - `multi_sync=True` 先缓存，待调用 `control_actions.sync_motion()` 统一触发后同时开始
- 注意：使用 `start_homing(homing_mode: int, multi_sync: bool)` 即可，接线/参数需符合各回零模式要求，请按“原点回零”章节操作。

### 触发动作（新增）

```python
# 紧急停止（立即停止电机并进入安全状态）
motor.trigger_actions.emergency_stop()

# 编码器校准
after_ok = motor.trigger_actions.trigger_encoder_calibration()

# 清零位置
motor.trigger_actions.clear_position()

# 解除堵转保护
motor.trigger_actions.release_stall_protection()

# 恢复出厂设置（谨慎执行）
motor.trigger_actions.factory_reset()
```

### 便捷方法

| 方法 | 说明 |
|------|------|
| `is_enabled()` | 检查电机是否使能 |
| `is_in_position()` | 检查电机是否到位 |
| `is_stalled()` | 检查电机是否堵转 |
| `wait_for_position()` | 等待电机到位 |

## 多机同步控制详解

### 同步机制与多机命令（API 视角）

- 广播（X/Y）：用 `motor_id=0` 控制器直接调用控制方法，所有电机同时执行相同命令。
- 同步标志（X/Y）：各电机调用控制方法时设置 `multi_sync=True` 先缓存，最后调用 `control_actions.sync_motion()` 统一触发。
- 多机聚合（Y 板）：用 `multi_motor_command(..., mode='control'|'read')` 聚合不同电机的指令一次下发；控制类与读取类需分两次调用。

### 同步控制步骤

```python
# 1. 创建控制器并连接
broadcast = ZDTMotorController(motor_id=0, port='COM18')
motor1 = ZDTMotorController(motor_id=1, port='COM18')
motor2 = ZDTMotorController(motor_id=2, port='COM18')

broadcast.connect()
motor1.can_interface = broadcast.can_interface
motor2.can_interface = broadcast.can_interface

# 2. 使能电机
motor1.control_actions.enable()
motor2.control_actions.enable()

# 3. 发送带同步标志的命令
motor1.control_actions.move_to_position(position=-3600, speed=1000, sync_flag=0x01)
motor2.control_actions.move_to_position_trapezoid(
    position=7200, max_speed=1000, acceleration=2000, 
    deceleration=2000, sync_flag=0x01
)

# 4. 触发同步运动
broadcast.can_interface.send_command_and_receive_response(
    motor_id=0, command=[0x00, 0xFF, 0x66, 0x6B]
)
```

### 支持的同步运动类型

- **直通位置模式同步**：所有电机同时开始位置运动
- **梯形位置模式同步**：所有电机同时开始梯形曲线运动
- **速度模式同步**：所有电机同时开始速度运动
- **混合模式同步**：不同电机可以使用不同的运动模式

## 通信协议

// 本文面向应用层开发者，底层协议细节省略。若需协议/字节级细节，请参考底层README。

### 支持的设备
- CANable (推荐)
- CANtact
- 其他支持SLCAN协议的USB转CAN设备

## 硬件配置

### ZDT驱动板设置
1. **P_Serial设置**: 必须设置为`CAN1_MAP`
2. **CAN速率**: 设置为500K
3. **电机ID**: 设置为1-255之间的唯一值（多机时每个电机ID必须不同）
4. **接线**: 确保CAN_H和CAN_L正确连接

### 多机连接示例
```
电脑(COM18) ←→ CANable ←→ CAN总线 ←→ ZDT驱动板1(ID=1)
                              ├→ ZDT驱动板2(ID=2)
                              └→ ZDT驱动板N(ID=N)
```

## 错误处理

SDK提供了完善的异常处理机制：

```python
from Control_Core import (
    MotorNotEnabledException, 
    StallProtectionException,
    TimeoutException,
    CANInterfaceException
)

try:
    motor.move_to_position(180)
except MotorNotEnabledException:
    print("电机未使能，请先使能电机")
    motor.enable()
except StallProtectionException:
    print("电机堵转，解除保护")
    motor.release_stall_protection()
except TimeoutException:
    print("通信超时")
except CANInterfaceException as e:
    print(f"CAN接口错误: {e}")
```

## 常见问题

### Q: 连接失败怎么办？
A: 检查以下项目：
1. 串口号是否正确（通过设备管理器确认）
2. 是否有其他程序占用串口（如CANgaroo）
3. ZDT驱动板是否正确上电
4. P_Serial是否设置为CAN1_MAP

### Q: 电机不响应怎么办？
A: 检查以下项目：
1. 电机ID是否正确
2. CAN总线连接是否正常
3. 驱动板CAN速率是否为500K
4. 是否先使能了电机

### Q: 多机同步不工作怎么办？
A: 检查以下项目：
1. 每个电机的ID是否唯一且正确
2. 是否正确发送了带同步标志（0x01）的命令
3. 是否发送了广播同步命令（00 FF 66 6B）
4. 所有电机是否都已使能
5. CAN总线连接是否稳定

### Q: 如何调试通信问题？
A: 
1. 使用多机测试工具的"基础CAN诊断"功能
2. 使用"分步连接测试"逐个检查电机
3. 设置DEBUG日志级别：
```python
from Control_Core import setup_logging
import logging

setup_logging(logging.DEBUG)
```

### Q: 状态读取显示不了怎么办？
A: 
1. 使用"简化状态检查"功能，只读取最基本信息
2. 检查是否有多个程序同时访问CAN总线
3. 确认电机通信正常（使用单电机测试）

## 示例代码

### 完整的多机同步控制示例

```python
from Control_Core import ZDTMotorController, setup_logging
import logging
import time

# 启用详细日志
setup_logging(logging.INFO)

def multi_motor_sync_demo():
    """多机同步控制演示"""
    
    # 创建控制器
    broadcast = ZDTMotorController(motor_id=0, port='COM18')
    motor1 = ZDTMotorController(motor_id=1, port='COM18')
    motor2 = ZDTMotorController(motor_id=2, port='COM18')
    
    try:
        # 连接CAN总线
        print("连接CAN总线...")
        broadcast.connect()
        
        # 共享CAN接口
        motor1.can_interface = broadcast.can_interface
        motor2.can_interface = broadcast.can_interface
        
        # 使能电机
        print("使能电机...")
        motor1.control_actions.enable()
        motor2.control_actions.enable()
        time.sleep(1)
        
        # 读取初始位置
        pos1 = motor1.read_parameters.get_position()
        pos2 = motor2.read_parameters.get_position()
        print(f"初始位置 - 电机1: {pos1:.2f}°, 电机2: {pos2:.2f}°")
        
        # 配置同步运动
        print("配置同步运动...")
        print("  电机1: 直通位置模式 -3600°")
        print("  电机2: 梯形位置模式 7200°")
        
        # 发送带同步标志的命令
        motor1.control_actions.move_to_position(
            position=-3600, speed=1000, sync_flag=0x01
        )
        motor2.control_actions.move_to_position_trapezoid(
            position=7200, max_speed=1000, acceleration=2000, 
            deceleration=2000, sync_flag=0x01
        )
        
        # 触发同步运动
        print("触发同步运动...")
        broadcast.can_interface.send_command_and_receive_response(
            motor_id=0, command=[0x00, 0xFF, 0x66, 0x6B]
        )
        
        # 监控运动过程
        print("监控运动过程...")
        start_time = time.time()
        while time.time() - start_time < 30:  # 最多监控30秒
            try:
                # 读取状态
                status1 = motor1.read_parameters.get_motor_status()
                status2 = motor2.read_parameters.get_motor_status()
                pos1 = motor1.read_parameters.get_position()
                pos2 = motor2.read_parameters.get_position()
                speed1 = motor1.read_parameters.get_speed()
                speed2 = motor2.read_parameters.get_speed()
                
                # 显示状态
                elapsed = time.time() - start_time
                print(f"[{elapsed:.1f}s] 电机1: {pos1:.1f}° {speed1:.0f}RPM {'到位' if status1.in_position else '运动中'}")
                print(f"[{elapsed:.1f}s] 电机2: {pos2:.1f}° {speed2:.0f}RPM {'到位' if status2.in_position else '运动中'}")
                
                # 检查是否都到位
                if status1.in_position and status2.in_position:
                    print("✅ 所有电机已到位，同步运动完成!")
                    break
                    
                time.sleep(2)  # 2秒更新一次
                
            except Exception as e:
                print(f"状态读取错误: {e}")
                time.sleep(1)
        
        # 显示最终位置
        final_pos1 = motor1.read_parameters.get_position()
        final_pos2 = motor2.read_parameters.get_position()
        print(f"最终位置 - 电机1: {final_pos1:.2f}°, 电机2: {final_pos2:.2f}°")
        
    except Exception as e:
        print(f"错误: {e}")
    finally:
        # 断开连接
        broadcast.disconnect()
        print("✓ 已断开连接")

if __name__ == "__main__":
    multi_motor_sync_demo()
```

## 版本历史

- **v1.0.0** - 初始版本，支持SLCAN通信协议
- **v1.1.0** - 添加多机同步控制功能
  - 真正的多机同步控制，基于官方上位机同步机制
  - 多机同步测试工具 (`test_multi_motor_sync.py`)
  - 串行状态读取，避免CAN通信冲突
  - CAN总线诊断和分步连接测试功能
  - 完善的错误处理和日志系统
- **v1.2.0（新增）**
  - 模块化架构完善（控制/读取/修改/回零/触发）
  - 新增驱动参数读写（`DriveParameters`）
  - 新增系统状态读取（`SystemStatus`）
  - 新增触发动作（`emergency_stop` 等）

## 许可证

本项目采用MIT许可证。

## 技术支持

如有问题或建议，请联系技术支持。 


 