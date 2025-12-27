# 快速入门

⚠️  **首次使用前必读：** 请先阅读 [安全须知](safety.md)，确保回零参数正确设置！

---

## 一、环境准备

### 1.1 系统要求

- **Python 版本**：必须 3.12+（低于 3.12 可能导致兼容性问题）
- **操作系统**：Windows 10/11，Ubuntu 20.04+
- **硬件**：CAN 适配器（如 CANable），USB 摄像头（可选）

### 1.2 安装依赖

```bash
# 进入 SDK 目录
cd HorizonArm_SDK

# 安装依赖
pip install -r requirements.txt
```

**核心依赖：**
- `pyserial`：串口通信
- `opencv-python`：相机采集与视觉处理
- `numpy`：数值计算
- `mujoco`：仿真（可选）

### 1.3 硬件连接

1. **连接 CAN 适配器**到电脑 USB 口
2. **机械臂上电**
3. **查看串口号**：
   - Windows：设备管理器 → 端口 → 记下 `COM14` 这样的编号
   - Linux：通常是 `/dev/ttyUSB0` 或 `can0`

### 1.4 配置文件

**配置目录：** `config/`

建议设置环境变量指向配置目录：

```python
import os
os.environ['HORIZONARM_CONFIG_DIR'] = '/path/to/your/config'
```

**主要配置文件：**

| 文件 | 用途 |
|------|------|
| `motor_config.json` | 电机减速比、方向、限位 |
| `calibration_parameter.json` | 相机标定参数 |
| `embodied_config/preset_actions.json` | 预设动作 |
| `aisdk_config.yaml` | AI API 配置 |

---

## 二、核心概念

### 2.1 motors 字典

SDK 以 `motors` 字典作为机械臂控制的基础上下文：

- **结构**：`{motor_id: motor_controller}`
- **motor_id**：电机地址（1-6 对应 6 轴）
- **motor_controller**：电机控制器实例

```python
from Embodied_SDK import create_motor_controller

motors = {mid: create_motor_controller(motor_id=mid, port="COM14") for mid in range(1, 7)}
for m in motors.values():
    m.connect()
```

### 2.2 顶层入口与子模块

`HorizonArmSDK` 是推荐的统一入口：

```python
from Embodied_SDK import HorizonArmSDK

sdk = HorizonArmSDK(motors=motors, camera_id=0)
```

**子模块：**
- `sdk.motion` - 运动控制
- `sdk.vision` - 视觉抓取
- `sdk.follow` - 视觉跟随
- `sdk.joycon` - 手柄控制
- `sdk.digital_twin` - 仿真
- `sdk.embodied` - 自然语言控制
- `sdk.io` - IO 控制

### 2.3 坐标与单位约定

| 参数 | 单位 | 说明 |
|------|------|------|
| 关节角度 | 度（deg） | [J1, J2, J3, J4, J5, J6] |
| 末端位置 | 毫米（mm） | [x, y, z] |
| 末端姿态 | 度（deg） | [yaw, pitch, roll] |

---

## 三、⚠️  回零参数设置（极其重要）

**机械臂在首次使用前，必须确认回零参数是否正确。回零参数错误可能导致机械臂损坏！**

### 3.1 快速检查

```python
from Embodied_SDK import create_motor_controller

motor = create_motor_controller(motor_id=1, port="COM14")
motor.connect()

# 查询当前位置
pos = motor.read_parameters.get_position()
print(f"当前位置: {pos}°")
```

### 3.2 手动设置零点（首次使用必做）

```python
# 1. 手动将关节调整到机械零位
#    （通常是关节的中间位置，或者有物理标记的位置）

# 2. 执行以下命令将当前位置设为零点
motor.homing_commands.set_zero_position(save_to_chip=True)
print("✅ 零点已设置并保存")

# 3. 对所有 6 个关节重复此操作
```

**详细步骤请查看：[安全须知 - 回零参数检查](safety.md#1-回零参数检查极其重要)**

### 3.3 首次运动安全检查清单

- [ ] 清空机械臂周围障碍物
- [ ] 手放在急停按钮附近
- [ ] 首次运动使用低速（speed=50）
- [ ] 先测试单个关节小角度运动（±10度）
- [ ] 确认运动方向正确后再增大幅度

---

## 四、第一个程序（4 步）

### 步骤 1：启动程序

```bash
python example/sdk_quickstart.py
```

### 步骤 2：交互式配置

程序启动后，会首先询问硬件连接信息：

```text
[配置] 连接机械臂电机
------------------------------
请输入串口号 (默认 COM14): 
```

1.  输入你的串口号（如 `COM3` 或 `/dev/ttyUSB0`），直接回车使用默认值。
2.  输入电机 ID 列表（默认 1-6），通常直接回车即可。

### 步骤 3：功能菜单选择

配置完成后，将显示主功能菜单：

```text
======================================================================
 🚀 HorizonArm SDK 快速入门 (交互模式)
======================================================================
[1] 关节运动测试 (J1-J6)
[2] 笛卡尔运动测试 (XYZ+RPY)
[3] 夹爪控制测试
[4] 执行预设动作 (Home/Sleep)
[5] 查看电机状态
[0] 退出
----------------------------------------------------------------------
请选择功能 (0-5): 
```

你可以通过输入数字来选择要测试的功能模块。

### 步骤 4：测试流程建议

建议按照以下顺序进行测试：

1.  **查看电机状态 [5]**：确认所有电机电压、温度正常，且位置读数合理。
2.  **关节运动测试 [1]**：会让机械臂进行小幅度的关节运动，验证电机方向和控制链路。
3.  **夹爪控制测试 [3]**：验证夹爪的开合功能。
4.  **预设动作 [4]**：测试 "Home"（回零）和 "Sleep"（收纳）姿态。


---

## 五、完整示例代码

请直接参考 `example/sdk_quickstart.py` 源文件。该文件展示了如何：
1.  **动态连接电机**：通过用户输入灵活配置串口和 ID。
2.  **构建交互式菜单**：使用 `while` 循环和 `input` 处理用户指令。
3.  **调用 SDK 功能**：
    *   `sdk.motion.move_joints()`
    *   `sdk.motion.move_cartesian()`
    *   `sdk.motion.control_claw()`
    *   `sdk.motion.execute_preset_action()`
    *   `sdk.motion.get_motor_status()`

代码片段示例（初始化与菜单循环）：

```python
def main():
    clear_screen()
    print_header()
    
    # 1. 连接向导
    port, motor_ids = connect_motors()
    if not port: return

    # ... (连接逻辑) ...
    
    # 2. 初始化 SDK
    sdk = HorizonArmSDK(motors=motors)
    # 设置安全参数
    sdk.motion.set_motion_params(max_speed=50, acceleration=50, deceleration=50)

    # 3. 主循环
    while True:
        print_menu()
        choice = input("请选择功能 (0-5): ").strip()
        
        if choice == '1':
            test_joint_motion(sdk)
        elif choice == '2':
            test_cartesian_motion(sdk)
        elif choice == '3':
            test_claw(sdk)
        elif choice == '4':
            test_preset_action(sdk)
        elif choice == '5':
            show_motor_status(sdk)
        elif choice == '0':
            break
```

---

## 六、运行示例脚本

项目提供了交互式的示例脚本，请按照屏幕提示操作：

```bash
# 启动快速入门示例
python example/sdk_quickstart.py
```

---

## 七、常见问题

### Q1: 机械臂运动方向反了怎么办？

**A:** 立即按急停，然后修改 `config/motor_config.json`：

```json
{
  "motors": {
    "1": {
      "direction": -1  // 改为 -1 反转方向（原来是 1）
    }
  }
}
```

### Q2: 连接失败怎么办？

**A:** 检查：
- 串口号是否正确（Windows 设备管理器）
- CAN 适配器是否连接
- 机械臂是否上电
- 驱动板 CAN 速率是否为 500K

### Q3: 首次运行注意什么？

**A:** 
1. 降低速度（max_speed=50）
2. 小角度测试（±5-10 度）
3. 单轴测试（先测试单个关节）
4. 准备急停（手放在电源开关附近）
5. 清空障碍（确保工作区域安全）

---

## 八、下一步

- **必读**：[安全须知](safety.md) - 详细的安全操作指南
- **学习模块**：
  - [MotionSDK - 运动控制](motion.md)
  - [VisualGraspSDK - 视觉抓取](vision.md)
  - [JoyconSDK - 手柄控制](joycon.md)
  - [DigitalTwinSDK - 仿真](simulation.md)
  - [EmbodiedSDK - 具身智能](embodied.md)
  - [IOSDK - IO 控制](io.md)
- **参考**：[API 参考](api_reference.md) - 接口速查
- **故障排查**：[常见问题](troubleshooting.md)

---

**祝你使用愉快！记住：安全第一！** 🛡️
