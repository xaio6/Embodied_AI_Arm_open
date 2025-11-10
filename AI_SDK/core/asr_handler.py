"""
ASR处理器
负责处理所有语音识别相关的功能
"""

from typing import Dict, Any, Generator, AsyncGenerator, List
from ..services.asr import ASRService
from ..providers import get_provider
from ..utils.exceptions import ConfigException


class ASRHandler:
    """ASR功能处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化ASR处理器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self._asr_services = {}  # ASR服务缓存
    
    def _get_asr_service(self, provider: str) -> ASRService:
        """获取ASR服务实例（带缓存）"""
        if provider not in self._asr_services:
            # 获取提供商配置
            provider_config = self.config.get('providers', {}).get(provider, {})
            if not provider_config:
                raise ConfigException(f"未找到提供商配置: {provider}")
            
            api_key = provider_config.get('api_key')
            if not api_key:
                raise ConfigException(f"提供商 {provider} 缺少API密钥")
            
            # 创建ASR提供商实例
            # 从provider_config中移除api_key，避免重复传递
            config_without_api_key = {k: v for k, v in provider_config.items() if k != 'api_key'}
            asr_provider = get_provider(provider, 'asr', api_key=api_key, **config_without_api_key)
            
            # 创建ASR服务
            self._asr_services[provider] = ASRService(asr_provider)
        
        return self._asr_services[provider]
    
    def recognize_file(self, provider: str, audio_file: str, **kwargs) -> Dict[str, Any]:
        """
        识别音频文件
        
        Args:
            provider: ASR提供商名称
            audio_file: 音频文件路径
            **kwargs: 其他参数
            
        Returns:
            识别结果字典
        """
        asr_service = self._get_asr_service(provider)
        return asr_service.recognize_file(audio_file, **kwargs)
    
    async def recognize_file_async(self, provider: str, audio_file: str, **kwargs) -> Dict[str, Any]:
        """
        异步识别音频文件
        
        Args:
            provider: ASR提供商名称
            audio_file: 音频文件路径
            **kwargs: 其他参数
            
        Returns:
            识别结果字典
        """
        asr_service = self._get_asr_service(provider)
        return await asr_service.recognize_file_async(audio_file, **kwargs)
    
    def recognize_microphone(self, provider: str, duration: int = 5, **kwargs) -> Dict[str, Any]:
        """
        识别麦克风音频
        
        Args:
            provider: ASR提供商名称
            duration: 录音时长（秒）
            **kwargs: 其他参数
            
        Returns:
            识别结果字典
        """
        asr_service = self._get_asr_service(provider)
        return asr_service.recognize_microphone(duration, **kwargs)
    
    def recognize_stream(self, provider: str, audio_stream, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        实时语音识别
        
        Args:
            provider: ASR提供商名称
            audio_stream: 音频流
            **kwargs: 其他参数
            
        Yields:
            实时识别结果
        """
        asr_service = self._get_asr_service(provider)
        for result in asr_service.recognize_stream(audio_stream, **kwargs):
            yield result
    
    async def recognize_stream_async(self, provider: str, audio_stream, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """
        异步实时语音识别
        
        Args:
            provider: ASR提供商名称
            audio_stream: 音频流
            **kwargs: 其他参数
            
        Yields:
            实时识别结果
        """
        asr_service = self._get_asr_service(provider)
        async for result in asr_service.recognize_stream_async(audio_stream, **kwargs):
            yield result
    
    def keyword_spotting(self, provider: str, keywords: List[str], **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        关键词识别唤醒
        
        Args:
            provider: ASR提供商名称
            keywords: 关键词列表
            **kwargs: 其他参数
            
        Yields:
            关键词检测结果
        """
        asr_service = self._get_asr_service(provider)
        for result in asr_service.keyword_spotting(keywords, **kwargs):
            yield result
    
    def clear_cache(self):
        """清空ASR服务缓存"""
        self._asr_services.clear() 