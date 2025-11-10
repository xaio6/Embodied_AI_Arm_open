# -*- coding: utf-8 -*-
"""
通用配置管理器
提供统一的配置文件读取、保存和管理功能
"""

import os
import json
from typing import Dict, Any, Optional
from PyQt5.QtWidgets import QMessageBox


class ConfigManager:
    """通用配置管理器类"""
    
    def __init__(self, config_file_path: str = None):
        """
        初始化配置管理器
        
        Args:
            config_file_path: 配置文件路径，默认为项目根目录下的 config/all_parameter_config.json
        """
        if config_file_path is None:
            # 获取项目根目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            config_file_path = os.path.join(project_root, "config", "all_parameter_config.json")
        
        self.config_file_path = config_file_path
        self._config_cache = None  # 配置缓存
    
    def load_config(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        从配置文件加载完整配置
        
        Args:
            use_cache: 是否使用缓存，默认为 True
            
        Returns:
            完整的配置字典
        """
        try:
            # 如果启用缓存且缓存存在，直接返回缓存
            if use_cache and self._config_cache is not None:
                return self._config_cache.copy()
            
            if not os.path.exists(self.config_file_path):
                print(f"⚠️ 配置文件不存在: {self.config_file_path}")
                return {}
            
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 更新缓存
            if use_cache:
                self._config_cache = config.copy()
            
            print(f"✅ 成功加载配置文件: {self.config_file_path}")
            return config
            
        except Exception as e:
            print(f"❌ 加载配置文件失败: {e}")
            return {}
    
    def save_config(self, config: Dict[str, Any], backup: bool = True) -> bool:
        """
        保存完整配置到文件
        
        Args:
            config: 要保存的配置字典
            backup: 是否创建备份，默认为 True
            
        Returns:
            是否保存成功
        """
        try:
            # 创建目录（如果不存在）
            os.makedirs(os.path.dirname(self.config_file_path), exist_ok=True)
            
            # # 创建备份
            # if backup and os.path.exists(self.config_file_path):
            #     backup_path = self.config_file_path + '.backup'
            #     try:
            #         import shutil
            #         shutil.copy2(self.config_file_path, backup_path)
            #         print(f"📁 配置备份已创建: {backup_path}")
            #     except Exception as backup_error:
            #         print(f"⚠️ 创建备份失败: {backup_error}")
            
            # 保存配置
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            # 更新缓存
            self._config_cache = config.copy()
            
            return True
            
        except Exception as e:
            print(f"❌ 保存配置文件失败: {e}")
            return False
    
    def get_module_config(self, module_name: str) -> Dict[str, Any]:
        """
        获取指定模块的配置
        
        Args:
            module_name: 模块名称（如 'vision_grasp', 'embodied_intelligence' 等）
            
        Returns:
            模块配置字典
        """
        try:
            config = self.load_config()
            module_config = config.get(module_name, {})
            return module_config
            
        except Exception as e:
            print(f"❌ 获取模块配置失败 [{module_name}]: {e}")
            return {}
    
    def save_module_config(self, module_name: str, module_config: Dict[str, Any]) -> bool:
        """
        保存指定模块的配置
        
        Args:
            module_name: 模块名称
            module_config: 模块配置字典
            
        Returns:
            是否保存成功
        """
        try:
            # 读取现有完整配置
            config = self.load_config()
            
            # 更新指定模块配置
            config[module_name] = module_config
            
            # 保存完整配置
            success = self.save_config(config)
            
            return success
            
        except Exception as e:
            print(f"❌ 保存模块配置失败 [{module_name}]: {e}")
            return False
    
    def get_config_value(self, module_name: str, key_path: str, default_value: Any = None) -> Any:
        """
        获取指定路径的配置值
        
        Args:
            module_name: 模块名称
            key_path: 配置键路径，使用点号分隔（如 'camera.device_id'）
            default_value: 默认值
            
        Returns:
            配置值
        """
        try:
            module_config = self.get_module_config(module_name)
            
            # 解析键路径
            keys = key_path.split('.')
            value = module_config
            
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default_value
            
            return value
            
        except Exception as e:
            print(f"❌ 获取配置值失败 [{module_name}.{key_path}]: {e}")
            return default_value
    
    def set_config_value(self, module_name: str, key_path: str, value: Any) -> bool:
        """
        设置指定路径的配置值
        
        Args:
            module_name: 模块名称
            key_path: 配置键路径，使用点号分隔（如 'camera.device_id'）
            value: 要设置的值
            
        Returns:
            是否设置成功
        """
        try:
            module_config = self.get_module_config(module_name)
            
            # 解析键路径
            keys = key_path.split('.')
            current = module_config
            
            # 创建嵌套字典结构
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            
            # 设置最终值
            current[keys[-1]] = value
            
            # 保存模块配置
            return self.save_module_config(module_name, module_config)
            
        except Exception as e:
            print(f"❌ 设置配置值失败 [{module_name}.{key_path}]: {e}")
            return False
    
    def clear_cache(self):
        """清除配置缓存"""
        self._config_cache = None
        print("🧹 配置缓存已清除")
    
    def validate_config(self, config: Dict[str, Any], schema: Dict[str, Any] = None) -> bool:
        """
        验证配置格式
        
        Args:
            config: 要验证的配置
            schema: 验证模式（可选）
            
        Returns:
            是否验证通过
        """
        try:
            # 基础验证：确保是字典
            if not isinstance(config, dict):
                return False
            
            # 如果提供了模式，进行详细验证
            if schema:
                # 这里可以添加更复杂的模式验证逻辑
                pass
            
            return True
            
        except Exception as e:
            print(f"❌ 配置验证失败: {e}")
            return False
    
    def export_config(self, export_path: str, module_names: Optional[list] = None) -> bool:
        """
        导出配置到指定文件
        
        Args:
            export_path: 导出文件路径
            module_names: 要导出的模块名列表，None 表示导出全部
            
        Returns:
            是否导出成功
        """
        try:
            config = self.load_config()
            
            if module_names:
                # 只导出指定模块
                export_config = {name: config.get(name, {}) for name in module_names}
            else:
                # 导出全部配置
                export_config = config
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_config, f, indent=2, ensure_ascii=False)
            
            print(f"📤 配置导出成功: {export_path}")
            return True
            
        except Exception as e:
            print(f"❌ 配置导出失败: {e}")
            return False
    
    def import_config(self, import_path: str, merge: bool = True) -> bool:
        """
        从指定文件导入配置
        
        Args:
            import_path: 导入文件路径
            merge: 是否与现有配置合并，False 表示完全替换
            
        Returns:
            是否导入成功
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                import_config = json.load(f)
            
            if merge:
                # 合并配置
                existing_config = self.load_config()
                existing_config.update(import_config)
                final_config = existing_config
            else:
                # 替换配置
                final_config = import_config
            
            success = self.save_config(final_config)
            
            if success:
                print(f"📥 配置导入成功: {import_path}")
            
            return success
            
        except Exception as e:
            print(f"❌ 配置导入失败: {e}")
            return False


# 创建全局配置管理器实例
config_manager = ConfigManager()


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器实例"""
    return config_manager
