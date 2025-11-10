"""
辅助函数模块
"""

import time
import re
from typing import Dict, Any, Optional, Union
from .exceptions import ValidationException

def format_response(content: str, provider: str, model: str, is_stream: bool = False) -> Dict[str, Any]:
    """
    格式化响应结果为统一格式
    
    Args:
        content: 响应内容（字符串）
        provider: 提供商名称
        model: 模型名称
        is_stream: 是否为流式响应
        
    Returns:
        格式化的响应字典
    """
    current_time = int(time.time())
    
    if is_stream:
        # 流式响应格式
        return {
            "id": f"chatcmpl-{current_time}",
            "object": "chat.completion.chunk",
            "created": current_time,
            "model": model,
            "provider": provider,
            "choices": [{
                "index": 0,
                "delta": {
                    "content": content
                },
                "finish_reason": None
            }]
        }
    else:
        # 普通响应格式
        return {
            "id": f"chatcmpl-{current_time}",
            "object": "chat.completion",
            "created": current_time,
            "model": model,
            "provider": provider,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 0,  # 这里可以后续添加token计算
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }

def format_asr_response(result: Dict[str, Any], is_keyword: bool = False) -> Dict[str, Any]:
    """
    格式化ASR响应结果
    
    Args:
        result: 原始ASR结果
        is_keyword: 是否为关键词检测结果
        
    Returns:
        格式化的ASR响应
    """
    current_time = int(time.time())
    
    # 基础响应格式
    formatted_response = {
        "id": f"asr-{current_time}",
        "object": "speech.recognition",
        "created": current_time,
        "success": result.get('success', False),
        "text": result.get('text', ''),
        "confidence": result.get('confidence', 0.0)
    }
    
    # 添加错误信息
    if not result.get('success', False):
        formatted_response['error'] = result.get('error', '未知错误')
    
    # 关键词检测特有字段
    if is_keyword:
        formatted_response.update({
            "keyword_detected": result.get('keyword_detected', ''),
            "timestamp": result.get('timestamp', current_time)
        })
    
    # 流式识别特有字段
    if 'is_final' in result:
        formatted_response.update({
            "is_final": result.get('is_final', False),
            "begin_time": result.get('begin_time', 0),
            "end_time": result.get('end_time', 0)
        })
    
    # 详细信息（可选）
    if result.get('words'):
        formatted_response['words'] = result['words']
    
    if result.get('sentences'):
        formatted_response['sentences'] = result['sentences']
    
    if result.get('speaker_info'):
        formatted_response['speaker_info'] = result['speaker_info']
    
    if result.get('audio_duration'):
        formatted_response['audio_duration'] = result['audio_duration']
    
    if result.get('processing_time'):
        formatted_response['processing_time'] = result['processing_time']
    
    return formatted_response

def validate_params(params: Dict[str, Any], required_params: list = None, 
                   allowed_params: list = None) -> Dict[str, Any]:
    """
    验证参数
    
    Args:
        params: 输入参数
        required_params: 必需参数列表
        allowed_params: 允许的参数列表
        
    Returns:
        验证后的参数
        
    Raises:
        ValidationException: 参数验证失败
    """
    if required_params:
        missing_params = [param for param in required_params if param not in params]
        if missing_params:
            raise ValidationException(f"缺少必需参数: {', '.join(missing_params)}")
    
    if allowed_params:
        invalid_params = [param for param in params.keys() if param not in allowed_params]
        if invalid_params:
            raise ValidationException(f"不支持的参数: {', '.join(invalid_params)}")
    
    return params

def merge_params(default_params: Dict[str, Any], user_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    合并默认参数和用户参数
    
    Args:
        default_params: 默认参数
        user_params: 用户参数
        
    Returns:
        合并后的参数
    """
    merged = default_params.copy()
    merged.update(user_params)
    return merged

def sanitize_prompt(prompt: str) -> str:
    """
    清理和验证提示词
    
    Args:
        prompt: 原始提示词
        
    Returns:
        清理后的提示词
    """
    if not prompt or not isinstance(prompt, str):
        raise ValueError("提示词不能为空且必须是字符串")
    
    # 移除多余的空白字符
    prompt = re.sub(r'\s+', ' ', prompt.strip())
    
    # 检查长度限制
    if len(prompt) > 10000:
        raise ValueError("提示词长度不能超过10000字符")
    
    return prompt

def get_error_message(error: Exception, provider: str = None) -> str:
    """
    获取友好的错误消息
    
    Args:
        error: 异常对象
        provider: 厂商名称
        
    Returns:
        错误消息
    """
    if provider:
        return f"[{provider}] {str(error)}"
    return str(error)

def validate_model_config(model: str, provider_config: Dict[str, Any]) -> bool:
    """
    验证模型配置
    
    Args:
        model: 模型名称
        provider_config: 提供商配置
        
    Returns:
        验证结果
        
    Raises:
        ValidationException: 验证失败时抛出
    """
    models = provider_config.get('models', {})
    if model not in models:
        available_models = list(models.keys())
        raise ValidationException(f"模型 {model} 不可用。可用模型: {available_models}")
    
    model_config = models[model]
    if not model_config.get('enabled', True):
        raise ValidationException(f"模型 {model} 已被禁用")
    
    return True

def calculate_tokens(text: str) -> int:
    """
    简单的token计算（估算）
    
    Args:
        text: 文本内容
        
    Returns:
        估算的token数量
    """
    # 简单估算：中文字符按1个token计算，英文单词按0.75个token计算
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))
    
    return chinese_chars + int(english_words * 0.75)

def extract_content_from_response(response: Dict[str, Any], provider: str) -> str:
    """
    从不同提供商的响应中提取内容
    
    Args:
        response: 原始响应
        provider: 提供商名称
        
    Returns:
        提取的内容
    """
    try:
        if provider == 'alibaba':
            # 阿里云响应格式
            if 'output' in response and 'choices' in response['output']:
                choices = response['output']['choices']
                if choices and len(choices) > 0:
                    return choices[0]['message']['content']
        elif provider == 'deepseek':
            # DeepSeek响应格式
            if 'choices' in response and len(response['choices']) > 0:
                return response['choices'][0]['message']['content']
        
        # 如果无法提取，返回原始响应的字符串表示
        return str(response)
        
    except (KeyError, IndexError, TypeError):
        return str(response) 