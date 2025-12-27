# EmbodiedSDK - 具身智能（自然语言控制）

**对应源码：** `Embodied_SDK/embodied.py`

## 概述

`EmbodiedSDK` 提供自然语言控制机械臂的能力，通过 AI 大模型理解用户指令并转换为机械臂动作。

## 前置条件

- 已配置 AI API 密钥（`config/aisdk_config.yaml`）
- 网络连接正常
- 已安装 `Horizon_Core.AI_SDK`

---

## 模块入口

### 通过顶层 SDK

```python
from Embodied_SDK import HorizonArmSDK

sdk = HorizonArmSDK(motors=motors)
embodied = sdk.embodied  # 获取 EmbodiedSDK 实例
```

### 独立使用

```python
from Embodied_SDK.embodied import EmbodiedSDK

embodied = EmbodiedSDK(
    provider="alibaba",      # AI 服务商：alibaba/deepseek
    model="qwen-turbo",      # 模型名称
    control_mode="both"      # 控制模式：real/simulation/both
)
```

---

## 核心接口

### 1. 执行自然语言指令

#### `run_nl_instruction(instruction) -> dict`

执行单条自然语言指令。

**参数：**
- `instruction`: 自然语言指令（字符串）

**返回值：**
- `dict`: 包含执行结果的字典
  - `success`: 是否成功
  - `action`: 执行的动作
  - `result`: 执行结果详情

**示例：**
```python
# 基础运动指令
result = embodied.run_nl_instruction("机械臂回到初始位置")
print(f"执行结果: {result['success']}")

# 关节控制指令
result = embodied.run_nl_instruction("将第一个关节转动30度")

# 末端运动指令
result = embodied.run_nl_instruction("移动到坐标(300, 200, 400)")

# 抓取指令
result = embodied.run_nl_instruction("抓取红色的物体")

# 复杂指令
result = embodied.run_nl_instruction("先回到初始位置，然后执行挥手动作")
```

---

### 2. 流式执行（带回调）

#### `run_nl_instruction_stream(instruction, action_handler=None, progress_handler=None, completion_handler=None)`

流式执行自然语言指令，支持实时反馈。

**参数：**
- `instruction`: 自然语言指令
- `action_handler`: 动作开始回调函数
- `progress_handler`: 进度更新回调函数
- `completion_handler`: 完成回调函数

**示例：**
```python
def on_action(action_name):
    print(f"开始执行动作: {action_name}")

def on_progress(progress):
    print(f"进度: {progress}%")

def on_completion(result):
    print(f"完成: {result}")

embodied.run_nl_instruction_stream(
    "机械臂做一个挥手动作",
    action_handler=on_action,
    progress_handler=on_progress,
    completion_handler=on_completion
)
```

---

### 3. 查询可用功能

#### `get_available_functions() -> Dict[str, str]`

获取系统支持的所有功能列表。

**返回值：**
- `dict`: 功能名称 → 功能描述

**示例：**
```python
functions = embodied.get_available_functions()
print("系统支持的功能：")
for name, desc in functions.items():
    print(f"  - {name}: {desc}")
```

---

### 4. 对话历史管理

#### `get_history() -> list`

获取对话历史记录。

```python
history = embodied.get_history()
for entry in history:
    print(f"用户: {entry['user']}")
    print(f"助手: {entry['assistant']}")
```

#### `clear_history()`

清空对话历史。

```python
embodied.clear_history()
```

---

## 完整示例

### 基础自然语言控制

```python
from Embodied_SDK import HorizonArmSDK, create_motor_controller

# 1. 连接电机
motors = {mid: create_motor_controller(motor_id=mid, port="COM14") for mid in range(1, 7)}
for m in motors.values():
    m.connect()

# 2. 初始化 SDK
sdk = HorizonArmSDK(motors=motors)

# 3. 初始化具身智能 SDK
embodied = sdk.embodied

# 4. 执行自然语言指令
instructions = [
    "机械臂回到初始位置",
    "将第一个关节转动30度",
    "移动到坐标(300, 200, 400)",
    "执行一个挥手动作"
]

for instruction in instructions:
    print(f"\n执行指令: {instruction}")
    result = embodied.run_nl_instruction(instruction)
    
    if result['success']:
        print(f"✅ 执行成功")
    else:
        print(f"❌ 执行失败: {result.get('error')}")

# 5. 清理
for m in motors.values():
    m.disconnect()
```

---

### 交互式对话控制

```python
from Embodied_SDK.embodied import EmbodiedSDK

# 初始化
embodied = EmbodiedSDK(provider="alibaba", model="qwen-turbo")

print("具身智能交互式控制")
print("输入自然语言指令，输入 'quit' 退出")
print("=" * 50)

while True:
    # 获取用户输入
    instruction = input("\n您的指令: ").strip()
    
    if instruction.lower() in ['quit', 'exit', 'q']:
        break
    
    if not instruction:
        continue
    
    # 执行指令
    try:
        result = embodied.run_nl_instruction(instruction)
        
        if result['success']:
            print(f"✅ 已执行: {result.get('action', '未知动作')}")
        else:
            print(f"❌ 执行失败: {result.get('error', '未知错误')}")
            
    except Exception as e:
        print(f"❌ 发生错误: {e}")

print("\n再见！")
```

---

### 先在仿真中测试（推荐）

```python
from Embodied_SDK import HorizonArmSDK

# 1. 初始化（不连接真实电机）
sdk = HorizonArmSDK(motors={})

# 2. 启动仿真
sdk.digital_twin.start_simulation()

# 3. 配置具身智能使用仿真模式
embodied = sdk.embodied

# 4. 在仿真中测试指令
test_instructions = [
    "机械臂向上移动100mm",
    "旋转第二个关节45度",
    "执行挥手动作"
]

print("在仿真中测试指令...")
for instruction in test_instructions:
    print(f"\n测试: {instruction}")
    result = embodied.run_nl_instruction(instruction)
    print(f"结果: {'成功' if result['success'] else '失败'}")

# 5. 观察仿真结果，确认无误后再连接真实机械臂
```

---

## 支持的指令类型

### 1. 运动控制
- "回到初始位置"
- "移动到坐标(x, y, z)"
- "向前移动50mm"
- "向上移动100mm"

### 2. 关节控制
- "第一个关节转动30度"
- "第二个关节转到45度"
- "所有关节归零"

### 3. 预设动作
- "执行挥手动作"
- "执行抓取准备姿态"
- "进入收纳姿态"

### 4. 夹爪控制
- "张开夹爪"
- "闭合夹爪"
- "抓取"

### 5. 视觉任务（如已连接相机）
- "抓取红色的物体"
- "跟随移动的目标"

---

## 配置文件

### aisdk_config.yaml

AI SDK 配置文件（`config/aisdk_config.yaml`）：

```yaml
providers:
  alibaba:
    api_key: ${ALI_API_KEY}
    default_params:
      max_tokens: 2000
      temperature: 0.7
    enabled: true
    
  deepseek:
    api_key: ${DEEPSEEK_API_KEY}
    default_params:
      max_tokens: 2000
      temperature: 0.7
    enabled: true
```

**设置 API 密钥：**

```bash
# Linux/Mac
export ALI_API_KEY="your_api_key"

# Windows
set ALI_API_KEY=your_api_key
```

---

## 注意事项

### 安全建议

1. **先仿真测试**：
   - 自然语言指令存在不确定性
   - 建议先在仿真中测试，确认无误后再用于真实机械臂

2. **指令明确性**：
   - 使用清晰、明确的指令
   - 避免模糊或复杂的描述

3. **监控执行**：
   - 执行过程中保持监控
   - 准备好急停措施

### 限制说明

- 依赖 AI 大模型，需要网络连接
- 复杂指令可能理解不准确
- 不适用于高精度、安全关键的任务

---

## 相关文档

- [MotionSDK](motion.md) - 运动控制接口
- [DigitalTwinSDK](simulation.md) - 仿真测试
- [安全须知](safety.md) - 安全操作指南
- [配置说明](configuration.md) - AI API 配置

## 示例脚本

- `example/ai_sdk_examples/smart_chat_example.py` - 智能对话示例
- `example/ai_sdk_examples/smart_multimodal_chat_demo.py` - 多模态对话示例

