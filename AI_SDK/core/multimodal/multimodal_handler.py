"""
多模态处理器
负责处理所有多模态相关的功能
"""

from typing import Dict, Any, List, Generator, AsyncGenerator, Union
from ...services.multimodal import MultiModalService
from ...providers import get_provider
from ...utils.exceptions import ConfigException


class MultiModalHandler:
    """多模态功能处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化多模态处理器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self._multimodal_services = {}  # 多模态服务缓存
    
    def _get_multimodal_service(self, provider: str) -> MultiModalService:
        """获取多模态服务实例（带缓存）"""
        if provider not in self._multimodal_services:
            # 获取提供商配置
            provider_config = self.config.get('providers', {}).get(provider, {})
            if not provider_config:
                raise ConfigException(f"未找到提供商配置: {provider}")
            
            api_key = provider_config.get('api_key')
            if not api_key:
                raise ConfigException(f"提供商 {provider} 缺少API密钥")
            
            # 创建多模态提供商实例
            # 从provider_config中移除api_key，避免重复传递
            config_without_api_key = {k: v for k, v in provider_config.items() if k != 'api_key'}
            multimodal_provider = get_provider(provider, 'multimodal', api_key=api_key, **config_without_api_key)
            
            # 创建多模态服务
            self._multimodal_services[provider] = MultiModalService(multimodal_provider)
        
        return self._multimodal_services[provider]
    
    def chat_with_image(self, provider: str, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """
        图像理解对话
        
        Args:
            provider: 多模态提供商名称
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            对话结果字典
        """
        multimodal_service = self._get_multimodal_service(provider)
        return multimodal_service.chat_with_image(messages, **kwargs)
    
    async def chat_with_image_async(self, provider: str, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """
        异步图像理解对话
        
        Args:
            provider: 多模态提供商名称
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            对话结果字典
        """
        multimodal_service = self._get_multimodal_service(provider)
        return await multimodal_service.chat_with_image_async(messages, **kwargs)
    
    def chat_with_image_stream(self, provider: str, messages: List[Dict[str, Any]], **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        流式图像理解对话
        
        Args:
            provider: 多模态提供商名称
            messages: 消息列表
            **kwargs: 其他参数
            
        Yields:
            流式对话结果
        """
        multimodal_service = self._get_multimodal_service(provider)
        for result in multimodal_service.chat_with_image_stream(messages, **kwargs):
            yield result
    
    async def chat_with_image_stream_async(self, provider: str, messages: List[Dict[str, Any]], **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """
        异步流式图像理解对话
        
        Args:
            provider: 多模态提供商名称
            messages: 消息列表
            **kwargs: 其他参数
            
        Yields:
            流式对话结果
        """
        multimodal_service = self._get_multimodal_service(provider)
        async for result in multimodal_service.chat_with_image_stream_async(messages, **kwargs):
            yield result
    
    def chat_with_video(self, provider: str, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """
        视频理解对话
        
        Args:
            provider: 多模态提供商名称
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            对话结果字典
        """
        multimodal_service = self._get_multimodal_service(provider)
        return multimodal_service.chat_with_video(messages, **kwargs)
    
    async def chat_with_video_async(self, provider: str, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """
        异步视频理解对话
        
        Args:
            provider: 多模态提供商名称
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            对话结果字典
        """
        multimodal_service = self._get_multimodal_service(provider)
        return await multimodal_service.chat_with_video_async(messages, **kwargs)
    
    def analyze_image(self, provider: str, image_path: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        分析单张图像
        
        Args:
            provider: 多模态提供商名称
            image_path: 图像路径或URL
            prompt: 分析提示
            **kwargs: 其他参数
            
        Returns:
            分析结果字典
        """
        multimodal_service = self._get_multimodal_service(provider)
        return multimodal_service.analyze_image(image_path, prompt, **kwargs)
    
    def analyze_multiple_images(self, provider: str, image_paths: List[str], prompt: str, **kwargs) -> Dict[str, Any]:
        """
        分析多张图像
        
        Args:
            provider: 多模态提供商名称
            image_paths: 图像路径或URL列表
            prompt: 分析提示
            **kwargs: 其他参数
            
        Returns:
            分析结果字典
        """
        multimodal_service = self._get_multimodal_service(provider)
        return multimodal_service.analyze_multiple_images(image_paths, prompt, **kwargs)
    
    def analyze_video(self, provider: str, video_path: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        分析视频
        
        Args:
            provider: 多模态提供商名称
            video_path: 视频路径或URL
            prompt: 分析提示
            **kwargs: 其他参数
            
        Returns:
            分析结果字典
        """
        multimodal_service = self._get_multimodal_service(provider)
        return multimodal_service.analyze_video(video_path, prompt, **kwargs)
    
    async def analyze_image_async(self, provider: str, image_path: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        异步分析单张图像
        
        Args:
            provider: 多模态提供商名称
            image_path: 图像路径或URL
            prompt: 分析提示
            **kwargs: 其他参数
            
        Returns:
            分析结果字典
        """
        multimodal_service = self._get_multimodal_service(provider)
        # 使用线程池执行同步方法
        import asyncio
        import concurrent.futures
        
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(
                executor, 
                lambda: multimodal_service.analyze_image(image_path, prompt, **kwargs)
            )
            return result
    
    async def analyze_multiple_images_async(self, provider: str, image_paths: List[str], prompt: str, **kwargs) -> Dict[str, Any]:
        """
        异步分析多张图像
        
        Args:
            provider: 多模态提供商名称
            image_paths: 图像路径或URL列表
            prompt: 分析提示
            **kwargs: 其他参数
            
        Returns:
            分析结果字典
        """
        multimodal_service = self._get_multimodal_service(provider)
        # 使用线程池执行同步方法
        import asyncio
        import concurrent.futures
        
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(
                executor, 
                lambda: multimodal_service.analyze_multiple_images(image_paths, prompt, **kwargs)
            )
            return result
    
    async def analyze_video_async(self, provider: str, video_path: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        异步分析视频
        
        Args:
            provider: 多模态提供商名称
            video_path: 视频路径或URL
            prompt: 分析提示
            **kwargs: 其他参数
            
        Returns:
            分析结果字典
        """
        multimodal_service = self._get_multimodal_service(provider)
        # 使用线程池执行同步方法
        import asyncio
        import concurrent.futures
        
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(
                executor, 
                lambda: multimodal_service.analyze_video(video_path, prompt, **kwargs)
            )
            return result
    
    def clear_cache(self):
        """清空多模态服务缓存"""
        self._multimodal_services.clear() 