#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运动学工厂类
根据配置自动创建配置好的运动学实例
"""

import sys
import os
import numpy as np
from typing import Optional

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from core.arm_core.kinematics import RobotKinematics


class KinematicsFactory:
    """
    运动学工厂类
    根据DH参数配置自动创建和配置运动学实例
    """
    
    @staticmethod
    def create_robot_kinematics(use_config: bool = True) -> RobotKinematics:
        """
        创建机械臂运动学实例
        
        Args:
            use_config: 是否使用配置文件中的DH参数，False则使用默认参数
            
        Returns:
            配置好的RobotKinematics实例
        """
        if use_config:
            try:
                # 延迟导入避免循环导入
                from Main_UI.widgets.dh_parameter_manager import dh_config_manager
                
                # 从配置管理器获取参数
                config = dh_config_manager.config
                
                # 获取DH参数
                dh_params = dh_config_manager.get_dh_parameters()
                d = dh_params["d"]
                a = dh_params["a"]
                alpha = dh_params["alpha"]  # 已经是弧度制
                
                # 获取关节限制
                joint_limits = dh_config_manager.get_joint_limits()
                
                # 获取角度单位
                angle_unit = dh_config_manager.get_angle_unit()
                
                # 获取关节偏转
                joint_offsets = dh_config_manager.get_joint_offsets()
                
                # 创建运动学实例
                kinematics = RobotKinematics(
                    d=d,
                    a=a,
                    alpha=alpha,
                    joint_limits=joint_limits,
                    angle_unit=angle_unit,
                    joint_offsets=joint_offsets
                )
                
                # 设置偏转
                if dh_config_manager.is_offset_enabled():
                    kinematics.set_angle_offset(joint_offsets)
                
                
                return kinematics
                
            except Exception as e:
                print(f"⚠️ 使用配置参数创建运动学实例失败: {e}")
                print("   将使用默认参数创建运动学实例")
                return RobotKinematics()
        else:
            # 使用默认参数
            print("ℹ️ 使用默认参数创建运动学实例")
            return RobotKinematics()
    
    @staticmethod
    def reload_config():
        """重新加载DH参数配置"""
        try:
            # 延迟导入避免循环导入
            from Main_UI.widgets.dh_parameter_manager import dh_config_manager
            dh_config_manager.config = dh_config_manager.load_config()
        except Exception as e:
            print(f"❌ 重新加载DH参数配置失败: {e}")
    
    @staticmethod
    def get_current_dh_summary() -> dict:
        """
        获取当前DH参数配置摘要
        
        Returns:
            包含当前DH参数信息的字典
        """
        try:
            # 延迟导入避免循环导入
            from Main_UI.widgets.dh_parameter_manager import dh_config_manager
            
            dh_params = dh_config_manager.get_dh_parameters()
            joint_offsets = dh_config_manager.get_joint_offsets()
            joint_limits = dh_config_manager.get_joint_limits()
            
            return {
                "dh_parameters": {
                    "d": dh_params["d"],
                    "a": dh_params["a"],
                    "alpha_deg": [np.rad2deg(alpha) for alpha in dh_params["alpha"]]
                },
                "joint_offsets": joint_offsets,
                "joint_limits": joint_limits,
                "angle_unit": dh_config_manager.get_angle_unit(),
                "offset_enabled": dh_config_manager.is_offset_enabled(),
                "config_file": dh_config_manager.get_config_file_path()
            }
        except Exception as e:
            print(f"❌ 获取DH参数摘要失败: {e}")
            return {}
    


# 便捷的全局函数
def create_configured_kinematics() -> RobotKinematics:
    """
    创建使用配置参数的运动学实例的便捷函数
    
    Returns:
        配置好的RobotKinematics实例
    """
    return KinematicsFactory.create_robot_kinematics(use_config=True)


def create_default_kinematics() -> RobotKinematics:
    """
    创建使用默认参数的运动学实例的便捷函数
    
    Returns:
        使用默认参数的RobotKinematics实例
    """
    return KinematicsFactory.create_robot_kinematics(use_config=False)


