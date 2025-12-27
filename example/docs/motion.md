# MotionSDK - 运动控制

**对应源码：** `Embodied_SDK/motion.py`

## 概述

`MotionSDK` 提供机械臂的基础运动控制能力，支持关节空间运动、笛卡尔空间运动、预设动作和夹爪控制。

## 模块入口

### 通过顶层 SDK（推荐）

```python
from Embodied_SDK import HorizonArmSDK

sdk = HorizonArmSDK(motors=motors)
motion = sdk.motion  # 获取 MotionSDK 实例
```

### 独立使用

```python
from Embodied_SDK.motion import MotionSDK

motion = MotionSDK()
motion.bind_motors(motors, use_motor_config=True)
```

---

## 核心接口

### 1. 绑定电机

#### `bind_motors(motors, use_motor_config=True, reducer_ratios=None, directions=None)`

**参数：**
- `motors`: 电机字典 `{motor_id: controller}`
- `use_motor_config`: 是否从配置文件加载参数（默认 True）
- `reducer_ratios`: 手动指定减速比 `{motor_id: ratio}`
- `directions`: 手动指定方向 `{motor_id: 1或-1}`

**示例：**
```python
# 使用配置文件
motion.bind_motors(motors, use_motor_config=True)

# 手动指定参数
motion.bind_motors(
    motors,
    use_motor_config=False,
    reducer_ratios={1: 50.0, 2: 50.0, 3: 36.0, 4: 36.0, 5: 36.0, 6: 36.0},
    directions={1: 1, 2: -1, 3: 1, 4: 1, 5: 1, 6: 1}
)
```

---

### 2. 设置运动参数

#### `set_motion_params(max_speed=100, acceleration=50, deceleration=50)`

设置全局运动参数，影响后续所有运动指令。

**参数：**

| 参数 | 默认值 | 推荐范围 | 说明 |
|------|--------|----------|------|
| `max_speed` | 100 | 50-200 | 最大速度（RPM） |
| `acceleration` | 50 | 50-200 | 加速度（RPM/s） |
| `deceleration` | 50 | 50-200 | 减速度（RPM/s） |

**⚠️ 注意：**
- 首次使用建议设置较低值（speed=50）
- 速度过高可能导致电机堵转或精度下降

**示例：**
```python
# 安全的初始设置
sdk.motion.set_motion_params(max_speed=50, acceleration=50, deceleration=50)

# 正常运行设置
sdk.motion.set_motion_params(max_speed=150, acceleration=100, deceleration=100)
```

---

### 3. 关节空间运动

#### `move_joints(joint_angles, duration=None) -> bool`

控制机械臂运动到指定关节角度。

**参数：**
- `joint_angles`: 6 个关节角度列表 `[J1, J2, J3, J4, J5, J6]`（度）
- `duration`: 运动时间（秒），None 表示使用默认速度

**返回值：**
- `True`: 运动指令发送成功
- `False`: 运动失败

**⚠️ 安全提示：**
- 关节角度以机械零位为基准，确保已正确设置零点
- 确保角度在安全范围内（参考 `config/motor_config.json`）
- 首次运动建议使用小角度增量测试

**示例：**
```python
# 回到初始位置
sdk.motion.move_joints([0, 0, 0, 0, 0, 0], duration=2.0)

# 抬起大臂
sdk.motion.move_joints([0, 45, 0, 0, 0, 0], duration=1.5)

# 复杂姿态
sdk.motion.move_joints([30, 45, -30, 0, 15, 0], duration=3.0)
```

---

### 4. 笛卡尔空间运动

#### `move_cartesian(position, orientation=None, duration=None) -> bool`

控制机械臂末端运动到指定笛卡尔坐标。

**参数：**
- `position`: 末端位置 `[x, y, z]`（毫米）
- `orientation`: 末端姿态 `[yaw, pitch, roll]`（度）
- `duration`: 运动时间（秒）

**坐标系：**
- 原点：机械臂基座中心
- X 轴：向前，Y 轴：向左，Z 轴：向上

**⚠️ 注意：**
- 笛卡尔运动依赖逆运动学求解，可能存在无解情况
- 确保目标位置在机械臂可达工作空间内
- 避免奇异点附近的运动

**示例：**
```python
# 移动到前方 300mm，高度 200mm
sdk.motion.move_cartesian([300, 0, 200])

# 指定位置和姿态
sdk.motion.move_cartesian(
    position=[250, 100, 300],
    orientation=[0, 0, 180],
    duration=2.0
)
```

---

### 5. 预设动作

#### `execute_preset_action(name, speed="normal") -> bool`

执行预定义的动作序列。

**参数：**
- `name`: 动作名称（在 `config/embodied_config/preset_actions.json` 中定义）
- `speed`: 速度模式 `"slow"` | `"normal"` | `"fast"`

**常用预设动作：**
- `home`: 回到初始位置
- `sleep`: 收纳姿态
- `wave`: 挥手动作
- `pick`: 抓取准备姿态

**示例：**
```python
# 回到初始位置
sdk.motion.execute_preset_action("home", speed="normal")

# 快速执行挥手动作
sdk.motion.execute_preset_action("wave", speed="fast")
```

---

### 6. 夹爪控制

#### `control_claw(action) -> bool`

控制夹爪开合。

**参数：**
- `action`: `1` = 张开，`0` = 闭合

**示例：**
```python
import time

# 张开夹爪
sdk.motion.control_claw(action=1)
time.sleep(1)

# 闭合夹爪
sdk.motion.control_claw(action=0)
```

#### `set_claw_params(open_angle=None, close_angle=None)`

设置夹爪开合角度。

```python
sdk.motion.set_claw_params(open_angle=90, close_angle=0)
```

#### `get_claw_params() -> dict`

获取当前夹爪参数。

```python
params = sdk.motion.get_claw_params()
print(f"张开: {params['open']}°, 闭合: {params['close']}°")
```

---

## 完整示例

```python
import time
from Embodied_SDK import HorizonArmSDK, create_motor_controller

# 1. 连接电机
motors = {mid: create_motor_controller(motor_id=mid, port="COM14") for mid in range(1, 7)}
for m in motors.values():
    m.connect()

# 2. 初始化 SDK
sdk = HorizonArmSDK(motors=motors)

# 3. 设置运动参数
sdk.motion.set_motion_params(max_speed=100, acceleration=80, deceleration=80)

# 4. 执行运动
sdk.motion.move_joints([0, 90, 0, 0, 0, 0], duration=2.0)
time.sleep(2)

sdk.motion.move_cartesian([300, 0, 200])
time.sleep(2)

# 5. 控制夹爪
sdk.motion.control_claw(action=1)
time.sleep(1)
sdk.motion.control_claw(action=0)

# 6. 清理
for m in motors.values():
    m.disconnect()
```

---

## 配置文件

### motor_config.json

`MotionSDK` 从 `config/motor_config.json` 加载电机参数：

```json
{
  "motors": {
    "1": {
      "name": "基座关节",
      "reducer_ratio": 50.0,
      "direction": 1,
      "min_angle": -180,
      "max_angle": 180
    }
  }
}
```

**设置配置目录：**
```python
import os
os.environ['HORIZONARM_CONFIG_DIR'] = '/path/to/your/config'
```

---

## 相关文档

- [快速入门](quickstart.md) - 基础使用教程
- [安全须知](safety.md) - 安全操作指南
- [配置说明](configuration.md) - 配置文件详解
- [API 详细参考](api_detailed.md) - 完整 API 说明

## 示例脚本

- `example/sdk_quickstart.py` - 基础运动示例
- `example/test_multi_motor_sync.py` - 多电机同步示例
