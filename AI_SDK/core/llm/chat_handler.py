"""
聊天处理器 - 处理所有聊天相关的逻辑
"""

from typing import Iterator, AsyncIterator, Dict, Any, List, Optional, Union
from ..session import ChatSession, SessionManager
from ...services.llm import LLMService


class ChatHandler:
    """
    聊天处理器 - 负责处理所有聊天相关的逻辑
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化聊天处理器
        
        Args:
            config: 配置字典
        """
        self.config = config
        # 初始化语言模型服务
        self.llm_service = LLMService(config)
        # 初始化会话管理器
        self.session_manager = SessionManager(config)
        # 初始化全局对话历史
        self.global_conversation_history = []
    
    def handle_chat(self, 
                   provider: str, 
                   model: str, 
                   prompt: str,
                   stream: bool = False,
                   async_mode: bool = False,
                   use_context: bool = False,
                   session_id: str = None,
                   **kwargs) -> Union[Dict[str, Any], Iterator[Dict[str, Any]], AsyncIterator[Dict[str, Any]]]:
        """
        处理聊天请求
        
        Args:
            provider: 提供商名称
            model: 模型名称
            prompt: 提示词
            stream: 是否启用流式输出
            async_mode: 是否使用异步模式
            use_context: 是否启用上下文对话
            session_id: 会话ID
            **kwargs: 其他参数
            
        Returns:
            聊天响应
        """
        # 处理上下文对话
        if use_context:
            if session_id:
                # 使用指定会话
                session = self._get_or_create_session(session_id)
                kwargs['history'] = session.get_messages()
            else:
                # 使用全局历史
                kwargs['history'] = self.global_conversation_history
        
        # 根据参数选择调用方式
        if async_mode:
            if stream:
                return self._chat_stream_async(provider, model, prompt, use_context, session_id, **kwargs)
            else:
                return self._chat_async(provider, model, prompt, use_context, session_id, **kwargs)
        else:
            if stream:
                return self._chat_stream(provider, model, prompt, use_context, session_id, **kwargs)
            else:
                return self._chat_sync(provider, model, prompt, use_context, session_id, **kwargs)

    def _chat_sync(self, provider: str, model: str, prompt: str, use_context: bool, session_id: str, **kwargs) -> Dict[str, Any]:
        """同步聊天"""
        response = self.llm_service.chat(provider, model, prompt, **kwargs)
        
        # 更新上下文
        if use_context:
            self._update_context(prompt, response['choices'][0]['message']['content'], session_id)
        
        return response

    def _chat_stream(self, provider: str, model: str, prompt: str, use_context: bool, session_id: str, **kwargs) -> Iterator[Dict[str, Any]]:
        """同步流式聊天"""
        full_content = ""
        
        # 添加用户消息到上下文
        if use_context:
            self._add_user_message(prompt, session_id)
        
        for chunk in self.llm_service.chat_stream(provider, model, prompt, **kwargs):
            content = chunk['choices'][0]['delta']['content']
            full_content += content
            yield chunk
        
        # 添加完整的助手回复到上下文
        if use_context:
            self._add_assistant_message(full_content, session_id)

    async def _chat_async(self, provider: str, model: str, prompt: str, use_context: bool, session_id: str, **kwargs) -> Dict[str, Any]:
        """异步聊天"""
        response = await self.llm_service.chat_async(provider, model, prompt, **kwargs)
        
        # 更新上下文
        if use_context:
            self._update_context(prompt, response['choices'][0]['message']['content'], session_id)
        
        return response

    async def _chat_stream_async(self, provider: str, model: str, prompt: str, use_context: bool, session_id: str, **kwargs) -> AsyncIterator[Dict[str, Any]]:
        """异步流式聊天"""
        full_content = ""
        
        # 添加用户消息到上下文
        if use_context:
            self._add_user_message(prompt, session_id)
        
        async for chunk in self.llm_service.chat_stream_async(provider, model, prompt, **kwargs):
            content = chunk['choices'][0]['delta']['content']
            full_content += content
            yield chunk
        
        # 添加完整的助手回复到上下文
        if use_context:
            self._add_assistant_message(full_content, session_id)

    def _update_context(self, user_message: str, assistant_message: str, session_id: str = None):
        """更新上下文"""
        if session_id:
            session = self._get_or_create_session(session_id)
            session.add_message("user", user_message)
            session.add_message("assistant", assistant_message)
        else:
            self.global_conversation_history.append({"role": "user", "content": user_message})
            self.global_conversation_history.append({"role": "assistant", "content": assistant_message})

    def _add_user_message(self, message: str, session_id: str = None):
        """添加用户消息到上下文"""
        if session_id:
            session = self._get_or_create_session(session_id)
            session.add_message("user", message)
        else:
            self.global_conversation_history.append({"role": "user", "content": message})

    def _add_assistant_message(self, message: str, session_id: str = None):
        """添加助手消息到上下文"""
        if session_id:
            session = self._get_or_create_session(session_id)
            session.add_message("assistant", message)
        else:
            self.global_conversation_history.append({"role": "assistant", "content": message})

    def _get_or_create_session(self, session_id: str) -> ChatSession:
        """获取或创建会话"""
        session = self.session_manager.get_session(session_id)
        if not session:
            max_history = self.config.get('session', {}).get('default_max_history', 20)
            session = self.session_manager.create_session(session_id, max_history)
        return session

    # 上下文管理方法
    def get_conversation_history(self, session_id: str = None) -> List[Dict[str, str]]:
        """获取会话历史记录"""
        if session_id:
            session = self.session_manager.get_session(session_id)
            return session.get_messages() if session else []
        else:
            return self.global_conversation_history.copy()

    def clear_conversation_history(self, session_id: str = None):
        """清空会话历史记录"""
        if session_id:
            session = self.session_manager.get_session(session_id)
            if session:
                session.clear_history()
        else:
            self.global_conversation_history.clear()

    def set_conversation_history(self, history: List[Dict[str, str]], session_id: str = None):
        """设置会话历史记录"""
        if session_id:
            session = self._get_or_create_session(session_id)
            session.clear_history()
            for msg in history:
                session.add_message(msg['role'], msg['content'])
        else:
            self.global_conversation_history = history.copy()

    # 会话管理方法
    def create_session(self, session_id: str = None, max_history: int = None, 
                      system_prompt: str = None) -> ChatSession:
        """创建新的对话会话"""
        if max_history is None:
            max_history = self.config.get('session', {}).get('default_max_history', 20)
        
        session = self.session_manager.create_session(session_id, max_history)
        if system_prompt:
            session.set_system_prompt(system_prompt)
        return session
    
    def get_session(self, session_id: str) -> ChatSession:
        """获取对话会话"""
        session = self.session_manager.get_session(session_id)
        if not session:
            from utils.exceptions import AISDKException
            raise AISDKException(f"会话不存在: {session_id}")
        return session
    
    def delete_session(self, session_id: str) -> bool:
        """删除对话会话"""
        return self.session_manager.delete_session(session_id)
    
    def list_sessions(self):
        """列出所有会话"""
        return self.session_manager.list_sessions()

    # 提供商和模型信息
    def get_available_providers(self) -> Dict[str, Dict[str, Any]]:
        """获取可用的提供商列表"""
        return self.llm_service.get_available_providers()

    def get_provider_models(self, provider: str) -> Dict[str, Any]:
        """获取指定提供商的模型列表"""
        return self.llm_service.get_provider_models(provider) 