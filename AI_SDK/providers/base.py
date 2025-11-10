"""
基础LLM提供商类
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Iterator, AsyncIterator, Optional, Union, AsyncGenerator, Generator, List
import asyncio


class BaseLLMProvider(ABC):
    """
    LLM提供商基类
    """
    
    def __init__(self, api_key: str, base_url: str = None, **kwargs):
        """
        初始化提供商
        
        Args:
            api_key: API密钥
            base_url: 基础URL
            **kwargs: 其他参数
        """
        self.api_key = api_key
        self.base_url = base_url
        self.kwargs = kwargs
    
    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """同步聊天"""
        pass
    
    @abstractmethod
    async def chat_async(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """异步聊天"""
        pass
    
    @abstractmethod
    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[Dict[str, Any], None, None]:
        """流式聊天"""
        pass
    
    @abstractmethod
    async def chat_stream_async(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """异步流式聊天"""
        pass
    
    @abstractmethod
    def validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证参数
        
        Args:
            params: 输入参数
            
        Returns:
            验证后的参数
        """
        pass

class BaseASRProvider(ABC):
    """ASR提供商基类"""
    
    def __init__(self, api_key: str, base_url: str = None, **kwargs):
        self.api_key = api_key
        self.base_url = base_url
        self.kwargs = kwargs
    
    @abstractmethod
    def recognize_file(self, audio_file: str, **kwargs) -> Dict[str, Any]:
        """识别音频文件"""
        pass
    
    @abstractmethod
    async def recognize_file_async(self, audio_file: str, **kwargs) -> Dict[str, Any]:
        """异步识别音频文件"""
        pass
    
    @abstractmethod
    def recognize_stream(self, audio_stream, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """实时语音识别"""
        pass
    
    @abstractmethod
    async def recognize_stream_async(self, audio_stream, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """异步实时语音识别"""
        pass
    
    @abstractmethod
    def recognize_microphone(self, duration: int = 5, **kwargs) -> Dict[str, Any]:
        """识别麦克风音频"""
        pass
    
    @abstractmethod
    def keyword_spotting(self, keywords: List[str], **kwargs) -> Generator[Dict[str, Any], None, None]:
        """关键词识别唤醒"""
        pass

class BaseTTSProvider(ABC):
    """TTS提供商基类"""
    
    def __init__(self, api_key: str, **kwargs):
        self.api_key = api_key
        self.config = kwargs
    
    @abstractmethod
    def synthesize_to_file(self, text: str, output_file: str, **kwargs) -> Dict[str, Any]:
        """合成语音并保存到文件"""
        pass
    
    @abstractmethod
    async def synthesize_to_file_async(self, text: str, output_file: str, **kwargs) -> Dict[str, Any]:
        """异步合成语音并保存到文件"""
        pass
    
    @abstractmethod
    def synthesize_to_speaker(self, text: str, **kwargs) -> Dict[str, Any]:
        """合成语音并通过扬声器播放"""
        pass
    
    @abstractmethod
    async def synthesize_to_speaker_async(self, text: str, **kwargs) -> Dict[str, Any]:
        """异步合成语音并通过扬声器播放"""
        pass
    
    @abstractmethod
    def synthesize_stream(self, text_stream, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """流式文本转语音"""
        pass
    
    @abstractmethod
    async def synthesize_stream_async(self, text_stream, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """异步流式文本转语音"""
        pass

class BaseMultiModalProvider(ABC):
    """基础多模态提供商抽象类"""
    
    def __init__(self, api_key: str, **kwargs):
        """
        初始化多模态提供商
        
        Args:
            api_key: API密钥
            **kwargs: 其他参数
        """
        self.api_key = api_key
        self.config = kwargs
    
    @abstractmethod
    def chat_with_image(self, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """图像理解对话"""
        pass
    
    @abstractmethod
    async def chat_with_image_async(self, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """异步图像理解对话"""
        pass
    
    @abstractmethod
    def chat_with_image_stream(self, messages: List[Dict[str, Any]], **kwargs) -> Generator[Dict[str, Any], None, None]:
        """流式图像理解对话"""
        pass
    
    @abstractmethod
    async def chat_with_image_stream_async(self, messages: List[Dict[str, Any]], **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """异步流式图像理解对话"""
        pass
    
    @abstractmethod
    def chat_with_video(self, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """视频理解对话"""
        pass
    
    @abstractmethod
    async def chat_with_video_async(self, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """异步视频理解对话"""
        pass
    
    @abstractmethod
    def analyze_image(self, image_path: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """分析单张图像"""
        pass
    
    @abstractmethod
    def analyze_multiple_images(self, image_paths: List[str], prompt: str, **kwargs) -> Dict[str, Any]:
        """分析多张图像"""
        pass
    
    @abstractmethod
    def analyze_video(self, video_path: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """分析视频"""
        pass 