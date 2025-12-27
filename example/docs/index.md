# HorizonArm SDK 开发者文档

欢迎使用 HorizonArm SDK！这是专为机械臂二次开发设计的纯 Python 接口库。

---

## 设计理念

- **核心驱动**：底层算法与通信逻辑由 `Horizon_Core` 提供，确保系统稳定性
- **逻辑解耦**：SDK 为逻辑层驱动，不依赖图形界面，可在 Ubuntu、ROS2 或纯脚本环境中运行
- **开发优先**：通过 `Embodied_SDK` 提供标准的 Python 调用方式，降低开发门槛

---

## 项目结构

典型的开发项目目录结构：

```
HorizonArm_Project/
├── Horizon_Core/         # 核心驱动组件
│   ├── __init__.py       # 公开接口定义
│   ├── Control_SDK/      # 电机控制SDK
│   ├── AI_SDK/           # AI服务SDK
│   └── ...               # 其他核心模块
├── Embodied_SDK/         # 开发者接口层（源码）
│   ├── __init__.py
│   ├── horizon_sdk.py    # 顶层入口
│   ├── motion.py         # 运动控制
│   ├── visual_grasp.py   # 视觉抓取
│   ├── joycon.py         # 手柄控制
│   ├── digital_twin.py   # 数字孪生
│   ├── embodied.py       # 具身智能
│   └── io.py             # IO控制
├── config/               # 配置文件
│   ├── motor_config.json
│   ├── aisdk_config.yaml
│   └── embodied_config/
└── your_script.py        # 你的开发代码
```

---

## HorizonArmSDK - 顶层入口

**对应源码：** `Embodied_SDK/horizon_sdk.py`

`HorizonArmSDK` 是推荐的统一入口，它聚合了所有子 SDK，提供一站式访问能力。

### 初始化

```python
from Embodied_SDK import HorizonArmSDK, create_motor_controller

# 1. 创建电机字典
motors = {mid: create_motor_controller(motor_id=mid, port="COM14") for mid in range(1, 7)}
for m in motors.values():
    m.connect()

# 2. 初始化顶层 SDK
sdk = HorizonArmSDK(
    motors=motors,      # 电机字典（必需）
    camera_id=0         # 相机编号（可选，用于视觉功能）
)
```

### 子模块访问

创建 `HorizonArmSDK` 后，可直接访问以下子模块：

| 属性 | 类型 | 对应文档 | 功能 |
|------|------|----------|------|
| `sdk.motion` | [MotionSDK](motion.md) | [文档](motion.md) | 关节/末端运动、夹爪、预设动作 |
| `sdk.vision` | [VisualGraspSDK](vision.md) | [文档](vision.md) | 像素点抓取、框选抓取 |
| `sdk.follow` | [FollowGraspSDK](vision.md) | [文档](vision.md) | 视觉跟随、目标跟踪 |
| `sdk.joycon` | [JoyconSDK](joycon.md) | [文档](joycon.md) | Joy-Con 手柄控制 |
| `sdk.digital_twin` | [DigitalTwinSDK](simulation.md) | [文档](simulation.md) | MuJoCo 仿真 |
| `sdk.embodied` | [EmbodiedSDK](embodied.md) | [文档](embodied.md) | 自然语言控制 |
| `sdk.io` | [IOSDK](io.md) | [文档](io.md) | ESP32 IO 控制 |

---

## 快速示例

```python
from Embodied_SDK import HorizonArmSDK, create_motor_controller
import time

# 初始化
motors = {mid: create_motor_controller(motor_id=mid, port="COM14") for mid in range(1, 7)}
for m in motors.values():
    m.connect()

sdk = HorizonArmSDK(motors=motors)

# 运动控制
sdk.motion.move_joints([0, 90, 0, 0, 0, 0], duration=2.0)
time.sleep(2)

# 视觉抓取
sdk.vision.grasp_at_pixel(320, 240)

# 自然语言控制
sdk.embodied.run_nl_instruction("机械臂回到初始位置")

# 清理
for m in motors.values():
    m.disconnect()
```

---

## 核心功能模块

### 1. 运动控制 - [MotionSDK](motion.md)

提供机械臂基础运动能力：

- 关节空间运动
- 笛卡尔空间运动
- 预设动作执行
- 夹爪控制

**查看详情：** [运动控制文档](motion.md)

---

### 2. 视觉抓取 - [VisualGraspSDK](vision.md)

提供视觉相关能力：

- 像素点抓取
- 框选抓取
- 目标检测跟随
- 手动框选跟踪

**查看详情：** [视觉抓取文档](vision.md)

---

### 3. 手柄控制 - [JoyconSDK](joycon.md)

提供 Joy-Con 手柄控制：

- 关节模式
- 笛卡尔模式
- 模式切换
- 速度调节

**查看详情：** [手柄控制文档](joycon.md)

---

### 4. 数字孪生 - [DigitalTwinSDK](simulation.md)

提供 MuJoCo 仿真能力：

- 虚拟环境测试
- 运动可视化
- 算法验证
- 状态同步

**查看详情：** [仿真文档](simulation.md)

---

### 5. 具身智能 - [EmbodiedSDK](embodied.md)

提供自然语言控制：

- AI 理解指令
- 自动规划执行
- 复杂任务分解
- 流式反馈

**查看详情：** [具身智能文档](embodied.md)

---

### 6. IO 控制 - [IOSDK](io.md)

提供 ESP32 IO 控制：

- 数字输入读取
- 数字输出控制
- 传感器接入
- 外设联动

**查看详情：** [IO 控制文档](io.md)

---

## 开发流程建议

### 新手入门（5 步）

1. **环境准备**：[安装与环境](installation.md)
2. **⚠️  安全学习**：[安全须知](safety.md)（必读）
3. **快速上手**：[快速入门](quickstart.md)
4. **功能学习**：选择你需要的功能模块文档
5. **参考 API**：[API 详细参考](api_detailed.md)

### 开发路径

```
第 1 天：环境安装 + 安全须知 + 快速入门
第 2-3 天：学习运动控制 + 实践基础运动
第 4-5 天：学习视觉抓取 OR 手柄控制（按需选择）
第 6-7 天：学习具身智能 OR 仿真（按需选择）
第 7+ 天：开始实际项目开发
```

---

## 文档导航

### 入门必读
- [⚠️  安全须知](safety.md) - 安全操作（必读）
- [快速入门](quickstart.md) - 10 分钟上手
- [API参考](api_reference.md) - 接口速查

### 功能模块
- [MotionSDK - 运动控制](motion.md)
- [VisualGraspSDK - 视觉抓取](vision.md)
- [JoyconSDK - 手柄控制](joycon.md)
- [DigitalTwinSDK - 仿真](simulation.md)
- [EmbodiedSDK - 具身智能](embodied.md)
- [IOSDK - IO 控制](io.md)

### 扩展与参考
- [驱动扩展](driver_extension.md) - 多厂商驱动板接入
- [API 参考](api_reference.md) - 接口速查
- [常见问题](troubleshooting.md) - 故障排查

---

## 示例脚本

在 `example/` 目录下提供了丰富的示例：

| 示例文件 | 功能 |
|---------|------|
| `sdk_quickstart.py` | 基础运动控制 |
| `sdk_joycon_demo.py` | Joy-Con 手柄控制 |
| `test_visual_grasp.py` | 视觉抓取综合测试 |
| `test_io.py` | IO 控制测试 |
| `mujoco_control.py` | MuJoCo 仿真交互演示 |
| `test_multi_motor_sync.py` | 多电机同步 |
| `ai_sdk_examples/` | AI 功能示例（10+ 个） |

---

## 获取帮助

- **文档首页**：你正在查看
- **快速入门**：[quickstart.md](quickstart.md)
- **安全须知**：[safety.md](safety.md)
- **故障排查**：[troubleshooting.md](troubleshooting.md)

---

**祝你开发愉快！** 🚀
