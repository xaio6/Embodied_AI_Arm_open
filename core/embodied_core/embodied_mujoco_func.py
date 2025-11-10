#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MuJoCo仿真功能函数库
提供标准化的MuJoCo仿真控制接口，供LLM任务规划使用
"""

import sys
import os
import json
# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import numpy as np
import time
from typing import List, Optional, Tuple, Dict, Any

# 导入机械臂控制核心
# 延迟导入 MuJoCo 控制核心，避免在未安装/打包排除 MuJoCo 时导入失败
MujocoKinematicsControlCore = None

def _lazy_import_controller_class():
    """尝试延迟导入控制核心类；失败时返回 False 而不是抛异常。"""
    global MujocoKinematicsControlCore
    if MujocoKinematicsControlCore is not None:
        return True
    try:
        from core.embodied_core.mujoco_kinematics_control_core import MujocoKinematicsControlCore as _Controller
        MujocoKinematicsControlCore = _Controller
        return True
    except Exception as e:
        print(f"⚠️ MuJoCo 仿真组件不可用，已禁用仿真功能：{e}")
        return False

# 全局控制器实例
_arm_controller = None

# 全局运动参数（用于显示，MuJoCo仿真的速度由内部控制）
_motion_params = {
    "max_speed": 100,      # 最大速度 (RPM)
    "acceleration": 50,    # 加速度 (RPM/s)
    "deceleration": 50     # 减速度 (RPM/s)
}

def _get_controller():
    """获取全局控制器实例"""
    global _arm_controller
    if not _lazy_import_controller_class():
        return None
    if _arm_controller is None:
        try:
            _arm_controller = MujocoKinematicsControlCore()
        except Exception as e:
            print(f"⚠️ MuJoCo 控制器初始化失败：{e}")
            return None
    return _arm_controller

def _set_motion_params(max_speed=100, acceleration=50, deceleration=50):
    """
    设置MuJoCo仿真运动参数（主要用于显示和日志）
    
    Args:
        max_speed: 最大速度 (RPM)
        acceleration: 加速度 (RPM/s)
        deceleration: 减速度 (RPM/s)
    
    Note:
        MuJoCo仿真的实际速度由内部控制算法决定，这里主要用于参数同步和日志显示
    """
    global _motion_params
    _motion_params = {
        "max_speed": max_speed,
        "acceleration": acceleration,
        "deceleration": deceleration
    }
    print(f"⚙️ MuJoCo仿真运动参数已同步: 速度={max_speed}RPM, 加速度={acceleration}RPM/s, 减速度={deceleration}RPM/s")

def _clear_trajectory():
    """
    清空MuJoCo仿真的运动轨迹
    
    Returns:
        bool: 清空是否成功
    """
    try:
        controller = _get_controller()
        if hasattr(controller, 'controller') and controller.controller:
            controller.controller.clear_trajectory()
            return True
        else:
            print("⚠️ MuJoCo控制器未初始化，无法清空轨迹")
            return False
    except Exception as e:
        print(f"❌ 清空MuJoCo轨迹失败: {e}")
        return False

def _get_motion_params():
    """
    获取当前运动参数
    
    Returns:
        dict: 运动参数字典
    """
    global _motion_params
    return _motion_params.copy()

def c_a_j(j_a: List[float], du: float = None) -> bool:
    """
    控制机械臂关节角度运动 (Control Arm Joints)
    
    Args:
        j_a: 6个关节的目标角度值，单位度 [J1, J2, J3, J4, J5, J6]
        du: 运动持续时间，单位秒，None则自动计算最优时间
        
    Returns:
        bool: 运动执行是否成功
    """
    controller = _get_controller()
    joint_angles = j_a
    duration = du
    
    try:
        controller = _get_controller()
        if controller is None:
            print("ℹ️ 当前未启用 MuJoCo，c_a_j 被跳过")
            return False
        print(f"🎮 MuJoCo仿真关节角度控制: {joint_angles}")
        
        # 显示运动参数（虽然MuJoCo内部控制速度，但让用户知道参数已同步）
        motion_params = _get_motion_params()
        print(f"🎛️ 仿真运动参数: 速度={motion_params['max_speed']}RPM, 加速度={motion_params['acceleration']}RPM/s, 减速度={motion_params['deceleration']}RPM/s")
        if duration is not None:
            print(f"⏱️ 指定持续时间: {duration}秒")
        
        # 设置关节角度
        success = controller.set_joint_angles(joint_angles)
        if not success:
            print("❌ MuJoCo仿真设置失败")
            return False
        
        # 执行运动
        success = controller.drive_to_target(duration=duration)
        if success:
            print("✅ MuJoCo仿真关节控制成功")
        else:
            print("❌ MuJoCo仿真关节控制失败")
        return success
        
    except Exception as e:
        print(f"❌ MuJoCo仿真关节运动控制失败: {e}")
        return False

def c_a_p(pos: List[float], ori: Optional[List[float]] = None, 
          du: float = None) -> bool:
    """
    控制机械臂末端位置运动，自动进行逆运动学计算 (Control Arm Position)
    
    Args:
        pos: 末端执行器目标位置，单位毫米 [x, y, z]
        ori: 末端执行器目标姿态，单位度 [roll, pitch, yaw]，None则保持当前姿态
        du: 运动持续时间，单位秒，None则自动计算最优时间
        
    Returns:
        bool: 运动执行是否成功
    """
    position = pos
    orientation = ori
    duration = du
    
    try:
        controller = _get_controller()
        if controller is None:
            print("ℹ️ 当前未启用 MuJoCo，c_a_p 被跳过")
            return False
        print(f"🎮 MuJoCo仿真末端位置控制: {position}, 姿态: {orientation}")
        
        # 设置末端位置（自动进行逆运动学计算）
        success = controller.set_end_effector_position(position, orientation)
        if not success:
            print("❌ MuJoCo仿真逆运动学计算失败")
            return False
        
        # 执行运动
        success = controller.drive_to_target(duration=duration)
        if success:
            print("✅ MuJoCo仿真位置控制成功")
        else:
            print("❌ MuJoCo仿真位置控制失败")
        return success
        
    except Exception as e:
        print(f"❌ MuJoCo仿真位置运动控制失败: {e}")
        return False
    
def e_p_a(a_n: str, sp: str = "normal") -> bool:
    """
    执行预设的动作 (Execute Preset Action)
    
    Args:
        a_n: 动作名称，如"点头"、"抬头"、"摇头"等
        sp: 执行速度，"slow"/"normal"/"fast"
        
    Returns:
        bool: 动作执行是否成功
    """
    action_name = a_n
    speed = sp
    
    try:
        print(f"🎮 MuJoCo仿真执行预设动作: {action_name} (速度: {speed})")
        
        # 获取JSON文件路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, "preset_actions.json")
        
        # 读取JSON文件
        if not os.path.exists(json_path):
            print(f"❌ 预设动作文件不存在: {json_path}")
            return False
            
        with open(json_path, 'r', encoding='utf-8') as f:
            preset_actions = json.load(f)
        
        # 检查动作是否存在
        if action_name not in preset_actions:
            print(f"❌ 未知的预设动作: {action_name}")
            available_actions = list(preset_actions.keys())
            print(f"可用动作: {available_actions}")
            return False
        
        # 获取动作参数
        action_params = preset_actions[action_name]
        joints = action_params["joints"]
        duration = action_params["duration"]
        
        # 根据速度调整持续时间
        if speed == "slow":
            duration *= 1.5
        elif speed == "fast":
            duration *= 0.7
        
        print(f"📋 动作参数: 关节角度={joints}, 持续时间={duration:.1f}秒")
        
        # 使用关节控制函数执行动作
        return c_a_j(joints, duration)
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON文件解析错误: {e}")
        return False
    except FileNotFoundError:
        print(f"❌ 预设动作文件未找到: {json_path}")
        return False
    except Exception as e:
        print(f"❌ MuJoCo仿真预设动作执行失败: {e}")
        return False



