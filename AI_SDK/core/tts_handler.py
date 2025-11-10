"""
TTS处理器
负责处理所有语音合成相关的功能
"""

from typing import Dict, Any, Generator, AsyncGenerator
from ..services.tts import TTSService
from ..providers import get_provider
from ..utils.exceptions import ConfigException


class TTSHandler:
    """TTS功能处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化TTS处理器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self._tts_services = {}  # TTS服务缓存
    
    def _get_tts_service(self, provider: str) -> TTSService:
        """获取TTS服务实例（带缓存）"""
        if provider not in self._tts_services:
            # 获取提供商配置
            provider_config = self.config.get('providers', {}).get(provider, {})
            if not provider_config:
                raise ConfigException(f"未找到提供商配置: {provider}")
            
            api_key = provider_config.get('api_key')
            if not api_key:
                raise ConfigException(f"提供商 {provider} 缺少API密钥")
            
            # 创建TTS提供商实例
            # 从provider_config中移除api_key，避免重复传递
            config_without_api_key = {k: v for k, v in provider_config.items() if k != 'api_key'}
            tts_provider = get_provider(provider, 'tts', api_key=api_key, **config_without_api_key)
            
            # 创建TTS服务
            self._tts_services[provider] = TTSService(tts_provider)
        
        return self._tts_services[provider]
    
    def synthesize_to_file(self, provider: str, text: str, output_file: str, **kwargs) -> Dict[str, Any]:
        """
        合成语音并保存到文件
        
        Args:
            provider: TTS提供商名称
            text: 要合成的文本
            output_file: 输出文件路径
            **kwargs: 其他参数
            
        Returns:
            合成结果字典
        """
        tts_service = self._get_tts_service(provider)
        return tts_service.synthesize_to_file(text, output_file, **kwargs)
    
    async def synthesize_to_file_async(self, provider: str, text: str, output_file: str, **kwargs) -> Dict[str, Any]:
        """
        异步合成语音并保存到文件
        
        Args:
            provider: TTS提供商名称
            text: 要合成的文本
            output_file: 输出文件路径
            **kwargs: 其他参数
            
        Returns:
            合成结果字典
        """
        tts_service = self._get_tts_service(provider)
        return await tts_service.synthesize_to_file_async(text, output_file, **kwargs)
    
    def synthesize_to_speaker(self, provider: str, text: str, **kwargs) -> Dict[str, Any]:
        """
        合成语音并通过扬声器播放
        
        Args:
            provider: TTS提供商名称
            text: 要合成的文本
            **kwargs: 其他参数
            
        Returns:
            播放结果字典
        """
        tts_service = self._get_tts_service(provider)
        return tts_service.synthesize_to_speaker(text, **kwargs)
    
    async def synthesize_to_speaker_async(self, provider: str, text: str, **kwargs) -> Dict[str, Any]:
        """
        异步合成语音并通过扬声器播放
        
        Args:
            provider: TTS提供商名称
            text: 要合成的文本
            **kwargs: 其他参数
            
        Returns:
            播放结果字典
        """
        tts_service = self._get_tts_service(provider)
        return await tts_service.synthesize_to_speaker_async(text, **kwargs)
    
    def synthesize_stream(self, provider: str, text_stream, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        流式文本转语音
        
        Args:
            provider: TTS提供商名称
            text_stream: 文本流
            **kwargs: 其他参数
            
        Yields:
            流式合成结果
        """
        tts_service = self._get_tts_service(provider)
        for result in tts_service.synthesize_stream(text_stream, **kwargs):
            yield result
    
    async def synthesize_stream_async(self, provider: str, text_stream, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """
        异步流式文本转语音
        
        Args:
            provider: TTS提供商名称
            text_stream: 文本流
            **kwargs: 其他参数
            
        Yields:
            流式合成结果
        """
        tts_service = self._get_tts_service(provider)
        async for result in tts_service.synthesize_stream_async(text_stream, **kwargs):
            yield result
    
    def create_streaming_synthesizer(self, provider: str, **kwargs):
        """
        创建流式语音合成器
        
        Args:
            provider: TTS提供商名称
            **kwargs: 其他参数
            
        Returns:
            流式合成器实例
        """
        tts_service = self._get_tts_service(provider)
        return tts_service.create_streaming_synthesizer(**kwargs)
    
    def clear_cache(self):
        """清空TTS服务缓存"""
        self._tts_services.clear() 