# DigitalTwinSDK - 数字孪生与仿真

**对应源码：** `Embodied_SDK/digital_twin.py`

## 概述

`DigitalTwinSDK` 提供基于 MuJoCo 的数字孪生仿真能力，支持在虚拟环境中测试机械臂运动，无需连接真实硬件。

## 前置条件

- 已安装 `mujoco` 包：`pip install mujoco`
- URDF 模型文件存在：`config/urdf/`
- 显卡支持 OpenGL

---

## 模块入口

### 通过顶层 SDK

```python
from Embodied_SDK import HorizonArmSDK

sdk = HorizonArmSDK(motors=motors)
dt = sdk.digital_twin  # 获取 DigitalTwinSDK 实例
```

### 独立使用

```python
from Embodied_SDK.digital_twin import DigitalTwinSDK

dt = DigitalTwinSDK()
```

---

## 核心接口

### 1. 启动/停止仿真

#### `start_simulation() -> bool`

启动 MuJoCo 仿真环境。

**返回值：**
- `True`: 仿真启动成功
- `False`: 启动失败（MuJoCo 未安装或 URDF 文件缺失）

**示例：**
```python
if dt.start_simulation():
    print("✅ 仿真已启动")
else:
    print("❌ 仿真启动失败")
```

#### `stop_simulation()`

停止仿真环境。

```python
dt.stop_simulation()
```

#### `is_running() -> bool`

检查仿真是否正在运行。

```python
if dt.is_running():
    print("仿真正在运行")
```

---

### 2. 仿真运动

仿真 SDK 的运动接口与 `MotionSDK` 一致：

#### `move_joints(joint_angles, duration=None) -> bool`

在仿真中运动到指定关节角度。

**参数：**
- `joint_angles`: 6 个关节角度 `[J1, J2, J3, J4, J5, J6]`（度）
- `duration`: 运动时间（秒）

**示例：**
```python
dt.move_joints([0, 30, -45, 0, 15, 0], duration=2.0)
```

#### `move_cartesian(position, orientation=None, duration=None) -> bool`

在仿真中进行笛卡尔空间运动。

**参数：**
- `position`: 末端位置 `[x, y, z]`（毫米）
- `orientation`: 末端姿态 `[yaw, pitch, roll]`（度）
- `duration`: 运动时间（秒）

**示例：**
```python
dt.move_cartesian([300, 0, 200], orientation=[0, 0, 180])
```

#### `execute_preset_action(name, speed="normal") -> bool`

在仿真中执行预设动作。

**示例：**
```python
dt.execute_preset_action("wave_hand", speed="normal")
dt.execute_preset_action("home_position", speed="fast")
```

---

### 3. 直接设置关节角

#### `set_joint_angles(angles) -> bool`

直接设置关节角度（无运动过程，瞬时切换）。

**用途：**
- 同步真实机械臂状态到仿真
- 生成运动波形演示
- 快速切换姿态

**参数：**
- `angles`: 6 个关节角度（度）

**示例：**
```python
# 瞬间切换到指定姿态
dt.set_joint_angles([0, 90, 0, 0, 0, 0])

# 同步真实机械臂状态
real_angles = [m.read_parameters.get_position() for m in motors.values()]
dt.set_joint_angles(real_angles)
```

---

### 4. 轨迹管理

#### `clear_trajectory() -> bool`

清空轨迹记录。

```python
dt.clear_trajectory()
```

---

### 5. 运动参数设置

#### `set_motion_params(max_speed=200, acceleration=100, deceleration=100)`

设置仿真运动参数。

```python
dt.set_motion_params(max_speed=200, acceleration=100, deceleration=100)
```

---

## 完整示例

### 基础仿真测试

```python
from Embodied_SDK.digital_twin import DigitalTwinSDK
import time

# 1. 创建仿真 SDK
dt = DigitalTwinSDK()

# 2. 启动仿真
if not dt.start_simulation():
    print("仿真启动失败")
    exit(1)

print("✅ 仿真已启动")

# 3. 设置运动参数
dt.set_motion_params(max_speed=200, acceleration=100, deceleration=100)

# 4. 执行运动测试
print("测试关节运动...")
dt.move_joints([0, 30, -45, 0, 15, 0], duration=2.0)
time.sleep(2)

print("测试笛卡尔运动...")
dt.move_cartesian([300, 0, 200], duration=2.0)
time.sleep(2)

print("测试预设动作...")
dt.execute_preset_action("wave_hand")
time.sleep(3)

# 5. 停止仿真
dt.stop_simulation()
print("✅ 仿真已停止")
```

---

### 仿真与真实机械臂同步

```python
from Embodied_SDK import HorizonArmSDK, create_motor_controller
import time

# 1. 连接真实机械臂
motors = {mid: create_motor_controller(motor_id=mid, port="COM14") for mid in range(1, 7)}
for m in motors.values():
    m.connect()

# 2. 初始化 SDK
sdk = HorizonArmSDK(motors=motors)

# 3. 启动仿真
sdk.digital_twin.start_simulation()

# 4. 同步循环
try:
    while True:
        # 读取真实机械臂当前角度
        real_angles = []
        for mid in range(1, 7):
            angle = motors[mid].read_parameters.get_position()
            real_angles.append(angle)
        
        # 同步到仿真
        sdk.digital_twin.set_joint_angles(real_angles)
        
        time.sleep(0.1)  # 10Hz 更新
        
except KeyboardInterrupt:
    print("\n停止同步")
    
# 5. 清理
sdk.digital_twin.stop_simulation()
for m in motors.values():
    m.disconnect()
```

---

### 先在仿真中测试，再在真实机械臂上执行

```python
from Embodied_SDK import HorizonArmSDK

# 1. 在仿真中测试
dt = HorizonArmSDK(motors={}).digital_twin
dt.start_simulation()

print("在仿真中测试运动...")
test_angles = [0, 45, -30, 0, 15, 0]
dt.move_joints(test_angles, duration=2.0)
time.sleep(2)

print("仿真测试成功，准备在真实机械臂上执行...")
dt.stop_simulation()

# 2. 连接真实机械臂并执行相同运动
motors = {mid: create_motor_controller(motor_id=mid, port="COM14") for mid in range(1, 7)}
for m in motors.values():
    m.connect()

sdk = HorizonArmSDK(motors=motors)
sdk.motion.move_joints(test_angles, duration=2.0)

for m in motors.values():
    m.disconnect()
```

---

## 使用场景

1. **算法验证**：
   - 在仿真中验证运动规划算法
   - 测试轨迹是否合理

2. **培训演示**：
   - 不需要真实机械臂也能演示功能
   - 培训新用户时更安全

3. **开发测试**：
   - 快速迭代代码
   - 避免反复连接硬件

4. **数字孪生**：
   - 实时同步真实机械臂状态
   - 可视化监控运动过程

---

## 注意事项

1. **仿真限制**：
   - 仿真运动不会影响真实机械臂
   - 物理参数（摩擦力、惯性等）可能与真实环境有差异

2. **性能要求**：
   - MuJoCo 需要显卡支持 OpenGL
   - 低配置电脑可能运行卡顿

3. **模型文件**：
   - URDF 模型需与真实机械臂参数一致
   - 修改 URDF 后需重启仿真

---

## 相关文档

- [MotionSDK](motion.md) - 运动控制接口（仿真接口与之一致）
- [安全须知](safety.md) - 真实机械臂安全操作指南
- [配置说明](configuration.md) - URDF 模型配置

## 示例脚本

- **`example/mujoco_control.py`**  
  **用途：** MuJoCo 仿真交互式演示。  
  **功能：** 提供菜单选择，支持自动波形演示、预设动作执行和随机姿态生成，展示仿真 SDK 的基本控制能力。
