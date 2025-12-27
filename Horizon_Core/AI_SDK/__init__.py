"""
AI SDK - 多厂商人工智能服务统一调用框架

提供简单易用的统一接口，支持：
- 🤖 多厂商AI模型调用 (阿里云、DeepSeek等)
- 🎤 语音识别 (ASR)
- 🌊 流式输出
- ⚡ 异步调用
- 💬 上下文对话
- 👥 多会话管理
"""

import os
from typing import Iterator, AsyncIterator, Dict, Any, List, Optional, Union, Generator, AsyncGenerator, Tuple
from .core.llm import ChatHandler
from .core.session import ChatSession
from .core.asr import ASRHandler
from .core.tts import TTSHandler
from .core.multimodal import MultiModalHandler
from .core.smart_chat import SmartChatHandler
from .core.smart_chat.multimodal import SmartMultiModalChatHandler
from .core.smart_chat.voice import SmartVoiceChatHandler
from .core.smart_chat.multimodal_voice import SmartMultiModalVoiceChatHandler
from .utils.exceptions import AISDKException, ValidationException, ConfigException
import yaml
import cv2
import numpy as np
import time

__version__ = "1.0.0"
__author__ = "AI SDK Team"

class AISDK:
    """
    AI SDK 主类 - 多厂商人工智能服务统一调用框架
    
    🎯 核心功能：
    - chat(): 统一聊天接口，通过参数控制所有功能
    - asr(): 统一语音识别接口，支持多种识别模式
    - tts(): 统一语音合成接口，支持多种合成模式
    - multimodal(): 统一多模态接口，支持图像和视频理解
    - smart_chat(): LLM + TTS 智能对话，一键实现AI问答并语音播放
    - smart_multimodal_chat(): 多模态智能对话，支持图像、视频、语音等多种输入
    - 支持流式输出、异步调用、上下文对话
    - 自动管理会话和历史记录
    
    📝 使用示例：
        # 基础对话
        response = sdk.chat("alibaba", "qwen-turbo", "你好")
        
        # 流式输出
        for chunk in sdk.chat("alibaba", "qwen-turbo", "你好", stream=True):
            print(chunk['choices'][0]['delta']['content'], end='')
        
        # 上下文对话
        sdk.chat("alibaba", "qwen-turbo", "我叫张三", use_context=True)
        sdk.chat("alibaba", "qwen-turbo", "我叫什么？", use_context=True)
        
        # 语音识别
        result = sdk.asr("alibaba", "file", audio_file="audio.wav")
        result = sdk.asr("alibaba", "microphone", duration=5)
        
        # 语音合成
        result = sdk.tts("alibaba", "file", "你好世界", output_file="output.mp3")
        result = sdk.tts("alibaba", "speaker", "你好世界")
        
        # 多模态理解
        result = sdk.multimodal("alibaba", "image", "描述这张图片", image_path="image.jpg")
        result = sdk.multimodal("alibaba", "video", "分析这个视频", video_path="video.mp4")
        
        # 智能对话（LLM + TTS）
        result = sdk.smart_chat("你好，请介绍一下自己")
        result = sdk.smart_chat("讲个故事", tts_mode="file", output_file="story.mp3")
        
        # 异步调用
        response = await sdk.chat("alibaba", "qwen-turbo", "你好", async_mode=True)
        result = await sdk.smart_chat("你好", async_mode=True)
    """
    
    def __init__(self, config_path: str = None, config_dict: Dict[str, Any] = None):
        """
        初始化AI SDK
        
        Args:
            config_path: 配置文件路径，默认使用config.yaml
            config_dict: 配置字典（与config_path二选一）
        """
        # 加载配置
        if config_path:
            self.config = self._load_config(config_path)
        elif config_dict:
            self.config = config_dict
        else:
            # 优先从外置目录读取（由 run_gui 设置的环境变量）
            default_path = os.environ.get('AISDK_CONFIG_PATH')
            if not default_path:
                ext_dir = os.environ.get('HORIZONARM_CONFIG_DIR')
                if ext_dir:
                    default_path = os.path.join(ext_dir, 'aisdk_config.yaml')
            if not default_path:
                default_path = 'config/aisdk_config.yaml'
            try:
                self.config = self._load_config(default_path)
            except Exception as e:
                raise ConfigException(f"无法加载默认配置文件aisdk_config.yaml: {str(e)}")
        
        # 初始化处理器
        self.chat_handler = ChatHandler(self.config)
        self.asr_handler = ASRHandler(self.config)
        self.tts_handler = TTSHandler(self.config)
        self.multimodal_handler = MultiModalHandler(self.config)
        self.smart_chat_handler = SmartChatHandler(self)
        self.smart_multimodal_chat_handler = SmartMultiModalChatHandler(self)
        self.smart_voice_chat_handler = SmartVoiceChatHandler(self)
        self.smart_multimodal_voice_chat_handler = SmartMultiModalVoiceChatHandler(self)
        
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_content = f.read()
            
            # 替换环境变量
            config_content = self._replace_env_vars(config_content)
            
            # 解析YAML
            config = yaml.safe_load(config_content)
            return config
            
        except FileNotFoundError:
            raise ConfigException(f"配置文件未找到: {config_path}")
        except yaml.YAMLError as e:
            raise ConfigException(f"配置文件格式错误: {e}")
    
    def _replace_env_vars(self, content: str) -> str:
        """替换配置文件中的环境变量"""
        import re
        import os
        
        # 匹配 ${VAR_NAME:default_value} 格式
        pattern = r'\$\{([A-Za-z0-9_]+):?([^}]*)\}'
        
        def replace_var(match):
            var_name = match.group(1)
            default_value = match.group(2)
            return os.getenv(var_name, default_value)
        
        return re.sub(pattern, replace_var, content)
    
    def chat(self, 
             provider: str, 
             model: str, 
             prompt: str,
             stream: bool = False,
             async_mode: bool = False,
             use_context: bool = False,
             session_id: str = None,
             **kwargs) -> Union[Dict[str, Any], Iterator[Dict[str, Any]], AsyncIterator[Dict[str, Any]]]:
        """
        🤖 统一聊天接口 - 通过参数控制所有功能
        
        Args:
            provider: 提供商名称 (alibaba, deepseek)
            model: 模型名称
            prompt: 提示词
            stream: 是否启用流式输出，默认False
            async_mode: 是否使用异步模式，默认False
            use_context: 是否启用上下文对话，默认False
            session_id: 会话ID，启用上下文时使用，不提供则使用全局历史
            **kwargs: 其他参数 (temperature, max_tokens, top_p等)
            
        Returns:
            根据参数返回不同类型的结果：
            - 普通同步: Dict[str, Any]
            - 流式同步: Iterator[Dict[str, Any]]
            - 普通异步: Awaitable[Dict[str, Any]]
            - 流式异步: AsyncIterator[Dict[str, Any]]
            
        Examples:
            # 基础对话
            response = sdk.chat("alibaba", "qwen-turbo", "你好")
            
            # 流式输出
            for chunk in sdk.chat("alibaba", "qwen-turbo", "你好", stream=True):
                print(chunk['choices'][0]['delta']['content'], end='')
            
            # 异步对话
            response = await sdk.chat("alibaba", "qwen-turbo", "你好", async_mode=True)
            
            # 异步流式
            async for chunk in sdk.chat("alibaba", "qwen-turbo", "你好", stream=True, async_mode=True):
                print(chunk['choices'][0]['delta']['content'], end='')
            
            # 上下文对话
            response1 = sdk.chat("alibaba", "qwen-turbo", "我叫张三", use_context=True)
            response2 = sdk.chat("alibaba", "qwen-turbo", "我叫什么名字？", use_context=True)
            
            # 指定会话的上下文对话
            response = sdk.chat("alibaba", "qwen-turbo", "你好", use_context=True, session_id="user123")
        """
        return self.chat_handler.handle_chat(
            provider, model, prompt, stream, async_mode, use_context, session_id, **kwargs
        )
    
    def asr(self, 
            provider: str, 
            mode: str,
            async_mode: bool = False,
            **kwargs) -> Union[Dict[str, Any], Generator[Dict[str, Any], None, None], AsyncGenerator[Dict[str, Any], None]]:
        """
        🎤 统一语音识别接口 - 通过模式参数控制不同的ASR功能
        
        Args:
            provider: ASR提供商名称 (目前支持: alibaba)
            mode: 识别模式 ("file", "microphone", "stream", "keyword")
            async_mode: 是否使用异步模式，默认False
            **kwargs: 其他参数，根据模式不同而不同
            
        Returns:
            根据模式和async_mode返回不同类型的结果
            
        Examples:
            # 文件识别
            result = sdk.asr("alibaba", "file", audio_file="audio.wav")
            
            # 麦克风识别
            result = sdk.asr("alibaba", "microphone", duration=5)
            
            # 实时识别
            for result in sdk.asr("alibaba", "stream", audio_stream=stream):
                print(result['text'])
            
            # 关键词检测
            for result in sdk.asr("alibaba", "keyword", keywords=["你好", "小助手"]):
                if result['success']:
                    print(f"检测到: {result['keyword_detected']}")
            
            # 异步文件识别
            result = await sdk.asr("alibaba", "file", audio_file="audio.wav", async_mode=True)
        """
        if mode == "file":
            audio_file = kwargs.pop('audio_file', None)
            if not audio_file:
                raise ValueError("文件识别模式需要提供 audio_file 参数")
            
            if async_mode:
                return self.asr_handler.recognize_file_async(provider, audio_file, **kwargs)
            else:
                return self.asr_handler.recognize_file(provider, audio_file, **kwargs)
        
        elif mode == "microphone":
            duration = kwargs.pop('duration', 5)
            return self.asr_handler.recognize_microphone(provider, duration, **kwargs)
        
        elif mode == "stream":
            audio_stream = kwargs.pop('audio_stream', None)
            if audio_stream is None:
                raise ValueError("流式识别模式需要提供 audio_stream 参数")
            
            if async_mode:
                return self.asr_handler.recognize_stream_async(provider, audio_stream, **kwargs)
            else:
                return self.asr_handler.recognize_stream(provider, audio_stream, **kwargs)
        
        elif mode == "keyword":
            keywords = kwargs.pop('keywords', None)
            if not keywords:
                raise ValueError("关键词检测模式需要提供 keywords 参数")
            
            return self.asr_handler.keyword_spotting(provider, keywords, **kwargs)
        
        else:
            raise ValueError(f"不支持的ASR模式: {mode}，支持的模式: file, microphone, stream, keyword")

    def tts(self, 
            provider: str, 
            mode: str,
            text: str,
            async_mode: bool = False,
            **kwargs) -> Union[Dict[str, Any], Generator[Dict[str, Any], None, None], AsyncGenerator[Dict[str, Any], None]]:
        """
        🔊 统一语音合成接口 - 通过模式参数控制不同的TTS功能
        
        Args:
            provider: TTS提供商名称 (目前支持: alibaba)
            mode: 合成模式 ("file", "speaker", "stream")
            text: 要合成的文本
            async_mode: 是否使用异步模式，默认False
            **kwargs: 其他参数，根据模式不同而不同
            
        Returns:
            根据模式和async_mode返回不同类型的结果
            
        Examples:
            # 保存到文件
            result = sdk.tts("alibaba", "file", "你好世界", output_file="output.mp3")
            
            # 扬声器播放
            result = sdk.tts("alibaba", "speaker", "你好世界")
            
            # 流式合成（配合LLM流式输出）
            def text_generator():
                yield "你好"
                yield "世界"
            
            for result in sdk.tts("alibaba", "stream", text_generator()):
                print(f"合成完成: {result['text_chunk']}")
            
            # 异步合成
            result = await sdk.tts("alibaba", "file", "你好世界", 
                                 output_file="output.mp3", async_mode=True)
        """
        if mode == "file":
            output_file = kwargs.pop('output_file', None)
            if not output_file:
                raise ValueError("文件模式需要提供 output_file 参数")
            
            if async_mode:
                return self.tts_handler.synthesize_to_file_async(provider, text, output_file, **kwargs)
            else:
                return self.tts_handler.synthesize_to_file(provider, text, output_file, **kwargs)
        
        elif mode == "speaker":
            if async_mode:
                return self.tts_handler.synthesize_to_speaker_async(provider, text, **kwargs)
            else:
                return self.tts_handler.synthesize_to_speaker(provider, text, **kwargs)
        
        elif mode == "stream":
            # 对于流式模式，text参数应该是一个生成器
            text_stream = text if hasattr(text, '__iter__') and not isinstance(text, str) else [text]
            
            if async_mode:
                return self.tts_handler.synthesize_stream_async(provider, text_stream, **kwargs)
            else:
                return self.tts_handler.synthesize_stream(provider, text_stream, **kwargs)
        
        else:
            raise ValueError(f"不支持的TTS模式: {mode}，支持的模式: file, speaker, stream")

    def multimodal(self,
                   provider: str,
                   mode: str,
                   prompt: str,
                   image_path: str = None,
                   video_path: str = None,
                   async_mode: bool = False,
                   **kwargs) -> Dict[str, Any]:
        """
        🤖🎥 统一多模态接口 - 通过模式参数控制不同的多模态功能
        
        Args:
            provider: 多模态提供商名称 (目前支持: alibaba)
            mode: 多模态模式 ("image", "video", "multiple_images")
            prompt: 提示词
            image_path: 图像文件路径或URL（image模式使用）
            video_path: 视频文件路径或URL（video模式使用）
            async_mode: 是否使用异步模式，默认False
            **kwargs: 其他参数，根据模式不同而不同
                - image_paths: 多图像路径列表（multiple_images模式使用）
                - model: 模型名称，默认qwen-vl-max-latest
                - temperature: 温度参数
                - max_tokens: 最大token数
                - fps: 视频抽帧频率（video模式使用）
                
        Returns:
            多模态结果字典
            
        Examples:
            # 图像理解
            result = sdk.multimodal("alibaba", "image", "描述这张图片", image_path="image.jpg")
            
            # 视频分析
            result = sdk.multimodal("alibaba", "video", "分析这个视频", video_path="video.mp4")
            
            # 多图像分析
            result = sdk.multimodal("alibaba", "multiple_images", "比较这些图片", 
                                  image_paths=["img1.jpg", "img2.jpg"])
            
            # 异步调用
            result = await sdk.multimodal("alibaba", "image", "描述图片", 
                                        image_path="image.jpg", async_mode=True)
        """
        if mode == "image":
            if not image_path:
                raise ValueError("图像理解模式需要提供 image_path 参数")
            
            if async_mode:
                return self.multimodal_handler.analyze_image_async(provider, image_path, prompt, **kwargs)
            else:
                return self.multimodal_handler.analyze_image(provider, image_path, prompt, **kwargs)
        
        elif mode == "video":
            if not video_path:
                raise ValueError("视频分析模式需要提供 video_path 参数")
            
            if async_mode:
                return self.multimodal_handler.analyze_video_async(provider, video_path, prompt, **kwargs)
            else:
                return self.multimodal_handler.analyze_video(provider, video_path, prompt, **kwargs)
        
        elif mode == "multiple_images":
            image_paths = kwargs.pop('image_paths', [])
            if not image_paths:
                raise ValueError("多图像分析模式需要提供 image_paths 参数")
            
            if async_mode:
                return self.multimodal_handler.analyze_multiple_images_async(provider, image_paths, prompt, **kwargs)
            else:
                return self.multimodal_handler.analyze_multiple_images(provider, image_paths, prompt, **kwargs)
        
        else:
            raise ValueError(f"不支持的多模态模式: {mode}，支持的模式: image, video, multiple_images")

    def smart_chat(self,
                   prompt: str,
                   llm_provider: str = "alibaba",
                   llm_model: str = "qwen-turbo", 
                   tts_provider: str = "alibaba",
                   tts_model: str = "sambert-zhichu-v1",
                   tts_mode: str = "speaker",
                   use_context: bool = False,
                   session_id: str = None,
                   stream_chat: bool = False,
                   async_mode: bool = False,
                   **kwargs) -> Dict[str, Any]:
        """
        🤖🔊 LLM + TTS 智能对话 - 一键实现AI问答并语音播放
        
        这个函数封装了完整的智能对话流程：
        1. 使用LLM获取AI回答
        2. 将回答转换为语音并播放/保存
        
        Args:
            prompt: 用户问题/提示词
            llm_provider: LLM提供商名称，默认"alibaba"
            llm_model: LLM模型名称，默认"qwen-turbo"
            tts_provider: TTS提供商名称，默认"alibaba"
            tts_model: TTS模型名称，默认"sambert-zhichu-v1"
            tts_mode: TTS模式 ("speaker", "file", "stream")，默认"speaker"
            use_context: 是否启用上下文对话，默认False
            session_id: 会话ID，启用上下文时使用
            stream_chat: 是否使用流式LLM输出，默认False
            async_mode: 是否使用异步模式，默认False
            **kwargs: 其他参数
                - LLM参数: temperature, max_tokens, top_p等
                - TTS参数: voice, sample_rate, output_file等
                
        Returns:
            包含LLM回答和TTS结果的字典
            
        Examples:
            # 基础智能对话
            result = sdk.smart_chat("你好，请介绍一下自己")
            
            # 保存语音到文件
            result = sdk.smart_chat(
                "讲个故事", 
                tts_mode="file",
                output_file="story.mp3"
            )
            
            # 上下文对话
            sdk.smart_chat("我叫张三", use_context=True)
            result = sdk.smart_chat("我叫什么名字？", use_context=True)
            
            # 指定模型和音色
            result = sdk.smart_chat(
                "用温柔的声音说话",
                llm_model="qwen-plus",
                tts_model="cosyvoice-v1",
                voice="longxiaoxia"
            )
            
            # 异步调用
            result = await sdk.smart_chat("你好", async_mode=True)
        """
        
        # 分离LLM和TTS参数
        llm_kwargs = {}
        tts_kwargs = {}
        
        # LLM相关参数
        llm_params = ['temperature', 'max_tokens', 'top_p', 'top_k', 'repetition_penalty']
        for param in llm_params:
            if param in kwargs:
                llm_kwargs[param] = kwargs.pop(param)
        
        # TTS相关参数
        tts_params = ['voice', 'sample_rate', 'format', 'output_file']
        for param in tts_params:
            if param in kwargs:
                tts_kwargs[param] = kwargs.pop(param)
        
        # 添加TTS模型参数
        tts_kwargs['model'] = tts_model
        
        if async_mode:
            return self.smart_chat_handler.handle_async(
                prompt, llm_provider, llm_model, tts_provider, tts_mode,
                use_context, session_id, stream_chat, llm_kwargs, tts_kwargs
            )
        else:
            return self.smart_chat_handler.handle_sync(
                prompt, llm_provider, llm_model, tts_provider, tts_mode,
                use_context, session_id, stream_chat, llm_kwargs, tts_kwargs
            )

    def smart_multimodal_chat(self,
                             prompt: str,
                             image_path: str = None,
                             video_path: str = None,
                             image_paths: List[str] = None,
                             multimodal_provider: str = "alibaba",
                             multimodal_model: str = "qwen-vl-max-latest",
                             tts_provider: str = "alibaba",
                             tts_model: str = "sambert-zhichu-v1",
                             tts_mode: str = "speaker",
                             stream_output: bool = False,
                             realtime_tts: bool = True,
                             async_mode: bool = False,
                             **kwargs) -> Dict[str, Any]:
        """
        🤖🎥🔊 多模态智能对话 - 图像/视频理解 + 流式输出 + 实时语音播放
        
        这个函数封装了完整的多模态智能对话流程：
        1. 使用多模态模型理解图像/视频内容
        2. 流式输出AI的理解和回答
        3. 实时将回答转换为语音并播放
        
        Args:
            prompt: 用户问题/提示词
            image_path: 单张图像路径或URL
            video_path: 视频路径或URL
            image_paths: 多张图像路径或URL列表
            multimodal_provider: 多模态提供商名称，默认"alibaba"
            multimodal_model: 多模态模型名称，默认"qwen-vl-max-latest"
            tts_provider: TTS提供商名称，默认"alibaba"
            tts_model: TTS模型名称，默认"sambert-zhichu-v1"
            tts_mode: TTS模式 ("speaker", "file")，默认"speaker"
            stream_output: 是否使用流式输出，默认True
            realtime_tts: 是否实时语音播放，默认True
            async_mode: 是否使用异步模式，默认False
            **kwargs: 其他参数
                - 多模态参数: temperature, max_tokens等
                - TTS参数: voice, sample_rate, output_file等
                
        Returns:
            包含多模态理解结果和TTS结果的字典
            
        Examples:
            # 基础图像理解对话
            result = sdk.smart_multimodal_chat(
                "请描述这张图片",
                image_path="image.jpg"
            )
            
            # 视频分析对话
            result = sdk.smart_multimodal_chat(
                "分析这个视频的内容",
                video_path="video.mp4"
            )
            
            # 多图像比较对话
            result = sdk.smart_multimodal_chat(
                "比较这些图片的差异",
                image_paths=["img1.jpg", "img2.jpg"]
            )
            
            # 保存语音到文件
            result = sdk.smart_multimodal_chat(
                "详细分析这张图片",
                image_path="image.jpg",
                tts_mode="file",
                output_file="analysis.mp3"
            )
            
            # 异步调用
            result = await sdk.smart_multimodal_chat(
                "描述图片内容",
                image_path="image.jpg",
                async_mode=True
            )
        """
        
        # 分离多模态和TTS参数
        multimodal_kwargs = {}
        tts_kwargs = {}
        
        # 多模态相关参数
        multimodal_params = ['temperature', 'max_tokens', 'top_p', 'fps', 'use_openai_format']
        for param in multimodal_params:
            if param in kwargs:
                multimodal_kwargs[param] = kwargs.pop(param)
        
        # TTS相关参数
        tts_params = ['voice', 'sample_rate', 'format', 'output_file']
        for param in tts_params:
            if param in kwargs:
                tts_kwargs[param] = kwargs.pop(param)
        
        # 添加模型参数
        multimodal_kwargs['model'] = multimodal_model
        tts_kwargs['model'] = tts_model
        
        if async_mode:
            try:
                return self.smart_multimodal_chat_handler.handle_async(
                    prompt, image_path, video_path, image_paths,
                    multimodal_provider, tts_provider, tts_mode,
                    stream_output, realtime_tts, multimodal_kwargs, tts_kwargs
                )
            except Exception as e:
                print(f"❌ 异步多模态智能对话出现异常: {e}")
                import traceback
                print(f"详细错误信息:\n{traceback.format_exc()}")
                return {
                    'success': False,
                    'error': f"异步多模态智能对话异常: {str(e)}",
                    'answer': '',
                    'mode': 'error',
                    'media_info': 'error'
                }
        else:
            try:
                result = self.smart_multimodal_chat_handler.handle_sync(
                    prompt, image_path, video_path, image_paths,
                    multimodal_provider, tts_provider, tts_mode,
                    stream_output, realtime_tts, multimodal_kwargs, tts_kwargs
                )
                return result
            except Exception as e:
                print(f"❌ 多模态智能对话出现异常: {e}")
                import traceback
                print(f"详细错误信息:\n{traceback.format_exc()}")
                return {
                    'success': False,
                    'error': f"多模态智能对话异常: {str(e)}",
                    'answer': '',
                    'mode': 'error',
                    'media_info': 'error'
                }

    def smart_voice_chat(self,
                        duration: int = 5,
                        llm_provider: str = "alibaba",
                        llm_model: str = "qwen-turbo",
                        tts_provider: str = "alibaba",
                        tts_model: str = "sambert-zhichu-v1",
                        use_context: bool = True,
                        session_id: str = "voice_chat",
                        continue_conversation: bool = True,
                        activation_phrase: str = "你好助手",
                        activate_once: bool = True,
                        end_phrase: str = "结束对话",
                        silence_timeout: float = 2.0,
                        verbose: bool = False,
                        **kwargs) -> Dict[str, Any]:
        """
        🎙️🤖🔊 智能语音对话 - 实时ASR + LLM + 实时TTS
        
        通过麦克风捕获用户语音，实时转换为文本，发送给LLM，并实时播放AI回复。
        
        Args:
            duration: 每次录音的最大秒数，默认5秒
            llm_provider: LLM提供商名称，默认"alibaba"
            llm_model: LLM模型名称，默认"qwen-turbo"
            tts_provider: TTS提供商名称，默认"alibaba"
            tts_model: TTS模型名称，默认"sambert-zhichu-v1"
            use_context: 是否启用上下文对话，默认True
            session_id: 会话ID，默认"voice_chat"
            continue_conversation: 是否持续对话，默认True
            activation_phrase: 激活短语，说出此短语开始对话，为None时不需要激活短语
            activate_once: 是否只需激活一次，默认True，即首次启动对话时需要激活，后续对话不需要
            end_phrase: 结束对话的短语，默认"结束对话"
            silence_timeout: 静音超时时间（秒），检测到静音这么长时间后认为语音输入结束
            verbose: 是否输出详细日志，默认False
            **kwargs: 其他参数，包括LLM和TTS的参数
            
        Returns:
            Dict[str, Any]: 对话结果信息
            
        Example:
            # 启动实时语音对话
            sdk.smart_voice_chat()
            
            # 自定义参数
            sdk.smart_voice_chat(
                llm_model="qwen-plus",
                tts_model="cosyvoice-v1",
                voice="longxiaochun",
                activation_phrase="你好助手"
            )
        """
        return self.smart_voice_chat_handler.handle_voice_chat(
            duration=duration,
            llm_provider=llm_provider,
            llm_model=llm_model,
            tts_provider=tts_provider,
            tts_model=tts_model,
            use_context=use_context,
            session_id=session_id,
            continue_conversation=continue_conversation,
            activation_phrase=activation_phrase,
            activate_once=activate_once,
            end_phrase=end_phrase,
            silence_timeout=silence_timeout,
            verbose=verbose,
            **kwargs
        )

    def smart_multimodal_voice_chat(self,
                              image_path: str = None,
                              video_path: str = None,
                              image_paths: List[str] = None,
                              duration: int = 5,
                              llm_provider: str = "alibaba",
                              llm_model: str = "qwen-vl-max-latest",
                              tts_provider: str = "alibaba",
                              tts_model: str = "sambert-zhichu-v1",
                              use_context: bool = True,
                              session_id: str = "multimodal_voice_chat",
                              continue_conversation: bool = True,
                              activation_phrase: str = "你好助手",
                              activate_once: bool = True,
                              end_phrase: str = "结束对话",
                              silence_timeout: float = 2.0,
                              verbose: bool = False,
                              **kwargs) -> Dict[str, Any]:
        """
        🎙️🖼️🔊 智能多模态语音对话 - 实时ASR + 多模态LLM + 实时TTS
        
        将语音识别、多模态大模型和语音合成结合在一起，可以对图像、视频进行语音提问并获得语音回答。
        
        Args:
            image_path: 图像路径，可以是本地文件或URL
            video_path: 视频路径，可以是本地文件或URL
            image_paths: 多图像路径列表，用于比较多张图像
            duration: 每次录音的最大秒数，默认5秒
            llm_provider: LLM提供商名称，默认"alibaba"
            llm_model: LLM模型名称，默认"qwen-vl-max-latest"
            tts_provider: TTS提供商名称，默认"alibaba"
            tts_model: TTS模型名称，默认"sambert-zhichu-v1"
            use_context: 是否启用上下文对话，默认True
            session_id: 会话ID，默认"multimodal_voice_chat"
            continue_conversation: 是否持续对话，默认True
            activation_phrase: 激活短语，说出此短语开始对话，为None时不需要激活短语
            activate_once: 是否只需激活一次，默认True，即首次启动对话时需要激活，后续对话不需要
            end_phrase: 结束对话的短语，默认"结束对话"
            silence_timeout: 静音超时时间（秒），检测到静音这么长时间后认为语音输入结束
            verbose: 是否输出详细日志，默认False
            **kwargs: 其他参数，包括LLM和TTS的参数
            
        Returns:
            Dict[str, Any]: 对话结果信息
            
        Example:
            # 启动多模态语音对话（图像）
            sdk.smart_multimodal_voice_chat(image_path="path/to/image.jpg")
            
            # 启动多模态语音对话（视频）
            sdk.smart_multimodal_voice_chat(video_path="path/to/video.mp4")
            
            # 启动多模态语音对话（多图像比较）
            sdk.smart_multimodal_voice_chat(
                image_paths=["path/to/image1.jpg", "path/to/image2.jpg"],
                llm_model="qwen-vl-max",
                tts_model="sambert-zhichu-v1",
                voice="zhizhe",
                activation_phrase="你好助手"
            )
        """
        return self.smart_multimodal_voice_chat_handler.handle_multimodal_voice_chat(
            image_path=image_path,
            video_path=video_path,
            image_paths=image_paths,
            duration=duration,
            llm_provider=llm_provider,
            llm_model=llm_model,
            tts_provider=tts_provider,
            tts_model=tts_model,
            use_context=use_context,
            session_id=session_id,
            continue_conversation=continue_conversation,
            activation_phrase=activation_phrase,
            activate_once=activate_once,
            end_phrase=end_phrase,
            silence_timeout=silence_timeout,
            verbose=verbose,
            **kwargs
        )
        
    # 🛠️ 便捷工具方法
    def get_conversation_history(self, session_id: str = None) -> List[Dict[str, str]]:
        """
        📜 获取会话历史记录
        
        Args:
            session_id: 会话ID，不提供则返回全局历史
            
        Returns:
            会话历史列表
        """
        return self.chat_handler.get_conversation_history(session_id)

    def clear_conversation_history(self, session_id: str = None):
        """
        🗑️ 清空会话历史记录
        
        Args:
            session_id: 会话ID，不提供则清空全局历史
        """
        self.chat_handler.clear_conversation_history(session_id)

    def set_conversation_history(self, history: List[Dict[str, str]], session_id: str = None):
        """
        📝 设置会话历史记录
        
        Args:
            history: 会话历史列表
            session_id: 会话ID，不提供则设置全局历史
        """
        self.chat_handler.set_conversation_history(history, session_id)

    # 👥 会话管理
    def create_session(self, session_id: str = None, max_history: int = None, 
                      system_prompt: str = None) -> ChatSession:
        """
        ➕ 创建新的对话会话
        
        Args:
            session_id: 会话ID，不提供则自动生成
            max_history: 最大历史记录数，默认使用配置值
            system_prompt: 系统提示词
            
        Returns:
            会话对象
        """
        return self.chat_handler.create_session(session_id, max_history, system_prompt)

    def get_session(self, session_id: str) -> ChatSession:
        """
        📋 获取指定会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话对象
        """
        return self.chat_handler.get_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        """
        🗑️ 删除指定会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否删除成功
        """
        return self.chat_handler.delete_session(session_id)

    def list_sessions(self):
        """
        📋 列出所有会话
        
        Returns:
            会话ID列表
        """
        return self.chat_handler.list_sessions()

    # 📊 配置和信息查询
    def get_available_providers(self) -> Dict[str, Dict[str, Any]]:
        """
        📋 获取可用的提供商信息
        
        Returns:
            提供商信息字典
        """
        return self.config.get('providers', {})

    def get_provider_models(self, provider: str) -> Dict[str, Any]:
        """
        📋 获取指定提供商的模型信息
        
        Args:
            provider: 提供商名称
            
        Returns:
            模型信息字典
        """
        providers = self.config.get('providers', {})
        if provider not in providers:
            raise ValueError(f"未找到提供商: {provider}")
        
        return providers[provider].get('models', {})


    def get_config(self) -> Dict[str, Any]:
        """
        📋 获取当前配置
        
        Returns:
            配置字典
        """
        return self.config.copy()

    def update_config(self, new_config: Dict[str, Any]):
        """
        🔄 更新配置
        
        Args:
            new_config: 新配置字典
        """
        self.config.update(new_config)
        # 重新初始化处理器
        self.chat_handler = ChatHandler(self.config)
        self.asr_handler = ASRHandler(self.config)
        self.tts_handler = TTSHandler(self.config)
        self.multimodal_handler = MultiModalHandler(self.config)
        self.smart_chat_handler = SmartChatHandler(self)
        self.smart_multimodal_chat_handler = SmartMultiModalChatHandler(self)
        self.smart_voice_chat_handler = SmartVoiceChatHandler(self)
        self.smart_multimodal_voice_chat_handler = SmartMultiModalVoiceChatHandler(self)

# 导出主要类和异常
__all__ = ['AISDK', 'AISDKException', 'ValidationException', 'ConfigException'] 