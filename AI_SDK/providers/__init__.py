"""
提供商模块
"""

from .alibaba import AlibabaLLMProvider, AlibabaASRProvider, AlibabaTTSProvider
from .alibaba.multimodal_provider import AlibabaMultiModalProvider
from .deepseek import DeepSeekLLMProvider

def get_provider(provider_name: str, provider_type: str = 'llm', **kwargs):
    """
    获取指定的提供商实例
    
    Args:
        provider_name: 提供商名称
        provider_type: 提供商类型 ('llm', 'asr', 'tts', 'multimodal')
        **kwargs: 提供商初始化参数
        
    Returns:
        提供商实例
        
    Raises:
        ValueError: 不支持的提供商
    """
    if provider_type == 'llm':
        providers = {
            'alibaba': AlibabaLLMProvider,
            'deepseek': DeepSeekLLMProvider,
        }
    elif provider_type == 'asr':
        providers = {
            'alibaba': AlibabaASRProvider,
        }
    elif provider_type == 'tts':
        providers = {
            'alibaba': AlibabaTTSProvider,
        }
    elif provider_type == 'multimodal':
        providers = {
            'alibaba': AlibabaMultiModalProvider,
        }
    else:
        raise ValueError(f"不支持的提供商类型: {provider_type}")
    
    if provider_name not in providers:
        available_providers = list(providers.keys())
        raise ValueError(f"不支持的{provider_type.upper()}提供商: {provider_name}，可用提供商: {available_providers}")
    
    return providers[provider_name](**kwargs)

__all__ = [
    'AlibabaLLMProvider', 
    'AlibabaASRProvider',
    'AlibabaTTSProvider',
    'AlibabaMultiModalProvider',
    'DeepSeekLLMProvider', 
    'get_provider'
] 