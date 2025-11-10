"""
ASR服务层
提供统一的语音识别接口
"""

from typing import Dict, Any, Generator, AsyncGenerator, Optional
from ..providers.base import BaseASRProvider
from ..utils.helpers import format_asr_response


class ASRService:
    """ASR服务类"""
    
    def __init__(self, provider: BaseASRProvider):
        """
        初始化ASR服务
        
        Args:
            provider: ASR提供商实例
        """
        self.provider = provider
    
    def recognize_file(self, audio_file: str, **kwargs) -> Dict[str, Any]:
        """
        识别音频文件
        
        Args:
            audio_file: 音频文件路径
            **kwargs: 其他参数
            
        Returns:
            识别结果
        """
        try:
            result = self.provider.recognize_file(audio_file, **kwargs)
            return format_asr_response(result)
        except Exception as e:
            return {
                'success': False,
                'error': f"文件识别失败: {str(e)}",
                'text': '',
                'confidence': 0.0
            }
    
    async def recognize_file_async(self, audio_file: str, **kwargs) -> Dict[str, Any]:
        """
        异步识别音频文件
        
        Args:
            audio_file: 音频文件路径
            **kwargs: 其他参数
            
        Returns:
            识别结果
        """
        try:
            result = await self.provider.recognize_file_async(audio_file, **kwargs)
            return format_asr_response(result)
        except Exception as e:
            return {
                'success': False,
                'error': f"异步文件识别失败: {str(e)}",
                'text': '',
                'confidence': 0.0
            }
    
    def recognize_stream(self, audio_stream, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        实时语音识别
        
        Args:
            audio_stream: 音频流
            **kwargs: 其他参数
            
        Yields:
            识别结果
        """
        try:
            for result in self.provider.recognize_stream(audio_stream, **kwargs):
                yield format_asr_response(result)
        except Exception as e:
            yield {
                'success': False,
                'error': f"流式识别失败: {str(e)}",
                'text': '',
                'confidence': 0.0,
                'is_final': False
            }
    
    async def recognize_stream_async(self, audio_stream, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """
        异步实时语音识别
        
        Args:
            audio_stream: 音频流
            **kwargs: 其他参数
            
        Yields:
            识别结果
        """
        try:
            async for result in self.provider.recognize_stream_async(audio_stream, **kwargs):
                yield format_asr_response(result)
        except Exception as e:
            yield {
                'success': False,
                'error': f"异步流式识别失败: {str(e)}",
                'text': '',
                'confidence': 0.0,
                'is_final': False
            }
    
    def recognize_microphone(self, duration: int = 5, **kwargs) -> Dict[str, Any]:
        """
        识别麦克风音频
        
        Args:
            duration: 录音时长（秒）
            **kwargs: 其他参数
            
        Returns:
            识别结果
        """
        try:
            result = self.provider.recognize_microphone(duration, **kwargs)
            return format_asr_response(result)
        except Exception as e:
            return {
                'success': False,
                'error': f"麦克风识别失败: {str(e)}",
                'text': '',
                'confidence': 0.0
            }
    
    def keyword_spotting(self, keywords: list, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        关键词识别唤醒
        
        Args:
            keywords: 关键词列表
            **kwargs: 其他参数
            
        Yields:
            检测结果
        """
        try:
            for result in self.provider.keyword_spotting(keywords, **kwargs):
                yield format_asr_response(result, is_keyword=True)
        except Exception as e:
            yield {
                'success': False,
                'error': f"关键词检测失败: {str(e)}",
                'keyword_detected': '',
                'text': '',
                'confidence': 0.0
            } 