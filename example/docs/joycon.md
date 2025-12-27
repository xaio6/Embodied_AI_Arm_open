# JoyconSDK - 手柄控制

**对应源码：** `Embodied_SDK/joycon.py`

## 概述

`JoyconSDK` 提供 Nintendo Joy-Con 手柄控制机械臂的能力，支持关节模式和笛卡尔模式切换。

## 模块入口

```python
from Embodied_SDK.joycon import JoyconSDK

joycon = JoyconSDK()
```

---

## 使用流程

### 1. 连接手柄

#### `connect_joycon() -> (bool, bool)`

连接 Joy-Con 手柄。

**返回值：**
- `(left_ok, right_ok)`: 左右手柄连接状态

**示例：**
```python
left_ok, right_ok = joycon.connect_joycon()

if left_ok and right_ok:
    print("✅ 手柄连接成功")
else:
    print("❌ 手柄连接失败")
```

---

### 2. 绑定机械臂

#### `bind_arm(motors, use_motor_config=True, kinematics=None, mujoco_controller=None)`

绑定机械臂电机。

**参数：**
- `motors`: 电机字典 `{motor_id: controller}`
- `use_motor_config`: 是否从配置文件加载参数
- `kinematics`: 运动学对象（可选）
- `mujoco_controller`: MuJoCo 控制器（可选，用于仿真）

**示例：**
```python
from Embodied_SDK import create_motor_controller

motors = {mid: create_motor_controller(motor_id=mid, port="COM14") for mid in range(1, 7)}
for m in motors.values():
    m.connect()

joycon.bind_arm(motors, use_motor_config=True)
```

---

### 3. 启动控制

#### `start_control()`

启动手柄控制循环。

**示例：**
```python
joycon.start_control()
print("手柄控制已启动，按 Joy-Con 按钮控制机械臂")
print("按 Ctrl+C 退出")

try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    joycon.stop_control()
```

---

## 控制方法

### 停止/暂停/恢复

```python
# 停止控制
joycon.stop_control()

# 暂停控制
joycon.pause_control()

# 恢复控制
joycon.resume_control()
```

### 模式切换

#### `toggle_mode()`

在关节模式和笛卡尔模式之间切换。

```python
joycon.toggle_mode()
```

**说明：**
- **关节模式**：直接控制各关节角度
- **笛卡尔模式**：控制末端在空间中的位置和姿态

---

### 紧急停止

#### `emergency_stop()`

触发紧急停止。

```python
joycon.emergency_stop()
```

---

## 状态查询

### 获取控制状态

#### `get_status() -> dict`

获取当前控制状态。

```python
status = joycon.get_status()
print(f"模式: {status['mode']}")
print(f"速度倍率: {status['speed_multiplier']}")
print(f"是否运行: {status['running']}")
```

---

### 获取手柄状态

#### `get_left_joycon_status()` / `get_right_joycon_status()`

获取手柄原始状态（用于监控）。

```python
left_status = joycon.get_left_joycon_status()
right_status = joycon.get_right_joycon_status()

if left_status:
    print(f"左摇杆: {left_status.get('stick_l')}")
if right_status:
    print(f"右摇杆: {right_status.get('stick_r')}")
```

---

## 完整示例

请参考 `example/test_joycon_arm_control.py`，该文件展示了如何构建一个全功能的交互式控制台：

1.  **交互式配置**：启动时询问串口号和电机 ID。
2.  **安全检查**：显示详细的控制键位说明。
3.  **主控制循环**：
    *   实时读取手柄状态
    *   根据模式计算目标位姿
    *   调用 SDK 执行运动
    *   刷新屏幕显示状态

```python
# 代码片段：主控制逻辑示意
def main():
    # ... (连接电机与手柄) ...
    
    joycon.bind_arm(motors, use_motor_config=True)
    joycon.start_control()
    
    try:
        while True:
            # 刷新状态显示
            status = joycon.get_status()
            print_status(status, motors)
            time.sleep(0.1)
    except KeyboardInterrupt:
        joycon.stop_control()
```

---

## 按键映射

### 左 Joy-Con
- **摇杆**：控制运动（根据模式）
- **↑↓←→**：微调运动

### 右 Joy-Con
- **摇杆**：控制运动（根据模式）
- **X 键**：切换关节/笛卡尔模式
- **A 键**：张开夹爪
- **B 键**：闭合夹爪

---

## 注意事项

1. **手柄连接**：
   - 确保 Joy-Con 已通过蓝牙配对
   - Windows 系统需要安装对应驱动

2. **控制模式**：
   - 关节模式更直观，适合新手
   - 笛卡尔模式更灵活，需要熟练使用

3. **速度调节**：
   - 可通过手柄按键调节速度倍率
   - 首次使用建议使用低速模式

---

## 相关文档

- [MotionSDK](motion.md) - 运动控制接口
- [安全须知](safety.md) - 安全操作指南
- [API 详细参考](api_detailed.md) - 完整 API 说明

## 示例脚本

- **`example/sdk_joycon_demo.py`**  
  **用途：** 基础连接测试工具。  
  **功能：** 仅用于测试手柄与电脑的蓝牙连接及按键响应，不涉及机械臂控制。用于排查手柄连接问题。

- **`example/test_joycon_arm_control.py`**  
  **用途：** 全功能手柄控制台。  
  **功能：** 包含完整的机械臂控制功能，支持模式切换（关节/笛卡尔）、速度调节、夹爪控制，并提供实时状态显示和交互式连接向导。

- **`example/test_joycon_display.py`**  
  **用途：** 手柄状态可视化监控。
