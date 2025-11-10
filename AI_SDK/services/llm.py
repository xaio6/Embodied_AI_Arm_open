"""
LLM服务模块
"""

import asyncio
from typing import Dict, Any, Iterator, AsyncIterator, Optional
from ..core.base import BaseService
from ..providers.alibaba.llm_provider import AlibabaLLMProvider
from ..providers.deepseek.llm_provider import DeepSeekLLMProvider
from ..utils.exceptions import AISDKException, ProviderException, ModelException, ValidationException, APIException
from ..utils.helpers import format_response, validate_model_config
from ..providers import get_provider

class LLMService(BaseService):
    """LLM服务类"""
    
    def __init__(self, config):
        """
        初始化LLM服务
        
        Args:
            config: 配置对象
        """
        super().__init__(config)
        self._register_providers()
    
    def _register_providers(self):
        """注册所有支持的厂商适配器"""
        try:
            # 注册阿里云适配器
            alibaba_config = self.config.get('providers', {}).get('alibaba', {})
            if alibaba_config.get('enabled') and alibaba_config.get('api_key'):
                self.register_provider('alibaba', AlibabaLLMProvider)
        except Exception as e:
            # 如果注册失败，记录但不抛出异常，允许其他厂商正常工作
            pass
        
        try:
            # 注册DeepSeek适配器
            deepseek_config = self.config.get('providers', {}).get('deepseek', {})
            if deepseek_config.get('enabled') and deepseek_config.get('api_key'):
                self.register_provider('deepseek', DeepSeekLLMProvider)
        except Exception as e:
            pass
    
    def chat(self, provider: str, model: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        同步聊天接口
        
        Args:
            provider: 厂商名称
            model: 模型名称
            prompt: 提示词
            **kwargs: 其他参数
            
        Returns:
            格式化后的响应结果
        """
        try:
            # 验证厂商
            if provider not in self.providers:
                available_providers = list(self.providers.keys())
                raise ProviderException(
                    provider, 
                    f"不支持的厂商，可用厂商: {', '.join(available_providers)}"
                )
            

            
            # 获取厂商适配器
            provider_instance = self.get_provider(provider)
            
            # 验证参数
            validated_params = provider_instance.validate_params(kwargs)
            
            # 调用厂商API
            content = provider_instance.chat(model, prompt, **validated_params)
            
            # 格式化响应
            formatted_response = format_response(content, provider, model, is_stream=False)
            
            return formatted_response
            
        except (ProviderException, ModelException, AISDKException):
            # 重新抛出已知异常
            raise
        except Exception as e:
            # 包装未知异常
            raise APIException(f"聊天请求失败: {str(e)}")
    
    def chat_stream(self, provider: str, model: str, prompt: str, **kwargs) -> Iterator[Dict[str, Any]]:
        """
        同步流式聊天接口
        
        Args:
            provider: 厂商名称
            model: 模型名称
            prompt: 提示词
            **kwargs: 其他参数
            
        Yields:
            格式化后的流式响应结果
        """
        try:
            # 验证厂商
            if provider not in self.providers:
                available_providers = list(self.providers.keys())
                raise ProviderException(
                    provider, 
                    f"不支持的厂商，可用厂商: {', '.join(available_providers)}"
                )
            

            
            # 获取厂商适配器
            provider_instance = self.get_provider(provider)
            
            # 验证参数
            validated_params = provider_instance.validate_params(kwargs)
            
            # 调用厂商流式API
            for content_chunk in provider_instance.chat_stream(model, prompt, **validated_params):
                # 格式化流式响应
                formatted_chunk = format_response(content_chunk, provider, model, is_stream=True)
                yield formatted_chunk
            
        except (ProviderException, ModelException, AISDKException):
            # 重新抛出已知异常
            raise
        except Exception as e:
            # 包装未知异常
            raise APIException(f"流式聊天请求失败: {str(e)}")
    
    async def chat_async(self, provider: str, model: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        异步聊天接口
        
        Args:
            provider: 厂商名称
            model: 模型名称
            prompt: 提示词
            **kwargs: 其他参数
            
        Returns:
            格式化后的响应结果
        """
        try:
            # 验证厂商
            if provider not in self.providers:
                available_providers = list(self.providers.keys())
                raise ProviderException(
                    provider, 
                    f"不支持的厂商，可用厂商: {', '.join(available_providers)}"
                )
            

            
            # 获取厂商适配器
            provider_instance = self.get_provider(provider)
            
            # 验证参数
            validated_params = provider_instance.validate_params(kwargs)
            
            # 调用厂商API
            content = await provider_instance.chat_async(model, prompt, **validated_params)
            
            # 格式化响应
            formatted_response = format_response(content, provider, model, is_stream=False)
            
            return formatted_response
            
        except (ProviderException, ModelException, AISDKException):
            # 重新抛出已知异常
            raise
        except Exception as e:
            # 包装未知异常
            raise APIException(f"异步聊天请求失败: {str(e)}")
    
    async def chat_stream_async(self, provider: str, model: str, prompt: str, **kwargs) -> AsyncIterator[Dict[str, Any]]:
        """
        异步流式聊天接口
        
        Args:
            provider: 厂商名称
            model: 模型名称
            prompt: 提示词
            **kwargs: 其他参数
            
        Yields:
            格式化后的流式响应结果
        """
        try:
            # 验证厂商
            if provider not in self.providers:
                available_providers = list(self.providers.keys())
                raise ProviderException(
                    provider, 
                    f"不支持的厂商，可用厂商: {', '.join(available_providers)}"
                )
            
            
            # 获取厂商适配器
            provider_instance = self.get_provider(provider)
            
            # 验证参数
            validated_params = provider_instance.validate_params(kwargs)
            
            # 调用厂商异步流式API
            async for content_chunk in provider_instance.chat_stream_async(model, prompt, **validated_params):
                # 格式化流式响应
                formatted_chunk = format_response(content_chunk, provider, model, is_stream=True)
                yield formatted_chunk
            
        except (ProviderException, ModelException, AISDKException):
            # 重新抛出已知异常
            raise
        except Exception as e:
            # 包装未知异常
            raise APIException(f"异步流式聊天请求失败: {str(e)}")
    
    def get_available_providers(self) -> Dict[str, Dict[str, Any]]:
        """
        获取可用的厂商列表
        
        Returns:
            厂商信息字典
        """
        available = {}
        for name, provider in self.providers.items():
            provider_config = self.config['providers'][name]
            available[name] = {
                'enabled': True,
                'models': provider_config.get('models', {}),
                'description': provider_config.get('description', ''),
                'supports_stream': hasattr(provider, 'chat_stream')
            }
        return available
    
    def get_available_models(self, provider: str) -> list:
        """
        获取指定厂商的可用模型列表
        
        Args:
            provider: 厂商名称
            
        Returns:
            模型列表
        """
        provider_config = self.config.get('providers', {}).get(provider, {})
        return list(provider_config.get('models', {}).keys())
    
    def get_provider_info(self, provider: str) -> Dict[str, Any]:
        """
        获取厂商信息
        
        Args:
            provider: 厂商名称
            
        Returns:
            厂商信息
        """
        if provider not in self.providers:
            raise ProviderException(provider, "不支持的厂商")
        
        provider_config = self.config.get('providers', {}).get(provider, {})
        
        return {
            'provider': provider,
            'available_models': self.get_available_models(provider),
            'default_params': provider_config.get('default_params', {}),
            'description': provider_config.get('description', '')
        }

    def get_provider_models(self, provider: str) -> Dict[str, Any]:
        """
        获取指定厂商的模型列表
        
        Args:
            provider: 厂商名称
            
        Returns:
            模型信息字典
        """
        if provider not in self.providers:
            raise ValidationException(f"未找到厂商: {provider}")
        
        provider_config = self.config['providers'][provider]
        return provider_config.get('models', {}) 