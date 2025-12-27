# ⚠️ 安全须知

## 💀【高危警告】关于电机失能 (Disable)

### 🚨 重要警告

**如果您使用的机械臂电机没有物理抱闸（刹车）功能，请特别注意：**

- **❌ 严禁在代码中随意调用 `motor.control_actions.disable()` 接口！**
- **❌ 严禁在程序退出时自动失能！**
- **❌ 严禁在停止运动时使用失能！**
- **❌ 严禁在机械臂悬空状态下失能！**

### ⚠️ 失能的后果（无刹车电机）

对于**没有机械刹车的电机**，一旦失能，关节将**瞬间失去力矩锁止能力**。在重力作用下，机械臂会**立即掉落**，导致：

1. **机械臂砸到桌面** → 关节、连杆损坏
2. **末端执行器/夹爪砸坏** → 相机、传感器损坏  
3. **可能砸伤操作人员** → 手指、手臂受伤
4. **桌面砸坏** → 工作台损坏

### ✅ 正确做法

| 场景 | ❌ 错误做法 | ✅ 正确做法 |
|------|-----------|-----------|
| **程序退出** | `motor.disable()` | `motor.disconnect()` - 仅断开通信，保持使能 |
| **紧急停止** | `motor.disable()` | `motor.stop()` - 停止运动，保持使能 |
| **长时间不用** | `motor.disable()` | `motor.stop()` + 保持使能，或物理断电 |
| **调整位置** | 直接失能 | 先运动到安全姿态（趴下），再断电 |

### 💡 关键概念

- **`stop()`**: 停止运动，但保持电机使能（继续输出力矩锁住位置）✅ 安全
- **`disconnect()`**: 断开通信连接，但电机保持使能状态 ✅ 安全  
- **`disable()`**: 切断电机驱动电流，失去保持力 ❌ 对于无刹车电机极度危险！

### 📋 如何确认您的机械臂是否有刹车？

**有刹车的电机特征：**
- ✅ 断电后关节无法被手动转动（被锁住）
- ✅ 失能后机械臂不会掉落
- ✅ 电机规格书明确标注"带抱闸"或"带刹车"

**无刹车的电机特征：**
- ❌ 断电后关节可以被轻松转动
- ❌ 失能后机械臂会在重力作用下掉落
- ❌ 电机规格书中无刹车相关说明

**⚠️  如果不确定，请按照"无刹车"的安全规范操作！**

### 📝 代码示例

**❌ 错误示例（千万不要这样写）：**
```python
# 错误！退出时失能
try:
    sdk.move_joints([0, 90, 0, 0, 0, 0])
finally:
    for motor in motors.values():
        motor.disable()  # ❌ 错误！机械臂会掉落！
```

**✅ 正确示例：**
```python
# 正确！退出时只断开通信
try:
    sdk.move_joints([0, 90, 0, 0, 0, 0])
finally:
    for motor in motors.values():
        motor.disconnect()  # ✅ 正确！保持使能，仅断开通信
```

---

**在使用 SDK 控制机械臂之前，请务必完整阅读本章节！**

不当的操作可能导致机械臂损坏、人员受伤或设备故障。

---

## 🔴 首次使用前必读

### 1. 回零参数检查（极其重要）

**机械臂在首次使用或更换驱动板后，必须先确认回零参数是否正确。**

#### 为什么回零参数如此重要？

- 机械臂依靠回零来建立坐标系统
- 如果回零参数错误，机械臂会运动到错误的"零点"位置
- 这可能导致机械臂撞击自身或周围物体，造成损坏

#### 如何检查回零参数？

**方法 1：手动确认零点位置**

```python
from Embodied_SDK import create_motor_controller

# 连接 1 号电机（示例）
motor = create_motor_controller(motor_id=1, port="COM14")
motor.connect()

# 查询当前零点位置是否已设置
current_pos = motor.read_parameters.get_position()
print(f"当前位置: {current_pos}°")

# 如果零点不准确，手动调整到正确位置后设置零点
# 1. 先手动（示教模式或小心运动）将关节调整到机械零位
# 2. 执行以下命令将当前位置设为零点
motor.homing_commands.set_zero_position(save_to_chip=True)
print("零点已重新设置并保存")
```

**方法 2：使用限位开关自动回零（推荐，如果驱动板支持）**

```python
# 启动自动回零流程
motor.control_actions.start_homing()

# 等待回零完成（最多 30 秒）
if motor.homing_commands.wait_for_homing_complete(timeout=30):
    print("回零成功")
else:
    print("回零超时，请检查限位开关或手动设置零点")
```

#### ⚠️ 首次回零前的安全措施

1. **清空工作区域**：确保机械臂周围无障碍物
2. **准备急停**：手放在电源开关或急停按钮附近
3. **低速测试**：首次运动使用最低速度（速度参数设为 10-20）
4. **单轴测试**：先测试单个关节，确认方向正确后再测试全部关节
5. **小角度测试**：先运动 5-10 度，确认无异常后再增大幅度

---

## 🟡 日常使用安全规范

### 2. 速度与加速度限制

**不要设置过高的速度或加速度，这可能导致：**
- 电机堵转保护触发
- 机械结构损坏
- 控制精度下降

**推荐参数范围：**

| 参数 | 最小值 | 推荐值 | 最大值 | 说明 |
|------|--------|--------|--------|------|
| 速度 (speed) | 10 | 100-200 | 500 | 单位：RPM |
| 加速度 (acceleration) | 50 | 100-200 | 1000 | 单位：RPM/s |
| 减速度 (deceleration) | 50 | 100-200 | 1000 | 单位：RPM/s |

```python
# 设置安全的运动参数
sdk.motion.set_motion_params(
    max_speed=150,        # 适中速度
    acceleration=100,     # 平滑加速
    deceleration=100      # 平滑减速
)
```

### 3. 关节角度限制

**每个关节都有物理限位，超出限位可能损坏机械结构。**

检查你的机械臂的实际限位角度（在 `config/motor_config.json` 中配置）：

```json
{
  "motors": {
    "1": {
      "min_angle": -180,   // 最小角度
      "max_angle": 180     // 最大角度
    }
  }
}
```

**在代码中添加限位检查：**

```python
def safe_move_joints(sdk, target_angles):
    """带限位检查的安全运动函数"""
    # 从配置文件读取限位
    limits = {
        1: (-180, 180),
        2: (-90, 90),
        3: (-135, 135),
        4: (-180, 180),
        5: (-90, 90),
        6: (-180, 180)
    }
    
    # 检查每个关节角度
    for i, angle in enumerate(target_angles, start=1):
        min_ang, max_ang = limits.get(i, (-180, 180))
        if not (min_ang <= angle <= max_ang):
            print(f"⚠️  警告：关节 {i} 的目标角度 {angle}° 超出限位 [{min_ang}, {max_ang}]")
            return False
    
    # 通过检查后再运动
    return sdk.motion.move_joints(target_angles, duration=2.0)
```

### 4. 工作空间限制

**笛卡尔空间运动时，注意机械臂的可达空间：**

```python
# 典型 6 轴机械臂的可达范围（示例，具体参数以实际机械臂为准）
# X 轴：-500mm ~ 500mm
# Y 轴：-500mm ~ 500mm
# Z 轴：0mm ~ 800mm

def check_workspace(x, y, z):
    """检查目标位置是否在工作空间内"""
    if not (-500 <= x <= 500):
        print(f"⚠️  X 坐标 {x} 超出范围")
        return False
    if not (-500 <= y <= 500):
        print(f"⚠️  Y 坐标 {y} 超出范围")
        return False
    if not (0 <= z <= 800):
        print(f"⚠️  Z 坐标 {z} 超出范围")
        return False
    return True

# 使用前检查
if check_workspace(300, 200, 400):
    sdk.motion.move_cartesian([300, 200, 400])
else:
    print("目标位置超出工作空间，已取消运动")
```

### 5. 急停与安全停止

**在任何异常情况下，立即执行急停：**

```python
# 方法 1：断开通信（推荐）
for motor in motors.values():
    motor.disconnect()

# 方法 2：如果使用 JoyconSDK，可使用紧急停止
# sdk.joycon.emergency_stop()
```

**建议在代码中添加异常处理：**

```python
import sys

try:
    sdk.motion.move_joints([0, 90, 0, 0, 0, 0], duration=2.0)
except KeyboardInterrupt:
    print("\n检测到 Ctrl+C，执行急停...")
    for motor in motors.values():
        motor.disconnect()
    sys.exit(0)
except Exception as e:
    print(f"发生错误：{e}，执行急停...")
    for motor in motors.values():
        motor.disconnect()
    raise
```

---

## 🟢 视觉抓取安全

### 6. 视觉抓取前的准备

**视觉抓取涉及自动运动，风险更高，必须做好以下准备：**

#### 相机标定

- **未标定或标定不准确的相机会导致抓取位置错误**
- 首次使用视觉功能前，必须完成手眼标定
- 标定文件：`config/calibration_parameter.json`

```python
# 检查标定文件是否存在
import os
calib_file = "config/calibration_parameter.json"
if not os.path.exists(calib_file):
    print("⚠️  警告：未找到标定文件，视觉抓取可能不准确！")
    print("请先完成手眼标定再使用视觉功能")
else:
    print("✅ 标定文件已找到")
```

#### 抓取参数检查

```python
# 设置合理的抓取参数
sdk.vision.set_grasp_params(
    grasp_height=50,        # 抓取高度（mm），不要设置过低，避免碰撞桌面
    approach_height=100,    # 接近高度（mm），给足够的安全间隙
    tcp_offset=[0, 0, 120], # 工具中心点偏移（mm），根据夹爪长度调整
    retreat_height=150      # 抓取后抬升高度（mm）
)
```

#### 测试流程

1. **先测试单次点击**：手动点击一个已知位置，观察机械臂是否运动到正确位置
2. **逐步降低高度**：从安全高度开始，逐步降低 `grasp_height`
3. **准备急停**：整个测试过程中手放在急停按钮附近

---

## 🔵 自然语言控制安全

### 7. 自然语言控制的限制

**自然语言控制依赖 AI 解析，存在不确定性：**

- ✅ **推荐用于**：简单明确的指令（"回到初始位置"、"抬起大臂"）
- ❌ **不推荐用于**：高精度任务、安全关键场景

**使用建议：**

```python
# 方法 1：先在仿真中测试
sdk.digital_twin.start_simulation()  # 启动仿真
result = sdk.embodied.run_nl_instruction("机械臂向上移动 100mm")
# 观察仿真结果，确认无误后再在真实机械臂上执行

# 方法 2：先检查执行结果
result = sdk.embodied.run_nl_instruction("机械臂回到初始位置")
if not result.get("execution_result", {}).get("success"):
    print("指令执行失败，请检查日志")
```

---

## 📋 日常使用检查清单

每次使用前，按以下清单检查：

- [ ] 确认 Python 版本为 3.12+
- [ ] 清空机械臂工作区域
- [ ] 确认回零参数正确
- [ ] 检查各关节能够自由活动（无卡死）
- [ ] 确认电机温度正常（< 60°C）
- [ ] 准备好急停措施
- [ ] 首次运动使用低速测试
- [ ] 检查电源供电稳定

---

## 🆘 异常情况处理

| 异常情况 | 应对措施 |
|----------|----------|
| 机械臂运动方向错误 | 立即急停，修改 `motor_config.json` 中的 `direction` 参数 |
| 电机发出异响 | 立即断电，检查是否有机械卡死或干涉 |
| 电机过热（> 70°C） | 停止使用，等待冷却，检查负载是否过大 |
| 堵转保护触发 | 检查是否有障碍物，降低速度/加速度参数 |
| 视觉抓取位置偏差大 | 重新标定相机，检查标定文件 |
| 通信超时频繁 | 检查 CAN 总线连接，降低通信频率 |

---

## 📞 技术支持

如遇到本文档未涵盖的安全问题，请立即停止使用并联系技术支持。

**记住：安全永远是第一位的！** 🛡️

