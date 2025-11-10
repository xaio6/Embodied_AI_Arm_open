"""
配置管理模块 - 支持YAML配置文件
"""

import os
import re
import yaml
import logging
from typing import Dict, Any, Optional, Union
from pathlib import Path
from dotenv import load_dotenv

class Config:
    """配置管理类 - 支持YAML配置文件"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置
        
        Args:
            config_path: 配置文件路径，默认为项目根目录的config.yaml
        """
        # 加载环境变量
        load_dotenv()
        
        # 确定配置文件路径
        if config_path is None:
            # 默认配置文件路径
            current_dir = Path(__file__).parent.parent.parent
            config_path = current_dir / "config.yaml"
        
        self.config_path = Path(config_path)
        self.config_data = self._load_config()
        
        # 设置日志
        self._setup_logging()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        加载YAML配置文件
        
        Returns:
            配置数据字典
        """
        try:
            if not self.config_path.exists():
                logging.warning(f"配置文件不存在: {self.config_path}，使用默认配置")
                return self._get_default_config()
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_content = f.read()
            
            # 替换环境变量
            config_content = self._substitute_env_vars(config_content)
            
            # 解析YAML
            config_data = yaml.safe_load(config_content)
            
            if config_data is None:
                logging.warning("配置文件为空，使用默认配置")
                return self._get_default_config()
            
            logging.info(f"成功加载配置文件: {self.config_path}")
            return config_data
            
        except yaml.YAMLError as e:
            logging.error(f"YAML配置文件解析错误: {e}")
            return self._get_default_config()
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            return self._get_default_config()
    
    def _substitute_env_vars(self, content: str) -> str:
        """
        替换配置文件中的环境变量
        支持格式: ${ENV_VAR_NAME:default_value}
        
        Args:
            content: 配置文件内容
            
        Returns:
            替换后的内容
        """
        def replace_env_var(match):
            var_expr = match.group(1)
            if ':' in var_expr:
                var_name, default_value = var_expr.split(':', 1)
            else:
                var_name, default_value = var_expr, ''
            
            return os.getenv(var_name, default_value)
        
        # 匹配 ${VAR_NAME:default} 格式
        pattern = r'\$\{([^}]+)\}'
        return re.sub(pattern, replace_env_var, content)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        获取默认配置
        
        Returns:
            默认配置字典
        """
        return {
            'api_keys': {
                'alibaba': os.getenv('ALIBABA_API_KEY', ''),
                'deepseek': os.getenv('DEEPSEEK_API_KEY', ''),
            },
            'api_endpoints': {
                'alibaba': {
                    'llm': 'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation',
                    'tts': 'https://dashscope.aliyuncs.com/api/v1/services/audio/tts',
                    'asr': 'https://dashscope.aliyuncs.com/api/v1/services/audio/asr',
                },
                'deepseek': {
                    'llm': 'https://api.deepseek.com/v1/chat/completions',
                }
            },
            'models': {
                'alibaba': {
                    'llm': ['qwen-turbo', 'qwen-plus', 'qwen-max'],
                    'tts': ['sambert-zhichu-v1'],
                    'asr': ['paraformer-v1'],
                },
                'deepseek': {
                    'llm': ['deepseek-chat', 'deepseek-coder'],
                }
            },
            'default_params': {
                'alibaba': {
                    'llm': {'temperature': 0.7, 'max_tokens': 2000, 'top_p': 0.8}
                },
                'deepseek': {
                    'llm': {'temperature': 0.7, 'max_tokens': 2000, 'top_p': 1.0}
                }
            },
            'session': {
                'default_max_history': 20,
                'auto_cleanup': True,
                'cleanup_interval': 3600,
                'max_sessions': 100
            },
            'request': {
                'timeout': 60,
                'max_retries': 3,
                'retry_delay': 1.0
            },
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            }
        }
    
    def _setup_logging(self):
        """设置日志配置"""
        log_config = self.get('logging', {})
        
        level = getattr(logging, log_config.get('level', 'INFO').upper())
        format_str = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # 基本配置
        logging.basicConfig(
            level=level,
            format=format_str,
            force=True
        )
        
        # 如果配置了日志文件
        if 'file' in log_config:
            file_handler = logging.FileHandler(log_config['file'])
            file_handler.setFormatter(logging.Formatter(format_str))
            logging.getLogger().addHandler(file_handler)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，支持点号分隔的嵌套键
        
        Args:
            key: 配置键，支持 'section.subsection.key' 格式
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self.config_data
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any):
        """
        设置配置值
        
        Args:
            key: 配置键
            value: 配置值
        """
        keys = key.split('.')
        config = self.config_data
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """获取厂商API密钥"""
        return self.get(f'api_keys.{provider}')
    
    def get_api_endpoint(self, provider: str, service: str) -> Optional[str]:
        """获取厂商API端点"""
        return self.get(f'api_endpoints.{provider}.{service}')
    
    def get_available_models(self, provider: str, service: str) -> list:
        """获取厂商可用模型列表"""
        return self.get(f'models.{provider}.{service}', [])
    
    def get_default_params(self, provider: str, service: str) -> Dict[str, Any]:
        """获取默认参数"""
        return self.get(f'default_params.{provider}.{service}', {})
    
    def validate_model(self, provider: str, service: str, model: str) -> bool:
        """验证模型是否支持"""
        available_models = self.get_available_models(provider, service)
        return model in available_models
    
    def get_session_config(self) -> Dict[str, Any]:
        """获取会话配置"""
        return self.get('session', {})
    
    def get_request_config(self) -> Dict[str, Any]:
        """获取请求配置"""
        return self.get('request', {})
    
    def is_debug_mode(self) -> bool:
        """是否为调试模式"""
        return self.get('development.debug', False)
    
    def save_config(self, config_path: Optional[str] = None):
        """
        保存配置到文件
        
        Args:
            config_path: 配置文件路径，默认使用当前配置文件路径
        """
        if config_path is None:
            config_path = self.config_path
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config_data, f, default_flow_style=False, 
                         allow_unicode=True, indent=2)
            logging.info(f"配置已保存到: {config_path}")
        except Exception as e:
            logging.error(f"保存配置文件失败: {e}")
    
    def reload_config(self):
        """重新加载配置文件"""
        self.config_data = self._load_config()
        self._setup_logging()
        logging.info("配置文件已重新加载")
    
    def get_all_config(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self.config_data.copy()
    
    def validate_config(self) -> Dict[str, list]:
        """
        验证配置完整性
        
        Returns:
            验证结果，包含错误和警告
        """
        errors = []
        warnings = []
        
        # 检查必需的API密钥
        for provider in ['alibaba', 'deepseek']:
            api_key = self.get_api_key(provider)
            if not api_key:
                warnings.append(f"缺少 {provider} API密钥")
        
        # 检查API端点
        for provider in self.get('api_endpoints', {}):
            for service in self.get(f'api_endpoints.{provider}', {}):
                endpoint = self.get_api_endpoint(provider, service)
                if not endpoint or not endpoint.startswith('http'):
                    errors.append(f"无效的API端点: {provider}.{service}")
        
        # 检查模型配置
        for provider in self.get('models', {}):
            for service in self.get(f'models.{provider}', {}):
                models = self.get_available_models(provider, service)
                if not models:
                    warnings.append(f"没有配置模型: {provider}.{service}")
        
        return {'errors': errors, 'warnings': warnings} 