"""
TTS服务
封装TTS提供商的功能，提供统一的接口
"""

from typing import Dict, Any, Generator, AsyncGenerator
from ..providers.base import BaseTTSProvider


class TTSService:
    """TTS服务类"""
    
    def __init__(self, provider: BaseTTSProvider):
        """
        初始化TTS服务
        
        Args:
            provider: TTS提供商实例
        """
        self.provider = provider
    
    def synthesize_to_file(self, text: str, output_file: str, **kwargs) -> Dict[str, Any]:
        """
        合成语音并保存到文件
        
        Args:
            text: 要合成的文本
            output_file: 输出文件路径
            **kwargs: 其他参数
            
        Returns:
            合成结果字典
        """
        return self.provider.synthesize_to_file(text, output_file, **kwargs)
    
    async def synthesize_to_file_async(self, text: str, output_file: str, **kwargs) -> Dict[str, Any]:
        """
        异步合成语音并保存到文件
        
        Args:
            text: 要合成的文本
            output_file: 输出文件路径
            **kwargs: 其他参数
            
        Returns:
            合成结果字典
        """
        return await self.provider.synthesize_to_file_async(text, output_file, **kwargs)
    
    def synthesize_to_speaker(self, text: str, **kwargs) -> Dict[str, Any]:
        """
        合成语音并通过扬声器播放
        
        Args:
            text: 要合成的文本
            **kwargs: 其他参数
            
        Returns:
            播放结果字典
        """
        return self.provider.synthesize_to_speaker(text, **kwargs)
    
    async def synthesize_to_speaker_async(self, text: str, **kwargs) -> Dict[str, Any]:
        """
        异步合成语音并通过扬声器播放
        
        Args:
            text: 要合成的文本
            **kwargs: 其他参数
            
        Returns:
            播放结果字典
        """
        return await self.provider.synthesize_to_speaker_async(text, **kwargs)
    
    def synthesize_stream(self, text_stream, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        流式文本转语音
        
        Args:
            text_stream: 文本流
            **kwargs: 其他参数
            
        Yields:
            流式合成结果
        """
        for result in self.provider.synthesize_stream(text_stream, **kwargs):
            yield result
    
    async def synthesize_stream_async(self, text_stream, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """
        异步流式文本转语音
        
        Args:
            text_stream: 文本流
            **kwargs: 其他参数
            
        Yields:
            流式合成结果
        """
        async for result in self.provider.synthesize_stream_async(text_stream, **kwargs):
            yield result
    
    def create_streaming_synthesizer(self, **kwargs):
        """
        创建流式语音合成器
        
        Args:
            **kwargs: 其他参数
            
        Returns:
            流式合成器实例
        """
        return self.provider.streaming_synthesize(**kwargs) 