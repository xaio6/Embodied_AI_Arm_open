# 具身智能分层决策系统

## 系统概述

本系统实现了一个三层架构的具身智能分层决策模型，专为6轴机械臂控制设计。系统能够接收自然语言指令，通过高层LLM决策、中层函数调用、底层执行的流程完成机械臂的智能控制。

**核心特性**：LLM直接选择具体函数并传递参数，无需模式判断，更加直接高效。

## 架构设计

### 三层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    高层决策器 (High-Level Planner)           │
│  - 与LLM交互进行函数选择                                      │
│  - 将自然语言指令转换为函数调用JSON                           │
│  - 智能选择合适函数和参数                                     │
└─────────────────────┬───────────────────────────────────────┘
                      │ Function Call JSON
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   中层任务解析器 (Middle-Level Parser)        │
│  - 解析高层返回的函数调用JSON                                │
│  - 直接调用指定函数并传递参数                                 │
│  - 处理函数执行结果和错误                                     │
└─────────────────────┬───────────────────────────────────────┘
                      │ Function Execution
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    底层执行器 (Low-Level Executor)           │
│  - 具体的机械臂控制函数                                       │
│  - 实现平滑运动控制                                           │
│  - 处理硬件接口和安全约束                                     │
└─────────────────────────────────────────────────────────────┘
```

### 支持的函数类型

1. **关节角度控制函数**: `control_arm_joints(joint_angles, duration)`
   - 直接控制6个关节的角度
   - 支持运动时间参数

2. **末端位置控制函数**: `control_arm_position(position, orientation, duration)`
   - 通过逆运动学控制末端位置和姿态
   - 支持位置和姿态参数

3. **预设动作函数**: `execute_preset_action(action_name, speed)`
   - 执行预定义的动作序列
   - 支持速度调节参数

## 文件结构

```
embodied/
├── hierarchical_decision_system.py    # 分层决策系统核心 (函数调用架构)
├── embodied_func.py                   # 底层功能函数库
├── prompt.py                          # LLM提示词模板 (函数调用模式)
├── quick_test.py                      # 快速测试脚本
├── test_function_calling.py           # 函数调用架构测试
└── README.md                          # 系统说明文档
```

## 核心组件

### 1. 高层决策器 (HighLevelPlanner)

```python
class HighLevelPlanner:
    def __init__(self, use_llm=True, provider="alibaba", model="qwen-turbo"):
        # 初始化LLM客户端
        
    def plan_task(self, user_instruction: str) -> Dict[str, Any]:
        # 将用户指令转换为函数调用JSON
        # 返回: {"function": "函数名", "parameters": {...}}
```

### 2. 中层任务解析器 (MiddleLevelTaskParser)

```python
class MiddleLevelTaskParser:
    def __init__(self):
        # 导入embodied_func模块用于动态函数调用
        
    def parse_and_execute(self, function_call_json: Dict[str, Any]) -> Dict[str, Any]:
        # 解析函数调用JSON并直接执行对应函数
```

### 3. 底层执行器 (功能函数)

```python
# 核心控制函数
def control_arm_joints(joint_angles: List[float], duration: float = None) -> bool
def control_arm_position(position: List[float], orientation: List[float] = None, duration: float = None) -> bool

# 预设动作函数
def execute_preset_action(action_name: str, speed: str = "normal") -> bool
```

## 使用方法

### 基本使用 (使用真实LLM)

```python
from embodied.hierarchical_decision_system import HierarchicalDecisionSystem

# 创建分层决策系统（使用真实LLM）
decision_system = HierarchicalDecisionSystem(
    use_llm=True, 
    provider="alibaba", 
    model="qwen-turbo"
)

# 执行用户指令
result = decision_system.execute_instruction("机械臂点头")

# 检查执行结果
if result['execution_result']['success']:
    print("指令执行成功")
else:
    print(f"执行失败: {result['execution_result']['error']}")
```

### 离线模式 (使用示例任务)

```python
# 创建分层决策系统（不使用LLM，用于测试）
decision_system = HierarchicalDecisionSystem(use_llm=False)

# 执行预定义的示例任务
result = decision_system.execute_instruction("关节角度设置为[0, 30, -45, 0, 15, 0]")
```

### 高级使用

```python
# 自定义LLM配置
decision_system = HierarchicalDecisionSystem(
    use_llm=True,
    provider="deepseek",  # 或其他提供商
    model="deepseek-chat"
)

# 获取支持的动作列表
actions = decision_system.get_available_actions()

# 直接调用底层函数
from embodied import embodied_func
success = embodied_func.control_arm_joints([0, 30, -45, 0, 15, 0], 2.0)
```

## JSON格式规范

系统使用统一的函数调用JSON格式：

### 基本格式
```json
{
  "function": "函数名",
  "parameters": {
    "参数名1": 参数值1,
    "参数名2": 参数值2
  }
}
```

### 关节角度控制
```json
{
  "function": "control_arm_joints",
  "parameters": {
    "joint_angles": [0, 30, -45, 0, 15, 0],
    "duration": 2.0
  }
}
```

### 末端位置控制
```json
{
  "function": "control_arm_position", 
  "parameters": {
    "position": [200, 100, 300],
    "orientation": [0, 0, 0],
    "duration": 3.0
  }
}
```

### 预设动作调用
```json
{
  "function": "execute_preset_action",
  "parameters": {
    "action_name": "点头",
    "speed": "normal"
  }
}
```

## 预设动作库

| 动作名称 | 关节角度 | 持续时间 |
|---------|----------|----------|
| 点头 | [0, 30, 0, 0, -30, 0] | 1.5s |
| 抬头 | [0, -30, 0, 0, 30, 0] | 1.5s |
| 摇头 | [30, 0, 0, 0, 0, 0] | 2.0s |
| 挥手 | [0, 0, 45, 0, 45, 90] | 2.0s |
| 招手 | [90, -30, 30, 0, 0, 0] | 1.8s |
| 初始位置 | [0, 0, 0, 0, 0, 0] | 2.0s |

## 测试运行

```bash
# 函数调用架构专用测试
python embodied/test_function_calling.py

# 快速测试（支持LLM和离线模式）
python embodied/quick_test.py

# 单独测试决策系统
python embodied/hierarchical_decision_system.py
```

## 新架构优势

### 相比原来的模式选择架构

**原架构**：用户指令 → LLM → 模式选择 → 模式处理器 → 函数调用
**新架构**：用户指令 → LLM → 函数选择 → 直接执行

### 主要改进

1. **更直接**：LLM直接选择具体函数，减少中间转换
2. **更灵活**：支持任意函数组合和参数传递
3. **更高效**：减少模式判断层，提高响应速度
4. **更易扩展**：添加新函数只需在embodied_func.py中定义

## LLM配置说明

### 支持的LLM提供商

系统使用项目的 `AI_SDK` 来调用LLM，支持以下提供商：

- **阿里云**: 通义千问系列模型
- **OpenAI**: GPT系列模型
- **DeepSeek**: DeepSeek系列模型
- **其他**: 根据 `AI_SDK` 配置添加

### LLM调用参数

- `temperature=0.3`: 低温度确保更准确的JSON生成
- `max_tokens=200`: 限制回复长度
- 自动JSON解析和错误处理

### 网络要求

- 使用LLM模式需要网络连接
- 如果网络不可用，系统会自动切换到离线示例模式
- 离线模式不需要网络连接，使用预定义的示例任务

## 扩展说明

### 添加新的预设动作

在 `PresetActionHandler` 类中的 `preset_actions` 字典中添加新动作：

```python
self.preset_actions = {
    "新动作名称": {"joints": [j1, j2, j3, j4, j5, j6], "duration": 时长},
    # ... 其他动作
}
```

### 集成真实LLM

```python
class YourLLMClient:
    def generate(self, prompt: str) -> str:
        # 实现与实际LLM的交互
        return response_json_string

# 使用自定义LLM
decision_system = HierarchicalDecisionSystem(llm_client=YourLLMClient())
```

### 添加新的处理模式

1. 创建新的处理器类
2. 在 `MiddleLevelTaskParser` 中注册
3. 在 `prompt.py` 中添加对应的JSON格式说明

## 注意事项

1. **安全性**：所有关节角度都会进行范围检查
2. **平滑性**：使用插补算法确保运动平滑
3. **错误处理**：所有函数都包含异常处理和错误信息返回

## 依赖关系

- `core.embodied_core.kinematics_control_core`：机械臂控制核心
- `core.mujoco_arm_controller`：MuJoCo仿真控制器
- `core.arm_core.kinematics`：运动学计算
- `core.arm_core.interpolation`：运动插补

## 许可证

本系统遵循项目整体许可证。 