"""
DeepSeek LLM适配器
"""

import json
import asyncio
import aiohttp
import requests
from typing import Dict, Any, Iterator, AsyncIterator
from ..base import BaseLLMProvider
from ...utils.exceptions import APIException, ModelException
from ...utils.helpers import sanitize_prompt, merge_params

class DeepSeekLLMProvider(BaseLLMProvider):
    """
    DeepSeek LLM适配器 - 使用OpenAI兼容API格式
    """
    
    def __init__(self, api_key: str, config: Dict[str, Any] = None):
        """
        初始化DeepSeek LLM适配器
        
        Args:
            api_key: DeepSeek API密钥
            config: 配置参数
        """
        super().__init__(api_key, config)
        # 使用DeepSeek的OpenAI兼容端点
        self.base_url = "https://api.deepseek.com"
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
            raise Exception(f"DeepSeek API调用失败: {str(e)}")
    
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
            raise Exception(f"DeepSeek API异步调用失败: {str(e)}")
    
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
            raise Exception(f"DeepSeek流式API调用失败: {str(e)}")
    
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
            raise Exception(f"DeepSeek异步流式API调用失败: {str(e)}")
    
    def validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证和清理参数
        
        Args:
            params: 输入参数
            
        Returns:
            清理后的参数
        """
        # DeepSeek支持的参数
        supported_params = {
            'temperature', 'max_tokens', 'top_p', 'frequency_penalty', 
            'presence_penalty', 'stop', 'stream', 'system_prompt'
        }
        
        # 过滤不支持的参数
        cleaned_params = {k: v for k, v in params.items() if k in supported_params}
        
        # 参数范围验证
        if 'temperature' in cleaned_params:
            cleaned_params['temperature'] = max(0.0, min(2.0, cleaned_params['temperature']))
        
        if 'top_p' in cleaned_params:
            cleaned_params['top_p'] = max(0.0, min(1.0, cleaned_params['top_p']))
        
        if 'max_tokens' in cleaned_params:
            cleaned_params['max_tokens'] = max(1, min(4096, cleaned_params['max_tokens']))
        
        return cleaned_params 