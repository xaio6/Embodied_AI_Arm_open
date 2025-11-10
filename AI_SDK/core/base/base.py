"""
基础类定义模块
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from ...utils.exceptions import AISDKException

class BaseProvider(ABC):
    """厂商适配器基类"""
    
    def __init__(self, api_key: str, config: Dict[str, Any] = None):
        """
        初始化厂商适配器
        
        Args:
            api_key: API密钥
            config: 配置参数
        """
        if not api_key:
            raise AISDKException("API密钥不能为空")
        
        self.api_key = api_key
        self.config = config or {}
    
    @abstractmethod
    def chat(self, model: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        同步聊天接口
        
        Args:
            model: 模型名称
            prompt: 提示词
            **kwargs: 其他参数
            
        Returns:
            响应结果
        """
        pass
    
    @abstractmethod
    async def chat_async(self, model: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        异步聊天接口
        
        Args:
            model: 模型名称
            prompt: 提示词
            **kwargs: 其他参数
            
        Returns:
            响应结果
        """
        pass
    
    def validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证和处理参数
        
        Args:
            params: 输入参数
            
        Returns:
            处理后的参数
        """
        # 子类可以重写此方法来实现特定的参数验证逻辑
        return params

class BaseService(ABC):
    """服务基类"""
    
    def __init__(self, config):
        """
        初始化服务
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.providers = {}
    
    def get_provider(self, provider_name: str):
        """
        获取厂商适配器实例
        
        Args:
            provider_name: 厂商名称
            
        Returns:
            厂商适配器实例
        """
        if provider_name not in self.providers:
            raise AISDKException(f"不支持的厂商: {provider_name}")
        
        return self.providers[provider_name]
    
    def register_provider(self, provider_name: str, provider_class, **kwargs):
        """
        注册厂商适配器
        
        Args:
            provider_name: 厂商名称
            provider_class: 厂商适配器类
            **kwargs: 初始化参数
        """
        provider_config = self.config.get('providers', {}).get(provider_name, {})
        api_key = provider_config.get('api_key')
        if not api_key:
            raise AISDKException(f"未配置{provider_name}的API密钥")
        
        self.providers[provider_name] = provider_class(api_key, provider_config) 