"""
Smart Chat 处理器
负责处理智能对话的内部逻辑
"""

from typing import Dict, Any


class SmartChatHandler:
    """Smart Chat 功能处理器"""
    
    def __init__(self, sdk_instance):
        """
        初始化Smart Chat处理器
        
        Args:
            sdk_instance: AISDK实例
        """
        self.sdk = sdk_instance
    
    def handle_sync(self, prompt: str, llm_provider: str, llm_model: str, 
                   tts_provider: str, tts_mode: str, use_context: bool,
                   session_id: str, stream_chat: bool, llm_kwargs: dict, 
                   tts_kwargs: dict) -> Dict[str, Any]:
        """同步智能对话实现"""
        try:
            print(f"🤔 AI正在思考: {prompt}")
            
            # 获取LLM回答
            if stream_chat and tts_mode == "speaker":
                # 🚀 真正的实时模式：LLM流式输出 + TTS流式合成播放
                print("💬 AI回答（真正的实时语音播放）:")
                answer_parts = []
                
                # 创建流式TTS合成器
                try:
                    streaming_synthesizer = self.sdk.tts_handler.create_streaming_synthesizer(
                        provider=tts_provider,
                        **tts_kwargs
                    )
                    streaming_synthesizer.start()
                    print("🎵 流式TTS合成器已启动")
                except Exception as tts_init_error:
                    print(f"⚠️ 流式TTS初始化失败，回退到句子分割模式: {tts_init_error}")
                    # 回退到原来的句子分割方式
                    return self._handle_sentence_based_synthesis(
                        prompt, llm_provider, llm_model, tts_provider, tts_mode,
                        use_context, session_id, llm_kwargs, tts_kwargs
                    )
                
                try:
                    for chunk in self.sdk.chat(
                        provider=llm_provider,
                        model=llm_model,
                        prompt=prompt,
                        stream=True,
                        use_context=use_context,
                        session_id=session_id,
                        **llm_kwargs
                    ):
                        if 'choices' in chunk and chunk['choices']:
                            delta = chunk['choices'][0].get('delta', {})
                            content = delta.get('content', '')
                            if content:
                                print(content, end='', flush=True)
                                answer_parts.append(content)
                                
                                # 🎵 实时将每个字符/词发送给TTS合成器
                                streaming_synthesizer.add_text(content)
                    
                    # 完成流式合成
                    request_id = streaming_synthesizer.complete()
                    answer = ''.join(answer_parts)
                    print("\n🎉 真正的实时语音播放完成!")
                    
                    return {
                        'success': True,
                        'answer': answer,
                        'llm_provider': llm_provider,
                        'llm_model': llm_model,
                        'tts_provider': tts_provider,
                        'tts_model': tts_kwargs.get('model'),
                        'tts_mode': 'true_realtime_speaker',
                        'tts_result': {'success': True, 'mode': 'true_realtime', 'request_id': request_id}
                    }
                    
                except Exception as e:
                    print(f"\n❌ 实时合成过程出错: {e}")
                    return {
                        'success': False,
                        'error': f"实时合成过程出错: {str(e)}"
                    }
                finally:
                    # 确保关闭合成器
                    try:
                        streaming_synthesizer.close()
                    except Exception as close_error:
                        print(f"⚠️ 关闭流式合成器时出错: {close_error}")
                        # 不再抛出异常，避免影响主流程
                
            elif stream_chat:
                # 流式输出但不实时播放（用于文件模式等）
                print("💬 AI回答:")
                answer_parts = []
                
                for chunk in self.sdk.chat(
                    provider=llm_provider,
                    model=llm_model,
                    prompt=prompt,
                    stream=True,
                    use_context=use_context,
                    session_id=session_id,
                    **llm_kwargs
                ):
                    if 'choices' in chunk and chunk['choices']:
                        delta = chunk['choices'][0].get('delta', {})
                        content = delta.get('content', '')
                        if content:
                            print(content, end='', flush=True)
                            answer_parts.append(content)
                
                answer = ''.join(answer_parts)
                print()  # 换行
            else:
                # 普通输出
                response = self.sdk.chat(
                    provider=llm_provider,
                    model=llm_model,
                    prompt=prompt,
                    use_context=use_context,
                    session_id=session_id,
                    **llm_kwargs
                )
                
                if 'choices' in response and response['choices']:
                    answer = response['choices'][0]['message']['content']
                    print(f"💬 AI回答: {answer}")
                else:
                    return {
                        'success': False,
                        'error': '未获取到有效的LLM回答',
                        'llm_response': response
                    }
            
            # 非实时模式的语音合成（文件保存等）
            if not (stream_chat and tts_mode == "speaker"):
                if answer.strip():
                    print(f"\n🔄 正在将回答转换为语音...")
                    
                    tts_result = self.sdk.tts(
                        provider=tts_provider,
                        mode=tts_mode,
                        text=answer,
                        **tts_kwargs
                    )
                    
                    if tts_result['success']:
                        if tts_mode == "speaker":
                            print("🎉 语音播放完成!")
                        elif tts_mode == "file":
                            print(f"🎉 语音文件已保存: {tts_result.get('output_file', '未知')}")
                        else:
                            print("🎉 语音合成完成!")
                    else:
                        print(f"❌ 语音合成失败: {tts_result['error']}")
                    
                    return {
                        'success': True,
                        'answer': answer,
                        'llm_provider': llm_provider,
                        'llm_model': llm_model,
                        'tts_provider': tts_provider,
                        'tts_model': tts_kwargs.get('model'),
                        'tts_mode': tts_mode,
                        'tts_result': tts_result
                    }
                else:
                    return {
                        'success': False,
                        'error': 'LLM返回了空回答',
                        'answer': answer
                    }
            
            # 实时模式已经在上面处理并返回了
            return {
                'success': True,
                'answer': answer,
                'llm_provider': llm_provider,
                'llm_model': llm_model,
                'tts_provider': tts_provider,
                'tts_model': tts_kwargs.get('model'),
                'tts_mode': tts_mode,
                'tts_result': {'success': True, 'mode': 'realtime'}
            }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"智能对话过程出错: {str(e)}"
            }
    
    def _handle_sentence_based_synthesis(self, prompt: str, llm_provider: str, llm_model: str,
                                       tts_provider: str, tts_mode: str, use_context: bool,
                                       session_id: str, llm_kwargs: dict, tts_kwargs: dict) -> Dict[str, Any]:
        """句子分割模式的实时合成（回退方案）"""
        print("💬 AI回答（句子分割模式）:")
        answer_parts = []
        sentence_buffer = ""  # 句子缓冲区
        
        for chunk in self.sdk.chat(
            provider=llm_provider,
            model=llm_model,
            prompt=prompt,
            stream=True,
            use_context=use_context,
            session_id=session_id,
            **llm_kwargs
        ):
            if 'choices' in chunk and chunk['choices']:
                delta = chunk['choices'][0].get('delta', {})
                content = delta.get('content', '')
                if content:
                    print(content, end='', flush=True)
                    answer_parts.append(content)
                    sentence_buffer += content
                    
                    # 检查是否形成完整句子（以句号、问号、感叹号结尾）
                    if any(punct in sentence_buffer for punct in ['。', '！', '？', '.', '!', '?']):
                        # 找到句子结束位置
                        for punct in ['。', '！', '？', '.', '!', '?']:
                            if punct in sentence_buffer:
                                sentence_end = sentence_buffer.find(punct) + 1
                                complete_sentence = sentence_buffer[:sentence_end].strip()
                                
                                if complete_sentence:
                                    # 🎵 合成并播放这个句子
                                    try:
                                        self.sdk.tts(
                                            provider=tts_provider,
                                            mode="speaker",
                                            text=complete_sentence,
                                            **tts_kwargs
                                        )
                                    except Exception as tts_error:
                                        print(f"\n⚠️ TTS播放出错: {tts_error}")
                                
                                # 更新缓冲区，保留未处理的部分
                                sentence_buffer = sentence_buffer[sentence_end:].strip()
                                break
        
        # 处理最后剩余的文本
        if sentence_buffer.strip():
            try:
                self.sdk.tts(
                    provider=tts_provider,
                    mode="speaker", 
                    text=sentence_buffer.strip(),
                    **tts_kwargs
                )
            except Exception as tts_error:
                print(f"\n⚠️ 最后片段TTS播放出错: {tts_error}")
        
        answer = ''.join(answer_parts)
        print("\n🎉 句子分割模式语音播放完成!")
        
        return {
            'success': True,
            'answer': answer,
            'llm_provider': llm_provider,
            'llm_model': llm_model,
            'tts_provider': tts_provider,
            'tts_model': tts_kwargs.get('model'),
            'tts_mode': 'sentence_based_speaker',
            'tts_result': {'success': True, 'mode': 'sentence_based'}
        }
    
    async def handle_async(self, prompt: str, llm_provider: str, llm_model: str,
                          tts_provider: str, tts_mode: str, use_context: bool,
                          session_id: str, stream_chat: bool, llm_kwargs: dict,
                          tts_kwargs: dict) -> Dict[str, Any]:
        """异步智能对话实现"""
        try:
            print(f"🤔 AI正在思考: {prompt}")
            
            # 获取LLM回答
            if stream_chat and tts_mode == "speaker":
                # 🚀 真正的异步实时模式：LLM流式输出 + TTS流式合成播放
                print("💬 AI回答（真正的异步实时语音播放）:")
                answer_parts = []
                
                # 创建流式TTS合成器
                try:
                    streaming_synthesizer = self.sdk.tts_handler.create_streaming_synthesizer(
                        provider=tts_provider,
                        **tts_kwargs
                    )
                    streaming_synthesizer.start()
                    print("🎵 异步流式TTS合成器已启动")
                except Exception as tts_init_error:
                    print(f"⚠️ 异步流式TTS初始化失败，回退到句子分割模式: {tts_init_error}")
                    # 回退到原来的句子分割方式
                    return await self._handle_sentence_based_synthesis_async(
                        prompt, llm_provider, llm_model, tts_provider, tts_mode,
                        use_context, session_id, llm_kwargs, tts_kwargs
                    )
                
                try:
                    async for chunk in self.sdk.chat(
                        provider=llm_provider,
                        model=llm_model,
                        prompt=prompt,
                        stream=True,
                        async_mode=True,
                        use_context=use_context,
                        session_id=session_id,
                        **llm_kwargs
                    ):
                        if 'choices' in chunk and chunk['choices']:
                            delta = chunk['choices'][0].get('delta', {})
                            content = delta.get('content', '')
                            if content:
                                print(content, end='', flush=True)
                                answer_parts.append(content)
                                
                                # 🎵 实时将每个字符/词发送给TTS合成器
                                streaming_synthesizer.add_text(content)
                    
                    # 完成流式合成
                    request_id = streaming_synthesizer.complete()
                    answer = ''.join(answer_parts)
                    print("\n🎉 真正的异步实时语音播放完成!")
                    
                    return {
                        'success': True,
                        'answer': answer,
                        'llm_provider': llm_provider,
                        'llm_model': llm_model,
                        'tts_provider': tts_provider,
                        'tts_model': tts_kwargs.get('model'),
                        'tts_mode': 'true_async_realtime_speaker',
                        'tts_result': {'success': True, 'mode': 'true_async_realtime', 'request_id': request_id}
                    }
                    
                except Exception as e:
                    print(f"\n❌ 异步实时合成过程出错: {e}")
                    return {
                        'success': False,
                        'error': f"异步实时合成过程出错: {str(e)}"
                    }
                finally:
                    # 确保关闭合成器
                    try:
                        streaming_synthesizer.close()
                    except Exception as close_error:
                        print(f"⚠️ 关闭流式合成器时出错: {close_error}")
                        # 不再抛出异常，避免影响主流程
                
            elif stream_chat:
                # 异步流式输出但不实时播放（用于文件模式等）
                print("💬 AI回答:")
                answer_parts = []
                
                async for chunk in self.sdk.chat(
                    provider=llm_provider,
                    model=llm_model,
                    prompt=prompt,
                    stream=True,
                    async_mode=True,
                    use_context=use_context,
                    session_id=session_id,
                    **llm_kwargs
                ):
                    if 'choices' in chunk and chunk['choices']:
                        delta = chunk['choices'][0].get('delta', {})
                        content = delta.get('content', '')
                        if content:
                            print(content, end='', flush=True)
                            answer_parts.append(content)
                
                answer = ''.join(answer_parts)
                print()  # 换行
            else:
                # 异步普通输出
                response = await self.sdk.chat(
                    provider=llm_provider,
                    model=llm_model,
                    prompt=prompt,
                    async_mode=True,
                    use_context=use_context,
                    session_id=session_id,
                    **llm_kwargs
                )
                
                if 'choices' in response and response['choices']:
                    answer = response['choices'][0]['message']['content']
                    print(f"💬 AI回答: {answer}")
                else:
                    return {
                        'success': False,
                        'error': '未获取到有效的LLM回答',
                        'llm_response': response
                    }
            
            # 非实时模式的异步语音合成（文件保存等）
            if not (stream_chat and tts_mode == "speaker"):
                if answer.strip():
                    print(f"\n🔄 正在将回答转换为语音...")
                    
                    tts_result = await self.sdk.tts(
                        provider=tts_provider,
                        mode=tts_mode,
                        text=answer,
                        async_mode=True,
                        **tts_kwargs
                    )
                    
                    if tts_result['success']:
                        if tts_mode == "speaker":
                            print("🎉 异步语音播放完成!")
                        elif tts_mode == "file":
                            print(f"🎉 异步语音文件已保存: {tts_result.get('output_file', '未知')}")
                        else:
                            print("🎉 异步语音合成完成!")
                    else:
                        print(f"❌ 异步语音合成失败: {tts_result['error']}")
                    
                    return {
                        'success': True,
                        'answer': answer,
                        'llm_provider': llm_provider,
                        'llm_model': llm_model,
                        'tts_provider': tts_provider,
                        'tts_model': tts_kwargs.get('model'),
                        'tts_mode': tts_mode,
                        'tts_result': tts_result
                    }
                else:
                    return {
                        'success': False,
                        'error': 'LLM返回了空回答',
                        'answer': answer
                    }
            
            # 异步实时模式已经在上面处理并返回了
            return {
                'success': True,
                'answer': answer,
                'llm_provider': llm_provider,
                'llm_model': llm_model,
                'tts_provider': tts_provider,
                'tts_model': tts_kwargs.get('model'),
                'tts_mode': tts_mode,
                'tts_result': {'success': True, 'mode': 'async_realtime'}
            }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"异步智能对话过程出错: {str(e)}"
            }
    
    async def _handle_sentence_based_synthesis_async(self, prompt: str, llm_provider: str, llm_model: str,
                                                   tts_provider: str, tts_mode: str, use_context: bool,
                                                   session_id: str, llm_kwargs: dict, tts_kwargs: dict) -> Dict[str, Any]:
        """异步句子分割模式的实时合成（回退方案）"""
        print("💬 AI回答（异步句子分割模式）:")
        answer_parts = []
        sentence_buffer = ""  # 句子缓冲区
        
        async for chunk in self.sdk.chat(
            provider=llm_provider,
            model=llm_model,
            prompt=prompt,
            stream=True,
            async_mode=True,
            use_context=use_context,
            session_id=session_id,
            **llm_kwargs
        ):
            if 'choices' in chunk and chunk['choices']:
                delta = chunk['choices'][0].get('delta', {})
                content = delta.get('content', '')
                if content:
                    print(content, end='', flush=True)
                    answer_parts.append(content)
                    sentence_buffer += content
                    
                    # 检查是否形成完整句子（以句号、问号、感叹号结尾）
                    if any(punct in sentence_buffer for punct in ['。', '！', '？', '.', '!', '?']):
                        # 找到句子结束位置
                        for punct in ['。', '！', '？', '.', '!', '?']:
                            if punct in sentence_buffer:
                                sentence_end = sentence_buffer.find(punct) + 1
                                complete_sentence = sentence_buffer[:sentence_end].strip()
                                
                                if complete_sentence:
                                    # 🎵 异步合成并播放这个句子
                                    try:
                                        await self.sdk.tts(
                                            provider=tts_provider,
                                            mode="speaker",
                                            text=complete_sentence,
                                            async_mode=True,
                                            **tts_kwargs
                                        )
                                    except Exception as tts_error:
                                        print(f"\n⚠️ 异步TTS播放出错: {tts_error}")
                                
                                # 更新缓冲区，保留未处理的部分
                                sentence_buffer = sentence_buffer[sentence_end:].strip()
                                break
        
        # 处理最后剩余的文本
        if sentence_buffer.strip():
            try:
                await self.sdk.tts(
                    provider=tts_provider,
                    mode="speaker", 
                    text=sentence_buffer.strip(),
                    async_mode=True,
                    **tts_kwargs
                )
            except Exception as tts_error:
                print(f"\n⚠️ 最后片段异步TTS播放出错: {tts_error}")
        
        answer = ''.join(answer_parts)
        print("\n🎉 异步句子分割模式语音播放完成!")
        
        return {
            'success': True,
            'answer': answer,
            'llm_provider': llm_provider,
            'llm_model': llm_model,
            'tts_provider': tts_provider,
            'tts_model': tts_kwargs.get('model'),
            'tts_mode': 'async_sentence_based_speaker',
            'tts_result': {'success': True, 'mode': 'async_sentence_based'}
        } 