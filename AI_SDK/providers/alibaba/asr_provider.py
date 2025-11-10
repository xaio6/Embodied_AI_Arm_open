"""
阿里云ASR提供商
使用DashScope SDK实现语音识别功能
"""

import os
import time
import asyncio
import threading
import concurrent.futures
from typing import Dict, Any, Generator, AsyncGenerator, Optional
import pyaudio
import wave
import io
from ..base import BaseASRProvider

try:
    import dashscope
    from dashscope.audio.asr import Recognition, RecognitionCallback
    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False


class AlibabaASRProvider(BaseASRProvider):
    """阿里云ASR提供商"""
    
    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        
        if not DASHSCOPE_AVAILABLE:
            raise ImportError("请安装 dashscope: pip install dashscope")
        
        # 设置API Key
        dashscope.api_key = api_key
        
        # 音频参数
        self.sample_rate = kwargs.get('sample_rate', 16000)
        self.channels = kwargs.get('channels', 1)
        self.chunk_size = kwargs.get('chunk_size', 3200)
        
        # 支持的音频格式
        self.supported_formats = ['wav', 'mp3', 'pcm', 'aac', 'amr', 'ogg']
        
        # 默认模型
        self.default_model = kwargs.get('model', 'paraformer-realtime-v2')
    
    def _validate_audio_file(self, audio_file: str) -> bool:
        """验证音频文件"""
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"音频文件不存在: {audio_file}")
        
        file_ext = os.path.splitext(audio_file)[1][1:].lower()
        if file_ext not in self.supported_formats:
            raise ValueError(f"不支持的音频格式: {file_ext}，支持的格式: {self.supported_formats}")
        
        return True
    
    def recognize_file(self, audio_file: str, **kwargs) -> Dict[str, Any]:
        """识别音频文件"""
        self._validate_audio_file(audio_file)
        
        try:
            # 使用同步调用方式
            model = kwargs.get('model', self.default_model)
            
            # 创建识别器
            recognizer = Recognition(
                model=model,
                format='wav',
                sample_rate=self.sample_rate,
                callback=None  # 同步调用不需要回调
            )
            
            # 直接调用文件识别
            result = recognizer.call(audio_file)
            
            # 检查状态码
            if hasattr(result, 'status_code') and result.status_code.value == 200:
                # 使用官方推荐的get_sentence()方法获取结果
                sentences = result.get_sentence()
                
                if sentences:
                    # 提取所有句子的文本
                    full_text = ""
                    total_confidence = 0.0
                    sentence_count = 0
                    
                    # sentences可能是单个句子dict或句子列表
                    if isinstance(sentences, dict):
                        sentences = [sentences]
                    elif isinstance(sentences, list):
                        pass
                    else:
                        # 如果不是预期格式，尝试从output中获取
                        if hasattr(result, 'output') and result.output:
                            if 'sentence' in result.output:
                                sentences = result.output['sentence']
                            else:
                                sentences = []
                    
                    for sentence in sentences:
                        if isinstance(sentence, dict) and 'text' in sentence:
                            full_text += sentence['text']
                            sentence_count += 1
                            # 如果有置信度信息，累加计算平均值
                            if 'confidence' in sentence:
                                total_confidence += sentence.get('confidence', 0.0)
                    
                    # 计算平均置信度
                    avg_confidence = total_confidence / sentence_count if sentence_count > 0 else 0.0
                    
                    return {
                        'success': True,
                        'text': full_text,
                        'confidence': avg_confidence,
                        'audio_duration': 0,
                        'processing_time': 0,
                        'sentences': sentences,  # 保留原始句子信息
                        'request_id': getattr(result, 'request_id', '')
                    }
                else:
                    return {
                        'success': False,
                        'error': "识别结果为空",
                        'text': '',
                        'confidence': 0.0
                    }
            else:
                # 识别失败
                error_msg = getattr(result, 'message', '未知错误')
                return {
                    'success': False,
                    'error': f"识别失败: {error_msg}",
                    'text': '',
                    'confidence': 0.0
                }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"文件识别失败: {str(e)}",
                'text': '',
                'confidence': 0.0
            }
    
    async def recognize_file_async(self, audio_file: str, **kwargs) -> Dict[str, Any]:
        """异步识别音频文件"""
        # 在线程池中运行同步方法
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, self.recognize_file, audio_file, **kwargs)
            return result
    
    def recognize_stream(self, audio_stream, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """实时语音识别"""
        try:
            model = kwargs.get('model', self.default_model)
            
            # 创建回调类来处理流式结果
            class StreamCallback(RecognitionCallback):
                def __init__(self):
                    self.results = []
                    self.error_message = None
                
                def on_open(self):
                    pass
                
                def on_close(self):
                    pass
                
                def on_event(self, result):
                    if result and hasattr(result, 'status_code') and result.status_code.value == 200:
                        # 使用get_sentence()方法获取结果
                        sentences = result.get_sentence()
                        
                        if sentences:
                            # sentences可能是单个句子dict或句子列表
                            if isinstance(sentences, dict):
                                sentences = [sentences]
                            
                            for sentence in sentences:
                                if isinstance(sentence, dict) and 'text' in sentence:
                                    self.results.append({
                                        'success': True,
                                        'text': sentence['text'],
                                        'confidence': sentence.get('confidence', 0.0),
                                        'is_final': sentence.get('sentence_end', False),
                                        'begin_time': sentence.get('begin_time', 0),
                                        'end_time': sentence.get('end_time', 0),
                                        'sentence_id': sentence.get('sentence_id', 0)
                                    })
                
                def on_error(self, result):
                    error_msg = getattr(result, 'message', '未知错误')
                    self.error_message = error_msg
                    self.results.append({
                        'success': False,
                        'error': self.error_message,
                        'text': '',
                        'confidence': 0.0,
                        'is_final': False
                    })
                
                def on_complete(self):
                    pass
            
            callback = StreamCallback()
            
            # 创建识别器
            recognizer = Recognition(
                model=model,
                format='pcm',
                sample_rate=self.sample_rate,
                callback=callback
            )
            
            # 开始识别
            recognizer.start()
            
            try:
                # 处理音频流
                for audio_chunk in audio_stream:
                    recognizer.send_audio_frame(audio_chunk)
                    
                    # 返回累积的结果
                    while callback.results:
                        yield callback.results.pop(0)
                    
                    time.sleep(0.01)  # 短暂延迟
                
                # 停止识别
                recognizer.stop()
                
                # 返回剩余结果
                while callback.results:
                    yield callback.results.pop(0)
                    
            except Exception as e:
                yield {
                    'success': False,
                    'error': f"流式识别错误: {str(e)}",
                    'text': '',
                    'confidence': 0.0,
                    'is_final': False
                }
            
        except Exception as e:
            yield {
                'success': False,
                'error': f"实时识别失败: {str(e)}",
                'text': '',
                'confidence': 0.0,
                'is_final': False
            }
    
    async def recognize_stream_async(self, audio_stream, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """异步实时语音识别"""
        # 在线程池中运行同步生成器
        loop = asyncio.get_event_loop()
        
        def sync_generator():
            return list(self.recognize_stream(audio_stream, **kwargs))
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = await loop.run_in_executor(None, sync_generator)
            
            for result in results:
                yield result
    
    def recognize_microphone(self, duration: int = 5, **kwargs) -> Dict[str, Any]:
        """识别麦克风音频"""
        try:
            # 初始化PyAudio
            audio = pyaudio.PyAudio()
            
            # 音频参数
            sample_rate = kwargs.get('sample_rate', self.sample_rate)
            channels = kwargs.get('channels', self.channels)
            chunk_size = kwargs.get('chunk_size', self.chunk_size)
            
            print(f"开始录音，时长: {duration}秒...")
            
            # 开始录音
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                input=True,
                frames_per_buffer=chunk_size
            )
            
            # 创建回调类来收集识别结果
            class MicCallback(RecognitionCallback):
                def __init__(self):
                    self.final_text = ""
                    self.confidence = 0.0
                    self.error_message = None
                    self.sentence_count = 0
                
                def on_open(self):
                    pass
                
                def on_close(self):
                    pass
                
                def on_event(self, result):
                    if result and hasattr(result, 'status_code') and result.status_code.value == 200:
                        sentences = result.get_sentence()
                        
                        if sentences:
                            if isinstance(sentences, dict):
                                sentences = [sentences]
                            
                            for sentence in sentences:
                                if isinstance(sentence, dict) and 'text' in sentence:
                                    # 只处理完整的句子
                                    if sentence.get('sentence_end', False):
                                        self.final_text += sentence['text']
                                        self.sentence_count += 1
                                        if 'confidence' in sentence:
                                            self.confidence += sentence.get('confidence', 0.0)
                
                def on_error(self, result):
                    self.error_message = getattr(result, 'message', '未知错误')
                
                def on_complete(self):
                    pass
            
            callback = MicCallback()
            
            # 创建识别器
            recognizer = Recognition(
                model=kwargs.get('model', self.default_model),
                format='pcm',
                sample_rate=sample_rate,
                callback=callback
            )
            
            # 开始识别
            recognizer.start()
            
            # 录音并实时发送数据
            frames_to_record = int(sample_rate / chunk_size * duration)
            for _ in range(frames_to_record):
                data = stream.read(chunk_size)
                recognizer.send_audio_frame(data)
                time.sleep(0.01)  # 控制发送频率
            
            print("录音结束，等待识别完成...")
            
            # 停止录音
            stream.stop_stream()
            stream.close()
            # 安全地关闭PyAudio，避免程序退出
            audio = None
            
            # 停止识别
            recognizer.stop()
            
            if callback.error_message:
                return {
                    'success': False,
                    'error': callback.error_message,
                    'text': '',
                    'confidence': 0.0
                }
            
            # 计算平均置信度
            avg_confidence = callback.confidence / callback.sentence_count if callback.sentence_count > 0 else 0.0
            
            return {
                'success': True,
                'text': callback.final_text,
                'confidence': avg_confidence,
                'audio_duration': duration,
                'processing_time': 0
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"麦克风识别失败: {str(e)}",
                'text': '',
                'confidence': 0.0
            }
    
    def keyword_spotting(self, keywords: list, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """关键词识别唤醒 - 只有检测到关键词时才返回结果"""
        try:
            # 初始化PyAudio
            audio = pyaudio.PyAudio()
            
            # 音频参数
            sample_rate = kwargs.get('sample_rate', self.sample_rate)
            channels = kwargs.get('channels', self.channels)
            chunk_size = kwargs.get('chunk_size', self.chunk_size)
            
            # 关键词检测参数
            detection_threshold = kwargs.get('detection_threshold', 0.6)
            silence_timeout = kwargs.get('silence_timeout', 3.0)
            max_audio_length = kwargs.get('max_audio_length', 15)
            debug_mode = kwargs.get('debug_mode', False)  # 默认关闭调试模式
            
            # 将关键词转换为小写以便匹配
            keywords_lower = [kw.lower().strip() for kw in keywords]
            
            print(f"🔍 开始关键词检测，目标关键词: {keywords}")
            print(f"🔇 静默监听中...")
            
            # 开始录音
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                input=True,
                frames_per_buffer=chunk_size
            )
            
            # 创建回调类来处理关键词检测
            class KeywordDetectionCallback(RecognitionCallback):
                def __init__(self, target_keywords, threshold, debug=False):
                    self.target_keywords = target_keywords
                    self.threshold = threshold
                    self.debug = debug
                    self.detected_results = []
                    self.current_text = ""
                    self.current_confidence = 0.0
                    self.error_message = None
                
                def on_open(self):
                    if self.debug:
                        print("🔗 ASR连接已建立")
                
                def on_close(self):
                    if self.debug:
                        print("🔌 ASR连接已关闭")
                
                def on_event(self, result):
                    if self.debug:
                        print(f"📥 收到ASR事件: {result}")
                    
                    if result and hasattr(result, 'status_code') and result.status_code.value == 200:
                        sentences = result.get_sentence()
                        
                        if sentences:
                            if isinstance(sentences, dict):
                                sentences = [sentences]
                            
                            for sentence in sentences:
                                if isinstance(sentence, dict) and 'text' in sentence:
                                    text = sentence['text'].strip()
                                    confidence = sentence.get('confidence', 0.0)
                                    is_final = sentence.get('sentence_end', False)
                                    
                                    if self.debug:
                                        print(f"📝 识别文本: '{text}' (置信度: {confidence:.2f}, 完整: {is_final})")
                                    
                                    # 更新当前识别文本
                                    self.current_text = text
                                    self.current_confidence = confidence
                                    
                                    # 只在句子结束时检查关键词，确保是完整的识别结果
                                    if is_final and text:
                                        text_lower = text.lower()
                                        
                                        # 去除标点符号进行匹配
                                        import re
                                        text_clean = re.sub(r'[^\w\s]', '', text_lower)  # 去除所有标点符号
                                        
                                        if self.debug:
                                            print(f"🔍 检查关键词: '{text_clean}' (原文: '{text_lower}') vs {self.target_keywords}")
                                        
                                        # 检查是否包含任何目标关键词（使用词边界匹配）
                                        for keyword in self.target_keywords:
                                            # 使用词边界正则表达式进行精确匹配
                                            pattern = r'\b' + re.escape(keyword) + r'\b'
                                            if re.search(pattern, text_clean):
                                                if self.debug:
                                                    print(f"🎯 找到匹配关键词: '{keyword}' in '{text_clean}'")
                                                
                                                # 找到匹配的关键词
                                                self.detected_results.append({
                                                    'success': True,
                                                    'keyword_detected': keyword,
                                                    'text': text,  # 返回原始文本（带标点）
                                                    'confidence': confidence if confidence > 0 else 0.9,
                                                    'timestamp': time.time(),
                                                    'sentence_id': sentence.get('sentence_id', 0),
                                                    'begin_time': sentence.get('begin_time', 0),
                                                    'end_time': sentence.get('end_time', 0),
                                                    'is_final': is_final
                                                })
                                                return  # 找到关键词后立即返回
                    else:
                        if self.debug:
                            print(f"⚠️ ASR事件状态异常: {result}")
                
                def on_error(self, result):
                    error_msg = getattr(result, 'message', '未知错误')
                    self.error_message = error_msg
                    if self.debug:
                        print(f"❌ ASR错误: {error_msg}")
                
                def on_complete(self):
                    if self.debug:
                        print("✅ ASR识别完成")
            
            callback = KeywordDetectionCallback(keywords_lower, detection_threshold, debug_mode)
            
            # 创建识别器 - 启用标点符号预测
            recognizer = Recognition(
                model=kwargs.get('model', self.default_model),
                format='pcm',
                sample_rate=sample_rate,
                callback=callback,
                # 启用标点符号预测，然后在代码中处理标点符号匹配
                punctuation_prediction_enabled=True
            )
            
            # 开始识别
            recognizer.start()
            
            try:
                audio_buffer = []
                frames_count = 0
                max_frames = int(sample_rate / chunk_size * max_audio_length)
                silence_frames = int(sample_rate / chunk_size * silence_timeout)
                consecutive_silence = 0
                last_activity_time = time.time()
                
                while True:
                    # 读取音频数据
                    data = stream.read(chunk_size, exception_on_overflow=False)
                    audio_buffer.append(data)
                    frames_count += 1
                    
                    # 发送音频数据到识别器
                    recognizer.send_audio_frame(data)
                    
                    # 检测音频能量（简单的静音检测）
                    import struct
                    audio_data = struct.unpack(f'{len(data)//2}h', data)
                    energy = sum(abs(sample) for sample in audio_data) / len(audio_data)
                    
                    if energy < 300:  # 静音阈值
                        consecutive_silence += 1
                    else:
                        consecutive_silence = 0
                        last_activity_time = time.time()
                        if debug_mode and time.time() - last_activity_time > 2:
                            print(f"🔊 检测到音频活动")
                    
                    # 检查是否有检测到的关键词
                    if callback.detected_results:
                        # 找到关键词，返回结果
                        result = callback.detected_results.pop(0)
                        print(f"🎉 检测到关键词: {result['keyword_detected']}")
                        yield result
                        
                        # 重置状态，继续监听下一个关键词
                        callback.detected_results.clear()
                        callback.current_text = ""
                        callback.current_confidence = 0.0
                        audio_buffer.clear()
                        frames_count = 0
                        consecutive_silence = 0
                        print("🔇 继续静默监听...")
                        continue
                    
                    # 检查错误
                    if callback.error_message:
                        yield {
                            'success': False,
                            'error': callback.error_message,
                            'keyword_detected': '',
                            'text': '',
                            'confidence': 0.0
                        }
                        callback.error_message = None
                    
                    # 超时处理：如果连续静音太久或音频太长，重置缓冲区
                    if consecutive_silence >= silence_frames or frames_count >= max_frames:
                        if debug_mode:
                            if consecutive_silence >= silence_frames:
                                print(f"🔇 静音超时，重置缓冲区")
                            else:
                                print(f"⏱️ 音频长度超时，重置缓冲区")
                        
                        # 清空缓冲区，重新开始
                        audio_buffer.clear()
                        frames_count = 0
                        consecutive_silence = 0
                        callback.current_text = ""
                        callback.current_confidence = 0.0
                    
                    time.sleep(0.01)  # 控制循环频率
                    
            except KeyboardInterrupt:
                print("\n🛑 关键词检测已停止")
            finally:
                recognizer.stop()
                stream.stop_stream()
                stream.close()
                # 安全地关闭PyAudio，避免程序退出
                audio = None
                
        except Exception as e:
            yield {
                'success': False,
                'error': f"关键词检测失败: {str(e)}",
                'keyword_detected': '',
                'text': '',
                'confidence': 0.0
            } 