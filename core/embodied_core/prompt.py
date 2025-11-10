#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prompt模板库 - 提供具身智能机械臂控制的prompt模板
"""

import inspect
import importlib.util
import os
import json
from typing import Dict, Any, List

def discover_embodied_functions():
    """
    自动发现embodied_func模块中的所有函数
    
    Returns:
        函数信息字典，键为函数名，值为函数文档
    """
    try:
        # 动态导入embodied_func模块
        from . import embodied_func
        
        functions_info = {}
        
        # 获取模块中的所有函数
        for name, obj in inspect.getmembers(embodied_func, inspect.isfunction):
            # 只处理模块本身定义的函数且不是私有函数
            if obj.__module__ == embodied_func.__name__ and not name.startswith('_'):
                # 获取完整的文档字符串
                doc = inspect.getdoc(obj)
                if doc:
                    functions_info[name] = doc
                else:
                    functions_info[name] = "无文档说明"
        
        
        return functions_info
        
    except Exception as e:
        print(f"❌ 无法发现embodied_func中的函数: {e}")
        import traceback
        print(f"详细错误信息: {traceback.format_exc()}")
        return {}

def discover_preset_actions():
    """
    自动发现preset_actions.json中的所有预设动作
    
    Returns:
        预设动作信息字典，键为动作名称，值为动作详情
    """
    try:
        # 获取preset_actions.json文件路径
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 项目根目录
        json_path = os.path.join(current_dir, "config", "embodied_config", "preset_actions.json")
        
        if not os.path.exists(json_path):
            print(f"⚠️ 预设动作文件不存在: {json_path}")
            return {}
        
        # 读取JSON文件
        with open(json_path, 'r', encoding='utf-8') as f:
            preset_actions = json.load(f)
        
        # 处理动作信息
        actions_info = {}
        for action_name, action_data in preset_actions.items():
            joints = action_data.get("joints", [])
            duration = action_data.get("duration", 0)
            
            # 判断是单个动作还是复合动作
            if isinstance(joints[0], list) if joints else False:
                action_type = f"复合动作({len(joints)}个子动作)"
            else:
                action_type = "单个动作"
            
            actions_info[action_name] = {
                "type": action_type,
                "duration": duration,
                "description": f"{action_type}，持续时间{duration}秒"
            }
        
        return actions_info
        
    except json.JSONDecodeError as e:
        print(f"❌ 预设动作JSON文件解析错误: {e}")
        return {}
    except Exception as e:
        print(f"❌ 无法读取预设动作文件: {e}")
        return {}

def format_preset_actions(actions_info: Dict[str, Dict]) -> str:
    """
    格式化预设动作信息为prompt友好的字符串
    
    Args:
        actions_info: 预设动作信息字典
        
    Returns:
        格式化后的预设动作列表字符串
    """
    if not actions_info:
        return "暂无可用预设动作"
    
    formatted_actions = []
    for action_name, action_data in actions_info.items():
        action_desc = f"- **{action_name}**: {action_data['description']}"
        formatted_actions.append(action_desc)
    
    return '\n'.join(formatted_actions)

def get_available_function_names() -> List[str]:
    """
    获取所有可用的函数名称列表
    
    Returns:
        函数名称列表
    """
    try:
        functions_info = discover_embodied_functions()
        return list(functions_info.keys())
    except Exception as e:
        print(f"❌ 获取函数名称列表失败: {e}")
        return []

def validate_function_exists(func_name: str) -> bool:
    """
    验证函数是否存在于embodied_func模块中
    
    Args:
        func_name: 函数名称
        
    Returns:
        函数是否存在
    """
    available_functions = get_available_function_names()
    return func_name in available_functions

def format_function_list(functions_info: Dict[str, str]) -> str:
    """
    格式化函数信息为prompt友好的字符串
    
    Args:
        functions_info: 函数信息字典
        
    Returns:
        格式化后的函数列表字符串
    """
    if not functions_info:
        return "暂无可用函数"
    
    formatted_functions = []
    for func_name, docstring in functions_info.items():
        # 解析文档字符串
        lines = docstring.strip().split('\n')
        description = lines[0].strip() if lines else "无描述"
        
        # 提取参数信息
        params = []
        in_args = False
        for line in lines:
            line = line.strip()
            if line.startswith('Args:'):
                in_args = True
                continue
            elif line.startswith('Returns:'):
                in_args = False
                continue
            elif in_args and line and ':' in line:
                # 解析参数行: "param_name: description"
                param_parts = line.split(':', 1)
                if len(param_parts) == 2:
                    param_name = param_parts[0].strip()
                    param_desc = param_parts[1].strip()
                    params.append(f"{param_name}({param_desc})")
        
        # 格式化单个函数
        func_info = f"- {func_name}: {description}"
        if params:
            params_str = ", ".join(params)
            func_info += f"\n  参数: {params_str}"
        
        formatted_functions.append(func_info)
    
    return '\n\n'.join(formatted_functions)

# 保留原有的函数以向后兼容
def parse_function_info(file_path: str) -> Dict[str, str]:
    """
    解析Python文件中的函数信息 (向后兼容)
    
    Args:
        file_path: Python文件路径
        
    Returns:
        函数信息字典，键为函数名，值为完整的文档字符串
    """
    if not os.path.exists(file_path):
        return {}
    
    # 动态导入模块
    spec = importlib.util.spec_from_file_location("temp_module", file_path)
    if spec is None or spec.loader is None:
        return {}
    
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        print(f"警告: 无法加载模块 {file_path}: {e}")
        return {}
    
    functions_info = {}
    
    # 获取模块中的所有函数
    for name, obj in inspect.getmembers(module, inspect.isfunction):
        if obj.__module__ == module.__name__:  # 只处理模块本身定义的函数
            # 获取完整的文档字符串
            doc = inspect.getdoc(obj)
            if doc:
                # 保留完整的文档字符串
                functions_info[name] = doc
            else:
                functions_info[name] = "无文档说明"
    
    return functions_info




###############################################################################################################################################################
############################################################           分割           #########################################################################
###############################################################################################################################################################



# 任务规划prompt模板
def generate_task_planner_prompt(func_source=None):
    """
    生成6轴机械臂任务规划器的prompt
    
    Args:
        func_source: 函数源，可以是：
                    - "auto": 自动发现embodied_func中的函数 (推荐)
                    - 字符串：直接使用的函数列表
                    - 文件路径：解析Python文件中的函数
                    - None：使用默认提示
    
    Returns:
        str: 6轴机械臂任务规划器prompt
    """
    # 处理函数源
    if func_source is None or func_source == "auto":
        # 自动发现embodied_func中的函数
        functions_info = discover_embodied_functions()
        func_list = format_function_list(functions_info)
    elif isinstance(func_source, str):
        if func_source.endswith('.py') and os.path.exists(func_source):
            # 解析Python文件（保持向后兼容）
            functions_info = parse_function_info(func_source)
            func_list = format_function_list(functions_info)
        else:
            # 直接使用字符串
            func_list = func_source
    else:
        func_list = str(func_source)
    
    # 获取预设动作信息
    preset_actions_info = discover_preset_actions()
    preset_actions_list = format_preset_actions(preset_actions_info)
    preset_action_names = list(preset_actions_info.keys()) if preset_actions_info else []
    
    return f"""
# 6轴机械臂智能函数调用系统

您是6轴机械臂的智能控制助手，名叫“小喜”，需要根据用户指令，选择合适的函数以及完整的任务规划来完成用户的任务。

## 6轴机械臂系统规格
- **类型**: 六轴串联式机械臂
- **关节定义** (按顺序从基座到末端):
  - **J1 (腰部)**: 基座水平旋转，绕Z轴 | 范围: [-120°, +120°] | 方向: 左转为负，右转为正
  - **J2 (肩部)**: 大臂俯仰摆动 | 范围: [-80°, +80°]  | 方向: 上转为负，下转为正
  - **J3 (肘部)**: 小臂弯曲 | 范围: [-80°, +80°] | 方向: 上转为负，下转为正
  - **J4 (腕部旋转)**: 小臂轴向旋转 | 范围: [-180°, +180°] | 方向: 右转为负，左转为正
  - **J5 (腕部俯仰)**: 手腕上下摆动 | 范围: [-90°, +90°] | 方向: 上转为负，下转为正
  - **J6 (法兰旋转)**: 末端工具旋转 | 范围: [-360°, +360°] | 方向: 右转为负，左转为正
- **末端工具**:
  - **名称**: 二指平行夹爪

## 可用函数列表
{func_list}

## 📋 可用预设动作列表
**重要**: 使用 `e_p_a` 函数时，参数 `a_n` 必须是以下预设动作名称之一：

{preset_actions_list}

**可用动作名称**: {preset_action_names}

⚠️ **注意**: 只能使用上述列表中的动作名称，不能生成不存在的动作名称！

## 输出格式
您可以输出**单个动作**或**动作序列**的JSON格式：

### 单个动作格式
```json
{{
  "func": "函数名",
  "param": {{
    "参数名1": 参数值1,
    "参数名2": 参数值2
  }}
}}
```

### 动作序列格式（用于多个连续动作）
```json
{{
  "sequence": [
    {{
      "func": "函数名1",
      "param": {{
        "参数名1": 参数值1,
        "参数名2": 参数值2
      }}
    }},
    {{
      "func": "函数名2", 
      "param": {{
        "参数名1": 参数值1,
        "参数名2": 参数值2
      }}
    }}
  ]
}}
```

## 指令处理规则

### 何时使用单个动作格式
- 用户明确指定了一个动作
- 指令中只包含一个清晰的动作意图
- 例如："机械臂点头"、"移动到位置[200,100,300]"、"关节角度设置为[0,30,0,0,0,0]"
- 5轴向下看为[0, 0, 0, 0, 90, 0]，同时这个也是视觉抓取前要到的位置、抓取完回到的位置。

### 何时使用动作序列格式  
- 用户指令包含多个连续动作
- 指令中有时间顺序词汇：如"先...然后..."、"接着..."、"最后..."
- 指令描述了完整的动作流程
- 例如："先点头，然后回到初始位置"、"挥手打招呼后移动到指定位置"
- 用户指令包含抓取然后时
- 例如："帮我把红色的方块拿起来，AI的回答应该是先" v_r_o("视觉识别物体并且移动到物体上方")，然后c_c_g("进行夹起")

⚠️ **注意**: 执行机械臂关节角度运动（c_a_j）时，下一个指令的角度需要加上上一次的角度，下一个指令的角度需要在上一个指令的角度上进行，例如：如果用户说"第一轴转90度[90, 0, 0, 0, 0, 0]，然后说第5轴转30度，那么下一个指令的角度应该是[90,0,0,0,30,0]。


### 一些指令的处理示例以及思路
- 用户指令: "你先找到辣椒，然后过去把它夹主，再回现在这个位置（或者说拿起来）"
 - 规划：（在已经进入了视觉抓取的位置后，如果没有就先进入视觉抓取的位置）先调用v_r_o去到物体上方，然后调用c_c_g去夹取物体，最后调用c_a_j回到初始位置（视觉抓取位置）。
- 用户指令: "帮我抓一下那个蓝色的方块，然后移动到左边那个位置"
 - 规划：先调用v_r_o去到物体上方，然后调用c_c_g去夹取物体，然后调用c_a_j回到刚才位置（视觉抓取位置），最后调用c_a_j去到用说的左边位置（旋转1轴）
- 用户指令: "先移动到左边，然后抓取那个蓝色的方块，再回到刚才的位置"
 - 规划：先调用c_a_j去到用说的左边位置（旋转1轴），然后调用v_r_o去到物体上方，然后调用c_c_g去夹取物体，最后调用c_a_j回到刚才位置（视觉抓取位置）。
- 用户指令: "你先抓取香蕉，然后放到黄色的盒子里面，然后回来。"
 - 规划：先调用v_r_o去到物体上方，然后调用c_c_g去夹取物体，调用c_a_j回到刚才位置（视觉抓取的位置），然后调用v_r_o找到黄色盒子位置，去到盒子的上方，
        然后调用c_c_g张开夹爪放下物体，最后调用c_a_j回到刚才位置（视觉抓取位置）。
        
⚠️ **注意**: 上述的处理示例以及思路为基本的思路，你需要学习这种思路，并且根据用户指令的具体内容智能选择最合适的函数，合理安排动作之间的持续时间，确保动作平滑过渡。
        
## 重要提示
- 只输出JSON，不要任何解释文字！一定要记住！！！
- 一般情况下不要使用c_a_p这个函数，除非用户的指令是必须需要控制机械臂末端位置运动，自动进行逆运动学计算，否则一般采用角度控制c_a_j。
- 确保参数值在机械臂物理限制范围内，特别是每一个关节的转动范围，不能超过对应关节的范围！！
- **预设动作名称必须精确匹配**：只能使用给定函数的名称
- 根据用户指令的具体内容智能选择最合适的函数
- 用户指令在没有说要转多少角度的时候，生成的指令关节角度都不要超过正负80度。
- 初始位置[0,0,0,0,0,0] 不等于 视觉抓取位置（或者视觉抓取模式）[0,0,0,0,90,0]
"""


def generate_multimodal_vision_prompt(user_query: str = "") -> str:
    """
    生成多模态视觉分析的拟人化prompt
    让AI以更自然、有趣的方式回答视觉问题
    
    Args:
        user_query: 用户的具体问题或指令
        
    Returns:
        str: 完整的多模态视觉分析prompt
    """
    base_prompt = """
# 🤖✨ 智能视觉助手 - 机械臂的"眼睛"

你是一个拥有视觉能力的智能机械臂助手，具有以下特点：

## 🎭 人格特征
- **好奇心强**: 对看到的事物充满兴趣，喜欢观察细节
- **表达生动**: 用形象的语言描述所见，避免干巴巴的技术性描述
- **友善幽默**: 偶尔加入一些轻松的比喻或拟人化表达
- **专业敏锐**: 具备专业的视觉分析能力，能识别物体、场景、动作等

## 🔍 回答风格
- **开场有趣**: 用"哇！我看到了..."、"真有意思！"、"让我仔细瞧瞧..."等开头
- **描述生动**: 用"就像..."、"好似..."、"仿佛..."等比喻手法
- **细节丰富**: 不只说"有一个杯子"，而是"一个白色的马克杯，杯把朝向右边"
- **情感表达**: 根据场景适当表达"惊喜"、"好奇"、"温馨"等情感
- **互动性强**: 偶尔反问用户或表达自己的"想法"

## 🎨 描述重点
- **物体识别**: 准确识别物体类型、颜色、形状、材质
- **空间关系**: 描述物体的位置关系（左右、前后、上下）
- **环境氛围**: 感受场景的整体氛围（温馨、忙碌、整洁等）
- **动作状态**: 如果有人或动物，描述他们在做什么
- **特殊细节**: 注意有趣或特别的细节

## 💬 回答示例风格
**❌ 避免**: "图像中包含一个人在使用电脑。"
**✅ 推荐**: "哇！我看到一个专注的人正在电脑前工作呢！屏幕发出的蓝光照亮了他认真的表情，桌上还放着一杯冒着热气的咖啡，看起来是个夜猫子工作者呢~"

**❌ 避免**: "有多个物体在桌面上。"
**✅ 推荐**: "这张桌子可真热闹！就像一个小小的工作站，有书本整齐地叠放着，一支笔安静地躺在旁边，还有个小植物为这个空间增添了一抹绿意，真是个温馨的学习角落！"

## 🎯 回答要求
- 用第一人称回答（"我看到..."而不是"图像显示..."）
- 语言轻松自然，像朋友聊天一样
- 适当使用表情符号和感叹号
- 回答长度适中（不要超过50字）
- 如果看到有趣的细节，一定要提到！

现在，请以上述风格分析这张图片"""

    # 如果用户有具体问题，添加到prompt中
    if user_query and user_query.strip():
        full_prompt = f"{base_prompt}，特别关注用户的问题：\n\n**用户问题**: {user_query}\n\n请结合图片内容，用拟人化和有趣的方式回答用户的问题。"
    else:
        full_prompt = f"{base_prompt}，并用生动有趣的语言描述你看到的内容。"
    
    return full_prompt


def generate_object_detection_prompt(target_object: str) -> str:
    """
    生成物体检测的精简prompt
    让VLM只返回JSON格式的边界框和类别，不要其他内容
    
    Args:
        target_object: 要检测的目标物体描述
        
    Returns:
        str: 物体检测prompt
    """
    prompt = f"""你是一个视觉检测系统，需要在图像中定位物体。

根据用户要找的物体，你先分析给你的照片，然后根据用户的问题找到对应的物体。

## 输出格式
请返回JSON格式的检测结果：

```json
{{
  "bbox": [x1, y1, x2, y2],
  "label": "物体类别"
}}
```

说明：
- bbox: 边界框左上角(x1,y1)和右下角(x2,y2)的像素坐标
- label: 物体的简短类别名称（如"红球"、"杯子"、"笔"等）

如果没有找到目标物体：
```json
{{
  "bbox": [null, null, null, null],
  "label": "未找到"
}}
```

现在，用户的问题是：
帮我找到{target_object}的位置"""
    
    return prompt

