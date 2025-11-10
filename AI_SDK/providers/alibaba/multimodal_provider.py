"""
阿里云多模态提供商
使用DashScope SDK实现多模态功能
支持通义千问VL模型的图像和视频理解
"""

import os
import time
import base64
import asyncio
import concurrent.futures
from typing import Dict, Any, List, Generator, AsyncGenerator, Union, Optional
from ..base import BaseMultiModalProvider

try:
    import dashscope
    from dashscope import MultiModalConversation
    from openai import OpenAI
    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False


class AlibabaMultiModalProvider(BaseMultiModalProvider):
    """阿里云多模态提供商"""
    
    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        
        if not DASHSCOPE_AVAILABLE:
            raise ImportError("请安装 dashscope 和 openai: pip install dashscope openai")
        
        # 设置API Key
        dashscope.api_key = api_key
        
        # 初始化OpenAI客户端（用于兼容模式）
        self.openai_client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        
        # 默认参数
        self.default_model = kwargs.get('model', 'qwen-vl-max-latest')
        self.default_temperature = kwargs.get('temperature', 0.7)
        self.default_max_tokens = kwargs.get('max_tokens', 2048)
        
        # 支持的模型
        self.vl_models = [
            'qwen-vl-max', 'qwen-vl-max-latest', 'qwen-vl-max-2025-04-08',
            'qwen-vl-max-2025-04-02', 'qwen-vl-max-2025-01-25', 'qwen-vl-max-2024-12-30',
            'qwen-vl-max-2024-11-19', 'qwen-vl-max-2024-10-30', 'qwen-vl-max-2024-08-09',
            'qwen-vl-plus', 'qwen-vl-plus-latest', 'qwen-vl-plus-2025-05-07',
            'qwen-vl-plus-2025-01-25', 'qwen-vl-plus-2025-01-02', 'qwen-vl-plus-2024-08-09',
            'qwen-vl-plus-2023-12-01'
        ]
        
        # 支持的图像格式
        self.supported_image_formats = [
            '.bmp', '.dib', '.icns', '.ico', '.jfif', '.jpe', '.jpeg', '.jpg',
            '.j2c', '.j2k', '.jp2', '.jpc', '.jpf', '.jpx', '.apng', '.png',
            '.bw', '.rgb', '.rgba', '.sgi', '.tif', '.tiff', '.webp'
        ]
        
        # 支持的视频格式
        self.supported_video_formats = [
            '.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv'
        ]
    
    def _encode_image_to_base64(self, image_path: str) -> str:
        """将图像文件编码为Base64格式"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        except Exception as e:
            raise Exception(f"图像编码失败: {str(e)}")
    
    def _get_image_content_type(self, image_path: str) -> str:
        """根据文件扩展名获取Content Type"""
        ext = os.path.splitext(image_path)[1].lower()
        content_type_map = {
            '.bmp': 'image/bmp', '.dib': 'image/bmp', '.icns': 'image/icns',
            '.ico': 'image/x-icon', '.jfif': 'image/jpeg', '.jpe': 'image/jpeg',
            '.jpeg': 'image/jpeg', '.jpg': 'image/jpeg', '.j2c': 'image/jp2',
            '.j2k': 'image/jp2', '.jp2': 'image/jp2', '.jpc': 'image/jp2',
            '.jpf': 'image/jp2', '.jpx': 'image/jp2', '.apng': 'image/png',
            '.png': 'image/png', '.bw': 'image/sgi', '.rgb': 'image/sgi',
            '.rgba': 'image/sgi', '.sgi': 'image/sgi', '.tif': 'image/tiff',
            '.tiff': 'image/tiff', '.webp': 'image/webp'
        }
        return content_type_map.get(ext, 'image/jpeg')
    
    def _prepare_image_content(self, image_input: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """准备图像内容"""
        if isinstance(image_input, str):
            # 字符串输入，可能是URL或本地路径
            if image_input.startswith(('http://', 'https://')):
                # URL
                return {
                    "type": "image_url",
                    "image_url": {"url": image_input}
                }
            else:
                # 本地文件路径
                base64_image = self._encode_image_to_base64(image_input)
                content_type = self._get_image_content_type(image_input)
                return {
                    "type": "image_url",
                    "image_url": {"url": f"data:{content_type};base64,{base64_image}"}
                }
        elif isinstance(image_input, dict):
            # 字典输入，直接返回
            return image_input
        else:
            raise ValueError(f"不支持的图像输入类型: {type(image_input)}")
    
    def _prepare_video_content(self, video_input: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """准备视频内容"""
        if isinstance(video_input, str):
            # 字符串输入，可能是URL或本地路径
            if video_input.startswith(('http://', 'https://')):
                # URL
                return {
                    "type": "video_url",
                    "video_url": {"url": video_input}
                }
            else:
                # 本地文件路径
                with open(video_input, "rb") as video_file:
                    base64_video = base64.b64encode(video_file.read()).decode("utf-8")
                return {
                    "type": "video_url",
                    "video_url": {"url": f"data:video/mp4;base64,{base64_video}"}
                }
        elif isinstance(video_input, dict):
            # 字典输入，直接返回
            return video_input
        else:
            raise ValueError(f"不支持的视频输入类型: {type(video_input)}")
    
    def chat_with_image(self, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """图像理解对话"""
        try:
            model = kwargs.get('model', self.default_model)
            temperature = kwargs.get('temperature', self.default_temperature)
            max_tokens = kwargs.get('max_tokens', self.default_max_tokens)
            use_openai_format = kwargs.get('use_openai_format', True)
            
            start_time = time.time()
            
            if use_openai_format:
                # 使用OpenAI兼容格式
                completion = self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                response = {
                    'choices': [{
                        'message': {
                            'content': completion.choices[0].message.content,
                            'role': 'assistant'
                        },
                        'finish_reason': completion.choices[0].finish_reason
                    }],
                    'usage': {
                        'prompt_tokens': completion.usage.prompt_tokens,
                        'completion_tokens': completion.usage.completion_tokens,
                        'total_tokens': completion.usage.total_tokens
                    },
                    'model': model,
                    'request_id': completion.id
                }
            else:
                # 使用DashScope原生格式
                response = MultiModalConversation.call(
                    api_key=self.api_key,
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                if response.status_code != 200:
                    return {
                        'success': False,
                        'error': f'API调用失败: {response.message}',
                        'status_code': response.status_code
                    }
                
                response = {
                    'choices': [{
                        'message': {
                            'content': response.output.choices[0].message.content[0]["text"],
                            'role': 'assistant'
                        },
                        'finish_reason': response.output.choices[0].finish_reason
                    }],
                    'usage': response.usage,
                    'model': model,
                    'request_id': response.request_id
                }
            
            processing_time = time.time() - start_time
            
            return {
                'success': True,
                'response': response,
                'model': model,
                'processing_time': processing_time
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"多模态对话失败: {str(e)}"
            }
    
    async def chat_with_image_async(self, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """异步图像理解对话"""
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, self.chat_with_image, messages, **kwargs)
            return result
    
    def chat_with_image_stream(self, messages: List[Dict[str, Any]], **kwargs) -> Generator[Dict[str, Any], None, None]:
        """流式图像理解对话"""
        try:
            model = kwargs.get('model', self.default_model)
            temperature = kwargs.get('temperature', self.default_temperature)
            max_tokens = kwargs.get('max_tokens', self.default_max_tokens)
            
            completion = self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            
            for chunk in completion:
                if chunk.choices[0].delta.content is not None:
                    yield {
                        'choices': [{
                            'delta': {
                                'content': chunk.choices[0].delta.content,
                                'role': 'assistant'
                            },
                            'finish_reason': chunk.choices[0].finish_reason
                        }],
                        'model': model,
                        'id': chunk.id
                    }
                    
        except Exception as e:
            yield {
                'success': False,
                'error': f"流式多模态对话失败: {str(e)}"
            }
    
    async def chat_with_image_stream_async(self, messages: List[Dict[str, Any]], **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """异步流式图像理解对话"""
        # 在线程池中运行同步生成器
        loop = asyncio.get_event_loop()
        
        def sync_generator():
            return list(self.chat_with_image_stream(messages, **kwargs))
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = await loop.run_in_executor(None, sync_generator)
            
            for result in results:
                yield result
    
    def chat_with_video(self, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """视频理解对话"""
        try:
            model = kwargs.get('model', self.default_model)
            temperature = kwargs.get('temperature', self.default_temperature)
            max_tokens = kwargs.get('max_tokens', self.default_max_tokens)
            fps = kwargs.get('fps', 0.5)  # 抽帧频率
            use_openai_format = kwargs.get('use_openai_format', True)
            
            start_time = time.time()
            
            if use_openai_format:
                # 使用OpenAI兼容格式
                completion = self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                response = {
                    'choices': [{
                        'message': {
                            'content': completion.choices[0].message.content,
                            'role': 'assistant'
                        },
                        'finish_reason': completion.choices[0].finish_reason
                    }],
                    'usage': {
                        'prompt_tokens': completion.usage.prompt_tokens,
                        'completion_tokens': completion.usage.completion_tokens,
                        'total_tokens': completion.usage.total_tokens
                    },
                    'model': model,
                    'request_id': completion.id
                }
            else:
                # 使用DashScope原生格式，支持fps参数
                response = MultiModalConversation.call(
                    api_key=self.api_key,
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    fps=fps
                )
                
                if response.status_code != 200:
                    return {
                        'success': False,
                        'error': f'API调用失败: {response.message}',
                        'status_code': response.status_code
                    }
                
                response = {
                    'choices': [{
                        'message': {
                            'content': response.output.choices[0].message.content[0]["text"],
                            'role': 'assistant'
                        },
                        'finish_reason': response.output.choices[0].finish_reason
                    }],
                    'usage': response.usage,
                    'model': model,
                    'request_id': response.request_id
                }
            
            processing_time = time.time() - start_time
            
            return {
                'success': True,
                'response': response,
                'model': model,
                'processing_time': processing_time,
                'fps': fps
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"视频理解对话失败: {str(e)}"
            }
    
    async def chat_with_video_async(self, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """异步视频理解对话"""
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, self.chat_with_video, messages, **kwargs)
            return result
    
    def analyze_image(self, image_path: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """分析单张图像"""
        try:
            # 准备消息
            image_content = self._prepare_image_content(image_path)
            
            messages = [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": "You are a helpful assistant."}]
                },
                {
                    "role": "user",
                    "content": [
                        image_content,
                        {"type": "text", "text": prompt}
                    ]
                }
            ]
            
            return self.chat_with_image(messages, **kwargs)
            
        except Exception as e:
            return {
                'success': False,
                'error': f"图像分析失败: {str(e)}"
            }
    
    def analyze_multiple_images(self, image_paths: List[str], prompt: str, **kwargs) -> Dict[str, Any]:
        """分析多张图像"""
        try:
            # 准备图像内容
            content = []
            for image_path in image_paths:
                content.append(self._prepare_image_content(image_path))
            
            # 添加文本提示
            content.append({"type": "text", "text": prompt})
            
            messages = [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": "You are a helpful assistant."}]
                },
                {
                    "role": "user",
                    "content": content
                }
            ]
            
            return self.chat_with_image(messages, **kwargs)
            
        except Exception as e:
            return {
                'success': False,
                'error': f"多图像分析失败: {str(e)}"
            }
    
    def analyze_video(self, video_path: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """分析视频"""
        try:
            # 准备消息
            video_content = self._prepare_video_content(video_path)
            
            messages = [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": "You are a helpful assistant."}]
                },
                {
                    "role": "user",
                    "content": [
                        video_content,
                        {"type": "text", "text": prompt}
                    ]
                }
            ]
            
            return self.chat_with_video(messages, **kwargs)
            
        except Exception as e:
            return {
                'success': False,
                'error': f"视频分析失败: {str(e)}"
            } 