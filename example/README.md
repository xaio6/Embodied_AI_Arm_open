# HorizonArm SDK 示例代码目录

欢迎使用 HorizonArm SDK！本目录提供完整的示例代码和开发者工具。

## 📚 首次使用必读

### 🎯 不知道从哪里开始？

1. **了解SDK** → 📖 **[SDK完全介绍](SDK完全介绍)** ⭐ **强烈推荐先看这个！**
   - SDK架构和模块总览
   - 各模块功能详解和API示例
   - 核心概念和设计理念
   - 典型应用流程
   
2. **快速上手** → 🚀 **`quickstart_guide.py`** (5分钟体验)
   - 连接电机
   - 读取状态
   - 执行运动
   
3. **深入学习** → 📚 按照下方的学习路径逐步学习

---

## 📂 目录结构

```
example/
├── quickstart_guide.py              ⭐ 【从这里开始】5分钟快速入门
│
├── control_sdk_examples/            📚 Control SDK 功能示例
│   ├── README.md                    - 学习路径指南
│   ├── motor_usage_example.py       - 单电机完全指南
│   ├── visual_grasp_example.py      - 视觉抓取功能
│   ├── joycon_control_example.py    - 手柄遥操作
│   ├── multi_motor_sync_example.py  - 多电机同步（简化版）
│   ├── io_control_example.py        - IO控制
│   └── digital_twin_example.py      - MuJoCo仿真
│
├── ai_sdk_examples/                 🧠 AI SDK 功能示例
│   ├── config_example.py            - 配置管理
│   ├── LLM_usage.py                 - 大语言模型
│   ├── asr_usage_example.py         - 语音识别
│   ├── tts_usage_example.py         - 语音合成
│   ├── multimodal_usage_example.py  - 多模态AI
│   ├── smart_chat_example.py        - 智能对话
│   └── ...
│
├── developer_tools/                 🛠️ 开发者调试工具
│   ├── README.md                    - 工具说明
│   ├── joycon_sensor_display.py     - Joy-Con传感器监控
│   └── ...
│
└── (旧示例 - 保留供参考)
    ├── sdk_quickstart.py            - 完整机械臂控制（保留）
    ├── test_interactive.py          - 完整单电机测试（保留）
    ├── test_multi_motor_sync.py     - 完整多机同步（保留）
    └── ...
```

## 🚀 快速开始

### 第一次使用？从这里开始！

```bash
cd example
python quickstart_guide.py
```

5分钟内您将学会：
- ✅ 连接一台电机
- ✅ 读取电机状态
- ✅ 执行简单运动
- ✅ 了解SDK核心概念

### 已经完成快速入门？继续学习

根据您的需求选择：

#### 🎯 我要学习机械臂控制
```bash
cd control_sdk_examples
# 1. 单电机控制
python motor_usage_example.py

# 2. 多关节运动（待补充）
python motion_usage_example.py
```

#### 👁️ 我要使用视觉功能
```bash
cd control_sdk_examples
python visual_grasp_example.py
```

#### 🎮 我要用手柄控制
```bash
cd control_sdk_examples
python joycon_control_example.py
```

#### 🧠 我要使用AI功能
```bash
cd ai_sdk_examples
python config_example.py        # 先了解配置
python LLM_usage.py             # 再使用AI功能
```

## 📊 示例对比：简化版 vs 完整版

| 功能 | 简化教学版 | 完整专业版 |
|------|-----------|-----------|
| **单电机控制** | `control_sdk_examples/motor_usage_example.py`<br>7个核心功能，带详细说明 | `test_interactive.py`<br>40+功能，所有API覆盖 |
| **多机同步** | `control_sdk_examples/multi_motor_sync_example.py`<br>3个核心同步模式 | `test_multi_motor_sync.py`<br>26+功能，包含诊断工具 |
| **手柄控制** | `control_sdk_examples/joycon_control_example.py`<br>分4级学习，整合3个原示例 | `test_joycon_*.py`<br>3个独立文件 |

💡 **建议：**
- 🎓 **学习阶段**：使用 `control_sdk_examples/` 下的简化版
- 🔧 **开发阶段**：参考完整版的高级功能
- 🐛 **调试阶段**：使用 `developer_tools/` 下的专业工具

## 🎯 学习路径推荐

### 路径1：机械臂控制工程师
```
quickstart_guide.py
    ↓
motor_usage_example.py (30min)
    ↓
motion_usage_example.py (30min)
    ↓
multi_motor_sync_example.py (20min)
    ↓
test_interactive.py (参考完整API)
```

### 路径2：视觉应用开发者
```
quickstart_guide.py
    ↓
motor_usage_example.py (基础)
    ↓
visual_grasp_example.py (45min)
    ↓
结合AI SDK: multimodal_usage_example.py
```

### 路径3：人机交互开发者
```
quickstart_guide.py
    ↓
joycon_control_example.py (40min)
    ↓
io_control_example.py (20min)
    ↓
结合AI SDK: smart_chat_example.py
```

### 路径4：AI集成开发者
```
ai_sdk_examples/config_example.py
    ↓
LLM_usage.py
    ↓
multimodal_usage_example.py
    ↓
smart_multimodal_voice_chat_demo.py
    ↓
结合Control SDK完成具身智能
```

## 🔑 关键概念

### Control SDK核心
- **电机控制**: 速度/位置/力矩三种模式
- **运动学**: 关节空间 vs 笛卡尔空间
- **同步控制**: Pre-load → Trigger → Execute
- **IO控制**: DI读取 + DO输出
- **数字孪生**: MuJoCo仿真验证

### AI SDK核心
- **配置管理**: YAML配置 + 运行时修改
- **大语言模型**: LLM接口统一封装
- **多模态**: 视觉 + 语音 + 文本整合
- **具身智能**: AI + 机械臂深度结合

## ⚠️ 重要说明

### 关于SDK版本
本开发包使用 `Horizon_Core/` 封装库，提供稳定的API接口。所有示例代码均基于此版本编写，可直接用于您的项目开发。

### 关于代码集成
本SDK专注于提供机械臂控制和AI功能的核心接口。示例代码展示了完整的API调用方法，您可以：
- 直接复制示例代码到项目中
- 集成到自己的应用架构
- 开发自定义的用户界面
- 实现特定的业务逻辑

## 📖 文档资源

- **SDK完全介绍**: `SDK完全介绍.md` ⭐ **必读！包含所有模块的详细说明**
- **API参考**: `docs/api_reference.md`
- **故障排除**: `docs/troubleshooting.md`
- **快速入门**: `docs/quickstart.md`
- **开发者学习路线**: `../开发者学习路线.md`

## 🆘 获取帮助

遇到问题？按以下顺序排查：

1. ✅ 检查 `docs/troubleshooting.md`
2. ✅ 运行对应的系统自检（如 `visual_grasp_example.py` 的自检功能）
3. ✅ 参考完整版示例的详细API调用
4. ✅ 使用 `developer_tools/` 下的诊断工具
5. ✅ 联系技术支持

## 🎓 从示例到生产

示例代码的设计理念：
- **可复制**: 代码片段可直接复制到您的项目
- **可扩展**: 提供了清晰的扩展点
- **可学习**: 每个功能都有详细注释和说明

从示例到生产代码的建议：
1. 先运行示例，理解功能
2. 复制核心代码片段
3. 根据需求调整参数
4. 添加错误处理和日志
5. 集成到您的应用架构中

---

**版本**: 1.4  
**更新日期**: 2024  
**维护**: HorizonArm Team  

祝您开发顺利！🚀

