"""
阿里云LLM适配器
"""

import json
import asyncio
import aiohttp
import requests
from typing import Dict, Any, Iterator, AsyncIterator
from ..base import BaseLLMProvider
from ...utils.exceptions import APIException, ModelException
from ...utils.helpers import sanitize_prompt, merge_params
import logging

logger = logging.getLogger(__name__)

class AlibabaLLMProvider(BaseLLMProvider):
    """
    阿里云LLM适配器 - 使用OpenAI兼容API格式
    """
    
    def __init__(self, api_key: str, config: Dict[str, Any] = None):
        """
        初始化阿里云LLM适配器
        
        Args:
            api_key: 阿里云API密钥
            config: 配置参数
        """
        super().__init__(api_key, config)
        # 使用阿里云的OpenAI兼容端点
        self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def _build_payload(self, model: str, prompt: str, stream: bool = False, **kwargs) -> Dict[str, Any]:
        """
        构建请求载荷
        
        Args:
            model: 模型名称
            prompt: 提示词
            stream: 是否流式输出
            **kwargs: 其他参数
            
        Returns:
            请求载荷
        """
        # 默认参数
        default_params = {
            'temperature': 0.7,
            'max_tokens': 2000,
            'top_p': 0.8,
        }
        
        # 合并用户参数
        params = merge_params(default_params, kwargs)
        
        # 构建OpenAI兼容的消息格式
        messages = []
        
        # 如果有系统提示词
        if 'system_prompt' in params:
            messages.append({
                "role": "system",
                "content": params.pop('system_prompt')
            })
        
        # 添加历史对话记录
        if 'history' in params:
            history = params.pop('history')
            if history and isinstance(history, list):
                for msg in history:
                    if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                        messages.append({
                            "role": msg['role'],
                            "content": msg['content']
                        })
        
        # 添加当前用户消息
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        # 构建请求载荷
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "temperature": params.get('temperature', 0.7),
            "max_tokens": params.get('max_tokens', 2000),
            "top_p": params.get('top_p', 0.8)
        }
        
        return payload
    
    def chat(self, model: str, prompt: str, **kwargs) -> str:
        """
        聊天对话
        
        Args:
            model: 模型名称
            prompt: 提示词
            **kwargs: 其他参数
            
        Returns:
            响应内容
        """
        try:
            payload = self._build_payload(model, prompt, stream=False, **kwargs)
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            response.raise_for_status()
            result = response.json()
            
            return result['choices'][0]['message']['content']
            
        except Exception as e:
            raise Exception(f"阿里云API调用失败: {str(e)}")
    
    async def chat_async(self, model: str, prompt: str, **kwargs) -> str:
        """
        异步聊天对话
        
        Args:
            model: 模型名称
            prompt: 提示词
            **kwargs: 其他参数
            
        Returns:
            响应内容
        """
        try:
            import aiohttp
            
            payload = self._build_payload(model, prompt, stream=False, **kwargs)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    
                    return result['choices'][0]['message']['content']
                    
        except Exception as e:
            raise Exception(f"阿里云API异步调用失败: {str(e)}")
    
    def chat_stream(self, model: str, prompt: str, **kwargs) -> Iterator[str]:
        """
        流式聊天对话（同步）
        
        Args:
            model: 模型名称
            prompt: 提示词
            **kwargs: 其他参数
            
        Yields:
            流式响应内容
        """
        try:
            payload = self._build_payload(model, prompt, stream=True, **kwargs)
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache"
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                stream=True,
                timeout=60
            )
            
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]  # 移除 'data: ' 前缀
                        if data.strip() == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data)
                            if 'choices' in chunk and len(chunk['choices']) > 0:
                                delta = chunk['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    yield delta['content']
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            raise Exception(f"阿里云流式API调用失败: {str(e)}")
    
    async def chat_stream_async(self, model: str, prompt: str, **kwargs) -> AsyncIterator[str]:
        """
        流式聊天对话（异步）
        
        Args:
            model: 模型名称
            prompt: 提示词
            **kwargs: 其他参数
            
        Yields:
            流式响应内容
        """
        try:
            import aiohttp
            
            payload = self._build_payload(model, prompt, stream=True, **kwargs)
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    response.raise_for_status()
                    
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if line.startswith('data: '):
                            data = line[6:]  # 移除 'data: ' 前缀
                            if data.strip() == '[DONE]':
                                break
                            try:
                                chunk = json.loads(data)
                                if 'choices' in chunk and len(chunk['choices']) > 0:
                                    delta = chunk['choices'][0].get('delta', {})
                                    if 'content' in delta:
                                        yield delta['content']
                            except json.JSONDecodeError:
                                continue
                                
        except Exception as e:
            raise Exception(f"阿里云异步流式API调用失败: {str(e)}")
    
    def validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证阿里云特定参数
        
        Args:
            params: 输入参数
            
        Returns:
            验证后的参数
        """
        # 验证温度参数
        if 'temperature' in params:
            temp = params['temperature']
            if not 0 <= temp <= 2:
                raise ModelException("temperature", "温度参数必须在0-2之间")
        
        # 验证top_p参数
        if 'top_p' in params:
            top_p = params['top_p']
            if not 0 < top_p <= 1:
                raise ModelException("top_p", "top_p参数必须在0-1之间")
        
        # 验证max_tokens参数
        if 'max_tokens' in params:
            max_tokens = params['max_tokens']
            if not 1 <= max_tokens <= 6000:
                raise ModelException("max_tokens", "max_tokens参数必须在1-6000之间")
        
        return params 