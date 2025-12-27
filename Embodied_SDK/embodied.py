#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
具身智能 SDK 封装
================

目标：
- 将现有 `core.embodied_core.hierarchical_decision_system.HierarchicalDecisionSystem`
  以及 `embodied_func` 中的高层函数，封装为一个无界面依赖的 SDK；
- 对外提供**简单的自然语言接口**，用于一键触发理解指令  规划  执行动作。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from Horizon_Core import gateway as horizon_gateway


class EmbodiedSDK:
    """
    具身智能高层 SDK。

    - 内部直接使用现有的 HierarchicalDecisionSystem，不改动原有逻辑；
    - 面向 Web / ROS2 / Python 脚本等环境，提供统一的自然语言调用入口。
    """

    def __init__(
        self,
        *,
        provider: str = "alibaba",
        model: str = "qwen-turbo",
        control_mode: str = "real_only",
        config_path: Optional[str] = None,
    ) -> None:
        """
        Args:
            provider: LLM 提供商（与项目当前配置保持一致，如 "alibaba"）
            model:    LLM 模型名（如 "qwen-turbo"）
            control_mode: 控制模式 ("real_only" / "simulation_only" / "both")
            config_path: 可选 AISDK 配置文件路径
        """
        HDS_cls = horizon_gateway.get_hierarchical_decision_system_class()
        self._hds = HDS_cls(
            provider=provider,
            model=model,
            control_mode=control_mode,
            config_path=config_path,
        )

    # ------------------------------------------------------------------
    # 自然语言任务接口
    # ------------------------------------------------------------------

    def run_nl_instruction(self, instruction: str) -> Dict[str, Any]:
        """
        执行一条自然语言指令（完整的理解  规划  执行流程）。

        直接复用 `HierarchicalDecisionSystem.execute_instruction`。
        """
        return self._hds.execute_instruction(instruction)

    def run_nl_instruction_stream(
        self,
        instruction: str,
        *,
        action_handler=None,
        progress_handler=None,
        completion_handler=None,
    ) -> None:
        """
        以流式方式执行一条自然语言指令（直接转发 execute_instruction_stream）。

        说明：
        - action_handler(action_dict)      每解析到一个动作时回调；
        - progress_handler(message: str)   执行过程中的简单进度文案；
        - completion_handler(result: dict) 全部动作执行完后的最终结果。
        """
        self._hds.execute_instruction_stream(
            instruction,
            action_handler=action_handler,
            progress_handler=progress_handler,
            completion_handler=completion_handler,
        )

    def get_available_functions(self) -> Dict[str, str]:
        """
        查询当前系统支持的函数及其说明。
        """
        return self._hds.get_available_functions()

    def get_available_actions(self) -> Dict[str, List[str]]:
        """
        获取系统支持的动作列表（向后兼容接口，直接转发 HierarchicalDecisionSystem.get_available_actions）。
        """
        return self._hds.get_available_actions()

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------

    def clear_history(self) -> None:
        """清空具身智能对话/任务历史。"""
        self._hds.clear_history()

    def get_history(self) -> List[Dict[str, Any]]:
        """获取历史记录列表。"""
        return self._hds.get_history()

    def get_history_count(self) -> int:
        """获取历史记录条目数量。"""
        return self._hds.get_history_count()

    # ------------------------------------------------------------------
    # 兼容旧接口 & 深度控制接口（供 GUI 等高阶调用）
    # ------------------------------------------------------------------

    def execute_instruction(self, instruction: str) -> Dict[str, Any]:
        """
        兼容旧接口：直接转发到 HierarchicalDecisionSystem.execute_instruction。
        """
        return self._hds.execute_instruction(instruction)

    @property
    def high_level_planner(self) -> Any:
        """
        暴露内部的 HighLevelPlanner（只读属性，供流式/高级用法使用）。
        """
        return getattr(self._hds, "high_level_planner", None)

    @property
    def middle_level_parser(self) -> Any:
        """
        暴露内部的 MiddleLevelParser（只读属性，供单步动作执行等高级用法使用）。
        """
        return getattr(self._hds, "middle_level_parser", None)

    # ------------------------------------------------------------------
    # 全局紧急停止标志封装
    # ------------------------------------------------------------------

    def set_emergency_stop_flag(self, flag: bool) -> None:
        """
        设置全局紧急停止标志。

        Args:
            flag: True 表示触发紧急停止，False 表示清除紧急停止状态。
        """
        embodied_func = horizon_gateway.get_embodied_module()
        embodied_func.set_emergency_stop_flag(flag)

    def clear_emergency_stop_flag(self) -> None:
        """清除全局紧急停止标志（等价于 set_emergency_stop_flag(False)）。"""
        self.set_emergency_stop_flag(False)

    def emergency_stop(self) -> None:
        """触发全局紧急停止（等价于 set_emergency_stop_flag(True)）。"""
        self.set_emergency_stop_flag(True)

