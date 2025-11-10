# -*- coding: utf-8 -*-
"""
电机配置管理器
统一管理所有电机的减速比和方向设置
"""

import os
import yaml
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import logging

# 获取项目根目录
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))

class MotorConfigManager:
    """电机配置管理器"""
    
    def __init__(self, config_file_path=None):
        """
        初始化配置管理器
        
        Args:
            config_file_path: 配置文件路径，如果为None则使用默认路径
        """
        if config_file_path is None:
            # 使用项目根目录下的config文件夹
            config_dir = os.path.join(project_root, "config")
            self.config_file_path = os.path.join(config_dir, "motor_config.json")
        else:
            self.config_file_path = config_file_path
        
        # 默认配置
        self.default_config = {
            "motor_reducer_ratios": {
                "1": 62.0,
                "2": 51.0,
                "3": 51.0,
                "4": 62.0,
                "5": 12.0,
                "6": 8.0
            },
            "motor_directions": {
                "1": 1,
                "2": 1,
                "3": 1,
                "4": 1,
                "5": 1,
                "6": 1
            }
        }
        
        # 当前配置
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """
        从文件加载配置
        
        Returns:
            配置字典
        """
        try:
            if os.path.exists(self.config_file_path):
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 确保配置完整
                    return self._ensure_complete_config(config)
            else:
                # 文件不存在，使用默认配置并保存
                self.save_config(self.default_config)
                return self.default_config.copy()
        except Exception as e:
            print(f"加载电机配置失败: {e}")
            return self.default_config.copy()
    
    def save_config(self, config: Dict[str, Any] = None) -> bool:
        """
        保存配置到文件
        
        Args:
            config: 要保存的配置，如果为None则保存当前配置
            
        Returns:
            是否保存成功
        """
        try:
            # 确保配置目录存在
            os.makedirs(os.path.dirname(self.config_file_path), exist_ok=True)
            
            save_config = config if config is not None else self.config
            
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(save_config, f, ensure_ascii=False, indent=2)
            
            if config is not None:
                self.config = save_config.copy()
            
            return True
        except Exception as e:
            print(f"保存电机配置失败: {e}")
            return False
    
    def _ensure_complete_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        确保配置完整，补充缺失的默认值
        
        Args:
            config: 输入配置
            
        Returns:
            完整的配置
        """
        complete_config = self.default_config.copy()
        
        # 更新减速比配置
        if "motor_reducer_ratios" in config:
            complete_config["motor_reducer_ratios"].update(config["motor_reducer_ratios"])
        
        # 更新方向配置
        if "motor_directions" in config:
            complete_config["motor_directions"].update(config["motor_directions"])
        
        return complete_config
    
    def get_motor_reducer_ratio(self, motor_id: int) -> float:
        """
        获取指定电机的减速比
        
        Args:
            motor_id: 电机ID
            
        Returns:
            减速比
        """
        return self.config["motor_reducer_ratios"].get(str(motor_id), 16.0)
    
    def get_motor_direction(self, motor_id: int) -> int:
        """
        获取指定电机的方向
        
        Args:
            motor_id: 电机ID
            
        Returns:
            方向 (1=正向, -1=反向)
        """
        return self.config["motor_directions"].get(str(motor_id), 1)
    
    def set_motor_reducer_ratio(self, motor_id: int, ratio: float) -> None:
        """
        设置指定电机的减速比
        
        Args:
            motor_id: 电机ID
            ratio: 减速比
        """
        self.config["motor_reducer_ratios"][str(motor_id)] = ratio
    
    def set_motor_direction(self, motor_id: int, direction: int) -> None:
        """
        设置指定电机的方向
        
        Args:
            motor_id: 电机ID
            direction: 方向 (1=正向, -1=反向)
        """
        self.config["motor_directions"][str(motor_id)] = direction
    
    def get_all_reducer_ratios(self) -> Dict[int, float]:
        """
        获取所有电机的减速比
        
        Returns:
            电机ID到减速比的映射字典
        """
        return {int(k): v for k, v in self.config["motor_reducer_ratios"].items()}
    
    def get_all_directions(self) -> Dict[int, int]:
        """
        获取所有电机的方向
        
        Returns:
            电机ID到方向的映射字典
        """
        return {int(k): v for k, v in self.config["motor_directions"].items()}
    
    def reset_to_default(self) -> None:
        """重置为默认配置"""
        self.config = self.default_config.copy()
    
    def get_config_file_path(self) -> str:
        """获取配置文件路径"""
        return self.config_file_path

# 全局配置管理器实例
motor_config_manager = MotorConfigManager() 