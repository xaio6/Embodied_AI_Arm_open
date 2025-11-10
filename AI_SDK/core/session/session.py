"""
对话会话管理模块
"""

import time
import uuid
import threading
from typing import Dict, List, Any, Optional
from ...utils.exceptions import AISDKException

class ChatSession:
    """对话会话类"""
    
    def __init__(self, session_id: str = None, max_history: int = 20):
        """
        初始化对话会话
        
        Args:
            session_id: 会话ID，如果不提供则自动生成
            max_history: 最大历史记录数量，防止上下文过长
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.max_history = max_history
        self.messages: List[Dict[str, str]] = []
        self.created_at = time.time()
        self.updated_at = time.time()
        self.system_prompt: Optional[str] = None
        self.metadata: Dict[str, Any] = {}
        self._lock = threading.Lock()  # 线程安全
    
    def set_system_prompt(self, system_prompt: str):
        """
        设置系统提示词
        
        Args:
            system_prompt: 系统提示词
        """
        with self._lock:
            self.system_prompt = system_prompt
            self.updated_at = time.time()
    
    def add_message(self, role: str, content: str):
        """
        添加消息到历史记录
        
        Args:
            role: 角色 (user, assistant, system)
            content: 消息内容
        """
        if role not in ['user', 'assistant', 'system']:
            raise AISDKException(f"无效的角色: {role}")
        
        with self._lock:
            message = {
                "role": role,
                "content": content,
                "timestamp": time.time()
            }
            
            self.messages.append(message)
            self.updated_at = time.time()
            
            # 限制历史记录长度，保留最近的对话
            if len(self.messages) > self.max_history:
                # 保留系统消息，删除最早的用户/助手消息
                system_messages = [msg for msg in self.messages if msg['role'] == 'system']
                other_messages = [msg for msg in self.messages if msg['role'] != 'system']
                
                # 保留最近的对话
                other_messages = other_messages[-(self.max_history - len(system_messages)):]
                self.messages = system_messages + other_messages
    
    def get_messages(self, include_system: bool = True) -> List[Dict[str, str]]:
        """
        获取消息历史
        
        Args:
            include_system: 是否包含系统消息
            
        Returns:
            消息列表
        """
        with self._lock:
            if include_system:
                return [{"role": msg["role"], "content": msg["content"]} for msg in self.messages]
            else:
                return [{"role": msg["role"], "content": msg["content"]} 
                       for msg in self.messages if msg["role"] != "system"]
    
    def clear_history(self):
        """清空历史记录"""
        with self._lock:
            self.messages = []
            self.updated_at = time.time()
    
    def get_context_info(self) -> Dict[str, Any]:
        """
        获取上下文信息
        
        Returns:
            上下文信息字典
        """
        with self._lock:
            return {
                "session_id": self.session_id,
                "message_count": len(self.messages),
                "max_history": self.max_history,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "has_system_prompt": self.system_prompt is not None,
                "system_prompt": self.system_prompt,
                "metadata": self.metadata.copy()
            }

class SessionManager:
    """会话管理器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化会话管理器
        
        Args:
            config: 配置字典
        """
        self.sessions: Dict[str, ChatSession] = {}
        self._lock = threading.Lock()
        self.config = config or {}
        
        # 从配置获取设置
        session_config = self.config.get('session', {})
        self.default_max_history = session_config.get('default_max_history', 20)
        self.auto_cleanup = session_config.get('auto_cleanup', True)
        self.cleanup_interval = session_config.get('cleanup_interval', 3600)
        self.max_sessions = session_config.get('max_sessions', 100)
        
        # 启动自动清理
        if self.auto_cleanup:
            self._start_auto_cleanup()
    
    def create_session(self, session_id: str = None, max_history: int = None) -> ChatSession:
        """
        创建新的对话会话
        
        Args:
            session_id: 会话ID
            max_history: 最大历史记录数量，默认使用配置值
            
        Returns:
            对话会话对象
        """
        if max_history is None:
            max_history = self.default_max_history
        
        with self._lock:
            # 检查会话数量限制
            if len(self.sessions) >= self.max_sessions:
                # 删除最旧的会话
                oldest_session_id = min(self.sessions.keys(), 
                                      key=lambda x: self.sessions[x].updated_at)
                del self.sessions[oldest_session_id]
            
            session = ChatSession(session_id, max_history)
            self.sessions[session.session_id] = session
            return session
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        获取对话会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            对话会话对象或None
        """
        with self._lock:
            return self.sessions.get(session_id)
    
    def delete_session(self, session_id: str) -> bool:
        """
        删除对话会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否删除成功
        """
        with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                return True
            return False
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        列出所有会话
        
        Returns:
            会话信息列表
        """
        with self._lock:
            return [session.get_context_info() for session in self.sessions.values()]
    
    def cleanup_old_sessions(self, max_age: int = None):
        """
        清理过期会话
        
        Args:
            max_age: 最大存活时间（秒），默认使用配置值
        """
        if max_age is None:
            max_age = self.cleanup_interval
        
        current_time = time.time()
        
        with self._lock:
            expired_sessions = [
                session_id for session_id, session in self.sessions.items()
                if current_time - session.updated_at > max_age
            ]
            
            for session_id in expired_sessions:
                del self.sessions[session_id]
        
        if expired_sessions:
            import logging
            logging.info(f"清理了 {len(expired_sessions)} 个过期会话")
    
    def _start_auto_cleanup(self):
        """启动自动清理线程"""
        import threading
        import time
        
        def cleanup_worker():
            while True:
                time.sleep(self.cleanup_interval)
                self.cleanup_old_sessions()
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取会话管理器统计信息
        
        Returns:
            统计信息
        """
        with self._lock:
            total_sessions = len(self.sessions)
            total_messages = sum(len(session.messages) for session in self.sessions.values())
            
            return {
                'total_sessions': total_sessions,
                'total_messages': total_messages,
                'max_sessions': self.max_sessions,
                'default_max_history': self.default_max_history,
                'auto_cleanup': self.auto_cleanup,
                'cleanup_interval': self.cleanup_interval
            } 