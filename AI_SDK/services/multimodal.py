"""
多模态服务
封装多模态提供商的功能，提供统一的接口
"""

from typing import Dict, Any, List, Generator, AsyncGenerator, Union
from ..providers.base import BaseMultiModalProvider


class MultiModalService:
    """多模态服务类"""
    
    def __init__(self, provider: BaseMultiModalProvider):
        """
        初始化多模态服务
        
        Args:
            provider: 多模态提供商实例
        """
        self.provider = provider
    
    def chat_with_image(self, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """
        图像理解对话
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            对话结果字典
        """
        return self.provider.chat_with_image(messages, **kwargs)
    
    async def chat_with_image_async(self, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """
        异步图像理解对话
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            对话结果字典
        """
        return await self.provider.chat_with_image_async(messages, **kwargs)
    
    def chat_with_image_stream(self, messages: List[Dict[str, Any]], **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        流式图像理解对话
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Yields:
            流式对话结果
        """
        for result in self.provider.chat_with_image_stream(messages, **kwargs):
            yield result
    
    async def chat_with_image_stream_async(self, messages: List[Dict[str, Any]], **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """
        异步流式图像理解对话
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Yields:
            流式对话结果
        """
        async for result in self.provider.chat_with_image_stream_async(messages, **kwargs):
            yield result
    
    def chat_with_video(self, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """
        视频理解对话
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            对话结果字典
        """
        return self.provider.chat_with_video(messages, **kwargs)
    
    async def chat_with_video_async(self, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """
        异步视频理解对话
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            对话结果字典
        """
        return await self.provider.chat_with_video_async(messages, **kwargs)
    
    def analyze_image(self, image_path: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        分析单张图像
        
        Args:
            image_path: 图像路径或URL
            prompt: 分析提示
            **kwargs: 其他参数
            
        Returns:
            分析结果字典
        """
        return self.provider.analyze_image(image_path, prompt, **kwargs)
    
    def analyze_multiple_images(self, image_paths: List[str], prompt: str, **kwargs) -> Dict[str, Any]:
        """
        分析多张图像
        
        Args:
            image_paths: 图像路径或URL列表
            prompt: 分析提示
            **kwargs: 其他参数
            
        Returns:
            分析结果字典
        """
        return self.provider.analyze_multiple_images(image_paths, prompt, **kwargs)
    
    def analyze_video(self, video_path: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        分析视频
        
        Args:
            video_path: 视频路径或URL
            prompt: 分析提示
            **kwargs: 其他参数
            
        Returns:
            分析结果字典
        """
        return self.provider.analyze_video(video_path, prompt, **kwargs) 