#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
具身智能分层决策系统
实现高层任务规划、中层任务解析、底层功能执行的三层架构
"""

import sys
import os
import json
import time
from typing import Dict, List, Any, Optional, Union

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from .prompt import generate_task_planner_prompt
from . import embodied_func
from AI_SDK import AISDK


class HighLevelPlanner:
    """
    高层决策器：与LLM交互，进行任务规划
    支持传统模式和流式模式的统一接口
    """
    
    def __init__(self, provider="alibaba", model="qwen-turbo", config_path=None):
        """
        初始化高层决策器
        
        Args:
            provider: LLM提供商
            model: LLM模型名称
            config_path: 配置文件路径
        """
        self.provider = provider
        self.model = model
        self.last_llm_response = None  # 保存LLM的原始回复
        self.task_prompt = generate_task_planner_prompt("auto") # 生成任务规划提示词
        
        # 历史记录功能
        self.conversation_history = []  # 保存对话历史
        self.max_history = 20
        
        # 流式处理相关
        self.stream_buffer = ""  # 流式输出缓冲区
        self.current_full_response = ""  # 当前完整响应
        
        try:
            # 如果指定了配置文件路径，则使用指定路径
            if config_path:
                self.sdk = AISDK(config_path=config_path)
            else:
                self.sdk = AISDK()
        except Exception as e:
            print(f"❌ LLM连接失败: {e}")
            raise Exception(f"无法连接到LLM服务: {e}")
    
    def plan_task(self, user_instruction: str) -> Dict[str, Any]:
        """
        根据用户指令生成任务规划
        
        Args:
            user_instruction: 用户的自然语言指令
            
        Returns:
            dict: LLM返回的任务规划JSON，支持单个动作或动作序列
        """
        try:        
            # 获取历史记录上下文
            history_context = self.get_history_context()
            
            # 构建完整的prompt
            full_prompt = f"""
            {self.task_prompt}
            {history_context}

            用户指令: {user_instruction}

            """
            
            # 调用LLM
            response = self.sdk.chat(
                provider=self.provider,
                model=self.model,
                prompt=full_prompt,
                temperature=0.3,  # 低温度，更准确
                max_tokens=500    # 增加token限制以支持动作序列
            )
            
            # 提取LLM的回复内容
            llm_response = response['choices'][0]['message']['content']
            self.last_llm_response = llm_response  # 保存原始回复
            print(f"🤖 LLM原始回复: {llm_response}")
            
            # 尝试解析JSON
            try:
                # 清理回复中的多余内容，只保留JSON部分
                json_content = self._extract_json_from_response(llm_response)
                task_json = json.loads(json_content)
                print(f"✅ JSON解析成功: {task_json}")
                
                # 检查是单个动作还是动作序列
                if "sequence" in task_json:
                    # 动作序列格式
                    sequence = task_json["sequence"]
                    if not isinstance(sequence, list) or len(sequence) == 0:
                        raise Exception("动作序列格式错误：sequence必须是非空数组")
                    
                    # 验证序列中的每个动作
                    for i, action in enumerate(sequence):
                        if not isinstance(action, dict) or "func" not in action or "param" not in action:
                            raise Exception(f"动作序列第{i+1}个动作格式错误：必须包含func和param字段")
                    
                    print(f"📋 识别到动作序列，包含 {len(sequence)} 个动作")
                    
                    # 任务规划成功后，保存到历史记录
                    self.add_to_history(user_instruction, llm_response)
                    
                    return task_json
                    
                elif "func" in task_json and "param" in task_json:
                    # 单个动作格式（向后兼容）
                    print("📋 识别到单个动作")
                    
                    # 任务规划成功后，保存到历史记录
                    self.add_to_history(user_instruction, llm_response)
                    
                    return task_json
                    
                else:
                    raise Exception("JSON格式错误：必须包含'func'和'param'字段或'sequence'字段")
                    
            except json.JSONDecodeError as e:
                print(f"❌ JSON解析失败: {e}")
                print(f"❌ 原始回复: {llm_response}")
                raise Exception(f"LLM返回格式错误，无法解析JSON: {e}")
                
        except Exception as e:
            print(f"❌ LLM调用失败: {e}")
            raise Exception(f"LLM任务规划失败: {e}")
    
    def _extract_json_from_response(self, response: str) -> str:
        """
        从LLM回复中提取JSON部分
        
        Args:
            response: LLM的原始回复
            
        Returns:
            str: 提取的JSON字符串
        """
        # 查找JSON开始和结束的位置
        start_idx = response.find('{')
        end_idx = response.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            return response[start_idx:end_idx+1]
        else:
            # 如果没有找到完整的JSON，返回原始回复
            return response.strip()
    
    def add_to_history(self, user_instruction: str, ai_response: str):
        """
        添加对话到历史记录
        
        Args:
            user_instruction: 用户指令
            ai_response: AI回答
        """
        # 添加新的对话记录
        self.conversation_history.append({
            "user": user_instruction,
            "assistant": ai_response,
            "timestamp": time.time()
        })
        
        # 保持历史记录数量不超过最大值
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]
    
    def clear_history(self):
        """清空对话历史记录"""
        self.conversation_history = []
    
    def get_history_context(self) -> str:
        """
        获取历史记录的上下文字符串
        
        Returns:
            str: 格式化的历史记录上下文
        """
        if not self.conversation_history:
            return ""
        
        history_lines = ["历史对话记录:"]
        for i, record in enumerate(self.conversation_history, 1):
            history_lines.append(f"第{i}轮:")
            history_lines.append(f"用户: {record['user']}")
            history_lines.append(f"助手: {record['assistant']}")
            history_lines.append("")  # 空行分隔
        
        return "\n".join(history_lines)
    
    def plan_task_stream(self, user_instruction: str, 
                        action_callback=None, 
                        chunk_callback=None,
                        completion_callback=None) -> None:
        """
        流式任务规划 - 支持实时输出和动作解析
        
        Args:
            user_instruction: 用户的自然语言指令
            action_callback: 当解析到完整动作时的回调函数 func(action_dict)
            chunk_callback: 接收到流式chunk时的回调函数 func(chunk_text)
            completion_callback: 流式完成时的回调函数 func(full_response)
        """
        
        try:
            # 重置流式处理状态
            self.stream_buffer = ""
            self.current_full_response = ""
            
            # 获取历史记录上下文
            history_context = self.get_history_context()
            
            # 构建完整的prompt（与传统模式一致）
            full_prompt = f"""
            {self.task_prompt}
            {history_context}

            用户指令: {user_instruction}

            请注意：为了支持流式输出，请在每个动作周围加上<ACTION>和</ACTION>标签，格式如下：

            <ACTION>
            {{
            "func": "函数名",
            "param": {{
                "参数名1": 参数值1,
                "参数名2": 参数值2
            }}
            }}
            </ACTION>

            如果是动作序列，请为每个动作都加上<ACTION>标签。

            现在开始处理用户指令：
            """
            
            print(f"🌊 开始流式LLM调用: {self.provider}/{self.model}")
            
            # 流式调用LLM
            for chunk in self.sdk.chat(
                provider=self.provider,
                model=self.model,
                prompt=full_prompt,
                stream=True,
                temperature=0.3,  # 与传统模式一致
                max_tokens=1500
            ):
                # 获取流式内容
                content = chunk['choices'][0]['delta']['content']
                self.stream_buffer += content
                self.current_full_response += content
                
                # 如果有chunk回调，调用它
                if chunk_callback and content:
                    chunk_callback(content)
                
                # 尝试从缓冲区解析动作
                self._parse_actions_from_buffer(action_callback)
            
            # 处理最后的缓冲区内容
            self._parse_actions_from_buffer(action_callback, final=True)
            
            # 保存完整响应
            self.last_llm_response = self.current_full_response
            
            # 添加到历史记录
            if self.current_full_response.strip():
                self.add_to_history(user_instruction, self.current_full_response)
                print(f"✅ 流式任务规划完成，已保存到历史记录")
            
            # 调用完成回调
            if completion_callback:
                completion_callback(self.current_full_response)
                
        except Exception as e:
            print(f"❌ 流式LLM调用失败: {e}")
            raise Exception(f"流式任务规划失败: {e}")
    
    def _parse_actions_from_buffer(self, action_callback, final=False):
        """
        从缓冲区解析ACTION标签中的动作
        
        Args:
            action_callback: 动作回调函数
            final: 是否是最后一次解析
        """
        if not action_callback:
            return
            
        import re
        import json
        
        # 查找完整的ACTION标签
        action_pattern = r'<ACTION>(.*?)</ACTION>'
        matches = re.findall(action_pattern, self.stream_buffer, re.DOTALL)
        
        for match in matches:
            try:
                # 清理JSON字符串
                json_str = match.strip()
                if json_str.startswith('{') and json_str.endswith('}'):
                    action_data = json.loads(json_str)
                    
                    # 验证动作数据格式
                    if self._validate_action(action_data):
                        # 调用动作回调
                        action_callback(action_data)
                        print(f"🎯 解析到动作: {action_data.get('func', '未知')}")
                    
            except json.JSONDecodeError as e:
                if final:
                    print(f"⚠️ JSON解析失败: {e}")
                # 非最终解析时忽略错误，可能数据不完整
                continue
        
        # 清理已处理的ACTION标签
        for match in matches:
            self.stream_buffer = self.stream_buffer.replace(f"<ACTION>{match}</ACTION>", "", 1)
    
    def _validate_action(self, action_data: dict) -> bool:
        """
        验证动作数据格式
        
        Args:
            action_data: 动作数据字典
            
        Returns:
            bool: 是否有效
        """
        required_fields = ['func', 'param']
        return all(field in action_data for field in required_fields)


class MiddleLevelTaskParser:
    """
    中层任务解析器：解析LLM返回的函数调用JSON，直接执行对应函数
    """
    
    def __init__(self, control_mode="real_only"):
        """
        初始化中层任务解析器
        
        Args:
            control_mode: 控制模式 ("real_only", "simulation_only", "both")
        """
        self.control_mode = control_mode
        
        # 根据控制模式导入相应的函数模块
        if control_mode == "real_only":
            from . import embodied_func
            self.real_func = embodied_func
            self.mujoco_func = None
            print("🎯 中层解析器: 仅使用真实机械臂控制")
            
        elif control_mode == "simulation_only":
            from . import embodied_mujoco_func
            self.real_func = None
            self.mujoco_func = embodied_mujoco_func
            print("🎮 中层解析器: 仅使用MuJoCo仿真控制")
            
        elif control_mode == "both":
            from . import embodied_func
            from . import embodied_mujoco_func
            self.real_func = embodied_func
            self.mujoco_func = embodied_mujoco_func
            print("🎯🎮 中层解析器: 同时使用真实机械臂和MuJoCo仿真")
            
        else:
            raise ValueError(f"不支持的控制模式: {control_mode}")
    
    def parse_and_execute(self, function_call_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析函数调用JSON并执行对应函数，支持单个动作和动作序列
        
        Args:
            function_call_json: 高层决策器返回的函数调用JSON
            
        Returns:
            dict: 执行结果，包含序列执行的详细信息
        """
        if "error" in function_call_json:
            return {"success": False, "error": function_call_json["error"]}
        
        # 检查是单个动作还是动作序列
        if "sequence" in function_call_json:
            # 动作序列执行
            return self._execute_action_sequence(function_call_json["sequence"])
        elif "func" in function_call_json and "param" in function_call_json:
            # 单个动作执行（向后兼容）
            function_name = function_call_json.get("func", "")
            parameters = function_call_json.get("param", {})
            return self._execute_single_action(function_name, parameters)
        else:
            return {"success": False, "error": "JSON格式错误：缺少必要字段"}
    
    def _execute_action_sequence(self, action_sequence: list) -> Dict[str, Any]:
        """
        执行动作序列（基于实际到位检测）
        
        Args:
            action_sequence: 动作序列列表
            
        Returns:
            dict: 序列执行结果
        """
        total_actions = len(action_sequence)
        print(f"🎯 开始执行动作序列，共 {total_actions} 个动作（基于实际到位检测）")
        
        sequence_results = []
        overall_success = True
        executed_count = 0
        
        for i, action in enumerate(action_sequence):
            action_index = i + 1
            function_name = action.get("func", "")
            parameters = action.get("param", {})
            
            print(f"\n📋 [{action_index}/{total_actions}] 执行动作: {function_name}")
            print(f"📋 动作参数: {parameters}")
            
            # 执行单个动作（函数内部会等待到位）
            action_result = self._execute_single_action(function_name, parameters)
            action_result["action_index"] = action_index
            action_result["total_actions"] = total_actions
            sequence_results.append(action_result)
            executed_count += 1
            
            if action_result["success"]:
                print(f"✅ [{action_index}/{total_actions}] 动作执行完成并到位")
            else:
                print(f"❌ [{action_index}/{total_actions}] 动作执行失败: {action_result.get('error', '未知错误')}")
                overall_success = False
                # 如果某个动作失败，停止执行后续动作
                print(f"⚠️ 由于动作失败，停止执行剩余 {total_actions - executed_count} 个动作")
                break
            
            # 动作完成后立即开始下一个（基于实际到位检测，无需额外等待）
            if action_index < total_actions:
                print(f"➡️ [{action_index}/{total_actions}] 动作已到位，立即开始下一动作")
        
        # 构建序列执行结果
        result = {
            "success": overall_success,
            "sequence_type": "action_sequence",
            "total_actions": total_actions,
            "executed_actions": executed_count,
            "sequence_results": sequence_results,
            "message": f"动作序列{'执行完成' if overall_success else '执行失败'}，完成 {executed_count}/{total_actions} 个动作"
        }
        
        print(f"\n🎯 动作序列{'执行完成' if overall_success else '执行失败'}：{executed_count}/{total_actions}")
        return result
    
    def _execute_single_action(self, function_name: str, parameters: dict) -> Dict[str, Any]:
        """
        执行单个动作
        
        Args:
            function_name: 函数名
            parameters: 函数参数
            
        Returns:
            dict: 单个动作执行结果
        """
        print(f"🎯 中层解析器收到函数调用: {function_name}")
        print(f"📋 函数参数: {parameters}")
        
        try:
            results = {}
            overall_success = False
            
            # 根据控制模式执行函数
            if self.control_mode == "real_only" and self.real_func:
                success = self._execute_function(self.real_func, function_name, parameters, "真实机械臂")
                results["real_arm"] = success
                overall_success = success
                
            elif self.control_mode == "simulation_only" and self.mujoco_func:
                success = self._execute_function(self.mujoco_func, function_name, parameters, "MuJoCo仿真")
                results["simulation"] = success
                overall_success = success
                
            elif self.control_mode == "both":
                # 同时控制模式
                real_success = False
                sim_success = False
                
                if self.real_func:
                    real_success = self._execute_function(self.real_func, function_name, parameters, "真实机械臂")
                    results["real_arm"] = real_success
                
                if self.mujoco_func:
                    sim_success = self._execute_function(self.mujoco_func, function_name, parameters, "MuJoCo仿真")
                    results["simulation"] = sim_success
                
                # 同时控制模式下，只要真实机械臂成功就算成功
                overall_success = real_success
                
                if real_success and sim_success:
                    print("✅ 真实机械臂和MuJoCo仿真都执行成功")
                elif real_success:
                    print("✅ 真实机械臂执行成功，MuJoCo仿真执行失败")
                elif sim_success:
                    print("⚠️ MuJoCo仿真执行成功，但真实机械臂执行失败")
                else:
                    print("❌ 真实机械臂和MuJoCo仿真都执行失败")
            
            return {
                "success": overall_success,
                "func": function_name,
                "param": parameters,
                "results": results,
                "message": f"函数 {function_name} 在{self._get_mode_text()}执行{'成功' if overall_success else '失败'}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "func": function_name,
                "param": parameters,
                "error": f"函数执行异常: {str(e)}"
            }
    
    def _execute_function(self, func_module, function_name, parameters, target_name):
        """
        执行单个函数模块中的函数
        
        Args:
            func_module: 函数模块
            function_name: 函数名
            parameters: 函数参数
            target_name: 目标名称（用于日志）
            
        Returns:
            bool: 执行是否成功
        """
        try:
            # 检查函数是否存在
            if not hasattr(func_module, function_name):
                print(f"❌ {target_name}: 未找到函数 {function_name}")
                return False
            
            # 获取函数对象
            func = getattr(func_module, function_name)
            
            # 调用函数
            print(f"🚀 执行{target_name}函数: {function_name}({parameters})")
            success = func(**parameters)
            
            if success:
                print(f"✅ {target_name}: 函数 {function_name} 执行成功")
            else:
                print(f"❌ {target_name}: 函数 {function_name} 执行失败")
                
            return success
            
        except TypeError as e:
            print(f"❌ {target_name}: 函数参数错误 - {str(e)}")
            return False
        except Exception as e:
            print(f"❌ {target_name}: 函数执行异常 - {str(e)}")
            return False
    
    def _get_mode_text(self):
        """获取控制模式的中文描述"""
        mode_map = {
            "real_only": "真实机械臂",
            "simulation_only": "MuJoCo仿真",
            "both": "真实机械臂和仿真"
        }
        return mode_map.get(self.control_mode, "未知模式")


class HierarchicalDecisionSystem:
    """
    分层决策系统主控制器
    整合高层、中层、底层的完整决策流程
    """
    
    def __init__(self, provider="alibaba", model="qwen-turbo", control_mode="real_only", config_path=None):
        """
        初始化分层决策系统
        
        Args:
            provider: LLM提供商
            model: LLM模型名称
            control_mode: 控制模式 ("real_only", "simulation_only", "both")
            config_path: 配置文件路径
        """
        self.control_mode = control_mode
        self.high_level_planner = HighLevelPlanner(provider=provider, model=model, config_path=config_path)
        self.middle_level_parser = MiddleLevelTaskParser(control_mode=control_mode)
        
    
    def _get_mode_description(self, mode):
        """获取控制模式描述"""
        mode_map = {
            "real_only": "仅真实机械臂",
            "simulation_only": "仅MuJoCo仿真", 
            "both": "同时控制真实机械臂和仿真"
        }
        return mode_map.get(mode, "未知模式")
    
    def execute_instruction(self, user_instruction: str) -> Dict[str, Any]:
        """
        执行用户指令的完整流程，支持单个动作和动作序列
        
        Args:
            user_instruction: 用户的自然语言指令
            
        Returns:
            dict: 完整的执行结果，包含序列执行的详细信息
        """
        print(f"\n🎯 接收用户指令: {user_instruction}")
        print("=" * 50)
        
        try:
            # 高层决策：任务规划
            print("📊 [高层] 开始任务规划...")
            task_plan = self.high_level_planner.plan_task(user_instruction)
            print(f"📊 [高层] 任务规划完成")
            
            # 检查是单个动作还是动作序列
            if "sequence" in task_plan:
                print(f"📊 [高层] 规划类型: 动作序列 ({len(task_plan['sequence'])} 个动作)")
            else:
                print(f"📊 [高层] 规划类型: 单个动作 ({task_plan.get('func', '未知')})")
            
            # 中层解析：任务分发
            print("\n⚙️ [中层] 开始任务解析和分发...")
            execution_result = self.middle_level_parser.parse_and_execute(task_plan)
            print(f"⚙️ [中层] 任务分发完成")
            
            # 整合结果
            final_result = {
                "user_instruction": user_instruction,
                "task_plan": task_plan,
                "execution_result": execution_result,
                "llm_response": getattr(self.high_level_planner, 'last_llm_response', None),
                "timestamp": time.time()
            }
            
            # 显示执行结果摘要
            if execution_result.get('sequence_type') == 'action_sequence':
                # 动作序列结果
                total_actions = execution_result.get('total_actions', 0)
                executed_actions = execution_result.get('executed_actions', 0)
                success = execution_result.get('success', False)
                
                print(f"\n✅ [系统] 动作序列执行完成")
                print(f"📊 [系统] 序列状态: {'全部完成' if success else '部分失败'}")
                print(f"📊 [系统] 完成进度: {executed_actions}/{total_actions} 个动作")
                print(f"🎯 [系统] 采用实际到位检测，确保动作精确完成")
                
                if execution_result.get('message'):
                    print(f"📝 [系统] 序列信息: {execution_result['message']}")
            else:
                # 单个动作结果
                success = execution_result.get('success', False)
                print(f"\n✅ [系统] 指令执行完成，成功: {success}")
                if execution_result.get('message'):
                    print(f"📝 [系统] 执行信息: {execution_result['message']}")
                if execution_result.get('error'):
                    print(f"❌ [系统] 错误信息: {execution_result['error']}")
            
            print("=" * 50)
            return final_result
            
        except Exception as e:
            # 如果高层决策失败，返回错误结果
            error_result = {
                "user_instruction": user_instruction,
                "task_plan": {"error": str(e)},
                "execution_result": {"success": False, "error": str(e)},
                "llm_response": getattr(self.high_level_planner, 'last_llm_response', None),
                "timestamp": time.time()
            }
            
            print(f"\n❌ [系统] 指令执行失败: {str(e)}")
            print("=" * 50)
            return error_result
    
    def get_available_functions(self) -> Dict[str, str]:
        """
        获取系统支持的所有函数
        
        Returns:
            dict: 函数名和函数描述的字典
        """
        from .prompt import discover_embodied_functions
        return discover_embodied_functions()
    
    # 保持向后兼容
    def get_available_actions(self) -> Dict[str, List[str]]:
        """
        获取系统支持的所有动作（向后兼容）
        
        Returns:
            dict: 各模式支持的动作列表
        """
        functions = self.get_available_functions()
        return {
            "available_functions": list(functions.keys())
        }
    
    # 历史记录管理方法
    def clear_history(self):
        """清空对话历史记录"""
        self.high_level_planner.clear_history()
    
    def get_history(self) -> List[Dict[str, Any]]:
        """获取对话历史记录列表"""
        return self.high_level_planner.conversation_history
    
    def get_history_count(self) -> int:
        """获取历史记录数量"""
        return len(self.high_level_planner.conversation_history)
    
    def execute_instruction_stream(self, user_instruction: str, 
                                  action_handler=None,
                                  progress_handler=None,
                                  completion_handler=None) -> None:
        """
        流式执行用户指令 - 支持实时动作执行
        
        Args:
            user_instruction: 用户的自然语言指令
            action_handler: 处理单个动作的函数 func(action_dict) -> result_dict
            progress_handler: 进度更新函数 func(message)
            completion_handler: 完成时的回调函数 func(results)
        """
        print(f"\n🌊 [流式] 接收用户指令: {user_instruction}")
        print("=" * 50)
        
        # 动作执行结果收集
        action_results = []
        action_counter = 0
        
        def on_action_parsed(action_data):
            """当解析到新动作时的回调"""
            nonlocal action_counter
            action_counter += 1
            
            # 添加序号信息
            action_data['_sequence_number'] = action_counter
            
            print(f"\n📋 [流式] 解析到动作 #{action_counter}: {action_data.get('func', '未知')}")
            print(f"📋 [流式] 动作参数: {action_data.get('param', {})}")
            
            # 执行动作
            if action_handler:
                result = action_handler(action_data)
            else:
                # 如果没有提供handler，使用中层解析器执行
                result = self.middle_level_parser._execute_single_action(
                    action_data.get('func', ''),
                    action_data.get('param', {})
                )
            
            # 记录结果
            action_results.append({
                'action': action_data,
                'result': result,
                'sequence_number': action_counter
            })
            
            # 进度更新
            if progress_handler:
                if result.get('success'):
                    progress_handler(f"✅ 动作 #{action_counter} 执行成功")
                else:
                    progress_handler(f"❌ 动作 #{action_counter} 执行失败: {result.get('error', '未知错误')}")
        
        def on_chunk_received(chunk):
            """接收到流式chunk时的回调（可选）"""
            # 可以用于显示实时输出，这里暂不处理
            pass
        
        def on_stream_complete(full_response):
            """流式完成时的回调"""
            print(f"\n✅ [流式] 执行完成")
            print(f"📊 [流式] 共执行 {action_counter} 个动作")
            print(f"📝 [流式] AI完整响应长度: {len(full_response)} 字符")
            print("=" * 50)
            
            # 构建最终结果
            final_result = {
                'user_instruction': user_instruction,
                'total_actions': action_counter,
                'action_results': action_results,
                'llm_response': full_response,
                'success': all(r['result'].get('success', False) for r in action_results) if action_results else True,
                'timestamp': time.time()
            }
            
            # 调用完成handler
            if completion_handler:
                completion_handler(final_result)
        
        try:
            # 调用高层决策器的流式方法
            self.high_level_planner.plan_task_stream(
                user_instruction=user_instruction,
                action_callback=on_action_parsed,
                chunk_callback=on_chunk_received,
                completion_callback=on_stream_complete
            )
            
        except Exception as e:
            error_msg = f"流式执行失败: {str(e)}"
            print(f"\n❌ [流式] {error_msg}")
            print("=" * 50)
            
            # 错误时也调用完成handler
            if completion_handler:
                completion_handler({
                    'user_instruction': user_instruction,
                    'total_actions': action_counter,
                    'action_results': action_results,
                    'error': error_msg,
                    'success': False,
                    'timestamp': time.time()
                })


# 使用示例
if __name__ == "__main__":
    # 创建分层决策系统（使用真实LLM）
    print("🚀 启动分层决策系统（使用真实LLM）")
    decision_system = HierarchicalDecisionSystem(provider="alibaba", model="qwen-turbo")
    
    try:
        # 测试关节角度控制
        test_instruction = "关节角度设置为[0, 30, -45, 0, 15, 0]"
        print(f"\n📝 测试指令: {test_instruction}")
        
        result = decision_system.execute_instruction(test_instruction)
        
        if result['execution_result']['success']:
            print("✅ 系统运行正常")
        else:
            print(f"❌ 系统运行异常: {result['execution_result'].get('error', '未知错误')}")
        
        print("\n📋 系统支持的函数:")
        functions = decision_system.get_available_functions()
        for func_name, func_doc in functions.items():
            # 只显示函数名和第一行描述
            first_line = func_doc.split('\n')[0] if func_doc else "无描述"
            print(f"  {func_name}: {first_line}")
    
    except Exception as e:
        print(f"❌ 系统初始化或运行失败: {e}")
    
    finally:
        # 清理资源，避免线程问题
        print("\n🧹 正在清理系统资源...")
        try:
            controller = embodied_func._get_controller()
            if controller and hasattr(controller, 'controller'):
                if hasattr(controller.controller, 'stop_viewer'):
                    controller.controller.stop_viewer()
                    print("✅ MuJoCo viewer已停止")
            embodied_func._arm_controller = None
            print("✅ 资源清理完成")
        except Exception as e:
            print(f"⚠️ 清理过程中出现错误: {e}") 