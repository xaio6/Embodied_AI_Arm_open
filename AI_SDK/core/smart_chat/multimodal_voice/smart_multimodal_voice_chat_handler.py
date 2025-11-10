"""
智能多模态语音对话处理器

集成ASR语音识别、多模态大语言模型对话和TTS语音合成的完整智能语音交互功能
"""

from typing import Dict, Any, List
import time
import logging

logger = logging.getLogger(__name__)

class SmartMultiModalVoiceChatHandler:
    """
    智能多模态语音对话处理器类
    
    管理麦克风输入、语音识别、多模态LLM对话和语音回复的完整流程
    
    功能：
    - 支持关键词唤醒
    - 麦克风语音录入
    - 上传图像/视频进行多模态分析
    - 流式LLM处理
    - 实时语音合成播放
    - 上下文对话支持
    - 语音指令控制
    """
    
    def __init__(self, sdk):
        """
        初始化智能多模态语音对话处理器
        
        Args:
            sdk: AI SDK实例
        """
        self.sdk = sdk
    
    def handle_multimodal_voice_chat(self,
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
        处理完整的多模态语音对话流程
        
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
        """
        # 使用简化实现：组合现有功能
        result = {
            "success": True,
            "conversations": []
        }
        
        # 检查是否提供了多模态媒体
        if not any([image_path, video_path, image_paths]):
            error_msg = "必须提供图像路径(image_path)、视频路径(video_path)或多图像路径(image_paths)中的至少一项"
            if verbose:
                logger.error(error_msg)
            print(f"❌ 错误: {error_msg}")
            return {"success": False, "error": error_msg}
            
        # 确定多模态媒体类型
        if image_paths:
            media_type = "多图像"
            media_info = f"{len(image_paths)}张图片"
        elif video_path:
            media_type = "视频"
            media_info = f"{video_path}"
        elif image_path:
            media_type = "图像"
            media_info = f"{image_path}"
        
        if verbose:
            logger.info("智能多模态语音对话已启动...")
        print(f"🎙️🖼️ 智能多模态语音对话已启动... ({media_type}: {media_info})")
        
        # 提取TTS参数
        voice = kwargs.pop('voice', None)
        
        # 从kwargs中提取静默参数
        tts_kwargs = kwargs.copy()
        if not verbose:
            tts_kwargs['silent'] = True
        
        conversation_active = True
        waiting_for_activation = activation_phrase is not None
        activated_once = False
        
        try:
            while conversation_active:
                # 激活处理
                if waiting_for_activation and (not activate_once or not activated_once):
                    if verbose:
                        logger.info(f"等待激活短语: '{activation_phrase}'...")
                    print(f"等待激活短语: '{activation_phrase}'...")
                    
                    # 使用ASR关键词模式等待激活
                    for keyword_result in self.sdk.asr(
                        provider=llm_provider,
                        mode="keyword",
                        keywords=[activation_phrase],
                        detection_threshold=0.6
                    ):
                        if keyword_result.get('success') and keyword_result.get('keyword_detected'):
                            if verbose:
                                logger.info(f"已激活! 检测到: '{keyword_result['keyword_detected']}'")
                            print(f"✓ 已激活! 检测到: '{keyword_result['keyword_detected']}'")
                            waiting_for_activation = False
                            activated_once = True
                            break
                
                # 已激活，开始语音输入
                print("🎤 正在聆听...(语音停止或说出结束短语将发送对话)")
                
                # 使用ASR获取用户语音输入
                user_input = ""
                
                # 预处理结束短语
                import re
                def clean_text(text):
                    if not text:
                        return ""
                    cleaned = re.sub(r'[^\w\s]', '', text.lower())
                    cleaned = ' '.join(cleaned.split())
                    return cleaned
                
                cleaned_end_phrase = clean_text(end_phrase)
                
                # 语音识别 - 麦克风模式直接返回结果而非生成器
                asr_result = self.sdk.asr(
                    provider=llm_provider,
                    mode="microphone",
                    duration=duration,
                    silence_timeout=silence_timeout
                )
                if asr_result.get('success'):
                    user_input = asr_result.get('text', '')
                
                # 检查是否是结束命令
                cleaned_input = clean_text(user_input)
                if end_phrase and cleaned_input == cleaned_end_phrase:
                    if verbose:
                        logger.info("检测到结束对话指令，正在结束会话...")
                    print("👋 已检测到结束对话指令，正在结束会话...")
                    conversation_active = False
                    break
                
                if not user_input:
                    print("❓ 未检测到有效语音输入，请再试一次")
                    continue
                
                if verbose:
                    logger.info(f"已识别: '{user_input}'")
                print(f"🔍 已识别: '{user_input}'")
                
                # 多模态处理
                print("🤖 AI分析中...")
                
                # 根据媒体类型调用不同的方法
                if image_path:
                    multimodal_result = self.sdk.smart_multimodal_chat(
                        prompt=user_input,
                        image_path=image_path,
                        multimodal_provider=llm_provider,
                        multimodal_model=llm_model,
                        tts_provider=tts_provider,
                        tts_model=tts_model,
                        tts_mode="speaker",
                        use_context=use_context,
                        session_id=session_id,
                        **tts_kwargs
                    )
                elif video_path:
                    multimodal_result = self.sdk.smart_multimodal_chat(
                        prompt=user_input,
                        video_path=video_path,
                        multimodal_provider=llm_provider,
                        multimodal_model=llm_model,
                        tts_provider=tts_provider,
                        tts_model=tts_model,
                        tts_mode="speaker",
                        use_context=use_context,
                        session_id=session_id,
                        **tts_kwargs
                    )
                elif image_paths:
                    multimodal_result = self.sdk.smart_multimodal_chat(
                        prompt=user_input,
                        image_paths=image_paths,
                        multimodal_provider=llm_provider,
                        multimodal_model=llm_model,
                        tts_provider=tts_provider,
                        tts_model=tts_model,
                        tts_mode="speaker",
                        use_context=use_context,
                        session_id=session_id,
                        **tts_kwargs
                    )
                
                # 记录对话
                if multimodal_result and multimodal_result.get('success'):
                    ai_response = multimodal_result.get('answer', '')
                    conversation_record = {
                        "user_input": user_input,
                        "ai_response": ai_response
                    }
                    result["conversations"].append(conversation_record)
                    
                    # 在控制台显示完整的回答文本
                    print(f"\n✓ AI回答: {ai_response}")
                    print("\n✓ 回答完成")
                else:
                    error_msg = multimodal_result.get('error', '未知错误') if multimodal_result else '处理失败'
                    print(f"❌ 多模态处理错误: {error_msg}")
                
                # 如果不是持续对话模式，退出循环
                if not continue_conversation:
                    conversation_active = False
                else:
                    # 激活处理逻辑
                    waiting_for_activation = activation_phrase is not None and (not activate_once or not activated_once)
                    if waiting_for_activation:
                        print("等待下一次激活...")
                    else:
                        print("准备下一轮对话...")
                        
        except KeyboardInterrupt:
            if verbose:
                logger.info("用户中断，结束对话")
            print("\n👋 用户中断，结束对话")
        except Exception as e:
            if verbose:
                logger.error(f"发生错误: {str(e)}")
            print(f"❌ 发生错误: {str(e)}")
            result = {"success": False, "error": str(e), "conversations": result.get("conversations", [])}
        
        print("🎙️🖼️ 智能多模态语音对话已结束")
        return result