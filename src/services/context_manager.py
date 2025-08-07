"""
上下文管理器 - 维护对话会话和记忆功能
"""
import asyncio
import hashlib
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """消息对象"""
    role: str  # user, assistant, system
    content: str
    timestamp: float


@dataclass
class Session:
    """会话对象"""
    session_id: str
    messages: List[Message]
    created_at: float
    last_activity: float
    client_info: Dict[str, str]


class ContextManager:
    """上下文管理器 - 智能会话管理和记忆系统"""
    
    def __init__(self, 
                 max_context_messages: int = 20,  # 每个会话最大消息数
                 session_timeout_minutes: int = 30,  # 会话超时时间
                 max_sessions: int = 1000,  # 最大会话数
                 cleanup_interval_minutes: int = 10):  # 清理间隔
        
        self.max_context_messages = max_context_messages
        self.session_timeout = session_timeout_minutes * 60
        self.max_sessions = max_sessions
        self.cleanup_interval = cleanup_interval_minutes * 60
        
        self.sessions: Dict[str, Session] = {}
        self.last_cleanup = time.time()
        
        logger.info(f"🧠 上下文管理器初始化完成")
        logger.info(f"📋 配置: 最大消息数={max_context_messages}, 超时={session_timeout_minutes}分钟")
    
    def generate_session_id(self, client_ip: str, user_agent: str = "") -> str:
        """生成会话ID"""
        # 使用客户端IP和User-Agent生成稳定的会话ID
        identifier = f"{client_ip}:{user_agent}"
        session_id = hashlib.md5(identifier.encode()).hexdigest()[:12]
        return f"session_{session_id}"
    
    async def get_or_create_session(self, client_ip: str, user_agent: str = "") -> Session:
        """获取或创建会话"""
        session_id = self.generate_session_id(client_ip, user_agent)
        current_time = time.time()
        
        # 检查是否需要清理过期会话
        if current_time - self.last_cleanup > self.cleanup_interval:
            await self._cleanup_expired_sessions()
        
        if session_id in self.sessions:
            # 更新最后活动时间
            session = self.sessions[session_id]
            session.last_activity = current_time
            logger.debug(f"📱 使用现有会话: {session_id}, 消息数: {len(session.messages)}")
            return session
        else:
            # 创建新会话
            session = Session(
                session_id=session_id,
                messages=[],
                created_at=current_time,
                last_activity=current_time,
                client_info={"ip": client_ip, "user_agent": user_agent}
            )
            self.sessions[session_id] = session
            logger.info(f"🆕 创建新会话: {session_id} (来自 {client_ip})")
            
            # 检查会话数量限制
            if len(self.sessions) > self.max_sessions:
                await self._remove_oldest_sessions()
            
            return session
    
    async def add_message(self, session: Session, role: str, content: str):
        """添加消息到会话"""
        message = Message(
            role=role,
            content=content,
            timestamp=time.time()
        )
        
        session.messages.append(message)
        session.last_activity = time.time()
        
        # 限制上下文长度，保留最近的消息
        if len(session.messages) > self.max_context_messages:
            removed_count = len(session.messages) - self.max_context_messages
            session.messages = session.messages[-self.max_context_messages:]
            logger.debug(f"🗑️ 会话 {session.session_id} 清理了 {removed_count} 条旧消息")
        
        logger.debug(f"💬 会话 {session.session_id} 添加消息: {role} ({len(content)} 字符)")
    
    def get_context_messages(self, session: Session) -> List[Dict[str, str]]:
        """获取会话的上下文消息（OpenAI格式）"""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in session.messages
        ]
    
    def format_context_for_claude(self, session: Session, new_question: str) -> str:
        """为Claude CLI格式化优化的对话上下文"""
        if not session.messages:
            return new_question
        
        # 🔥 优化策略：智能上下文管理
        if len(session.messages) <= 4:  # 前2轮对话，保持完整上下文
            return self._format_full_context(session.messages, new_question)
        else:  # 多轮对话，使用压缩上下文
            return self._format_compressed_context(session.messages, new_question)
    
    def _format_full_context(self, messages: list, new_question: str) -> str:
        """格式化完整上下文（用于短对话）"""
        context_lines = ["# 对话历史", ""]
        
        for i, msg in enumerate(messages, 1):
            if msg.role == "user":
                context_lines.append(f"## 用户问题 {i}")
                context_lines.append(msg.content)
                context_lines.append("")
            elif msg.role == "assistant":
                context_lines.append(f"## Claude回答 {i}")
                # 限制回答长度，避免上下文过长
                content = msg.content[:200] + ("..." if len(msg.content) > 200 else "")
                context_lines.append(content)
                context_lines.append("")
        
        context_lines.extend([
            f"## 当前问题",
            new_question,
            "",
            "---",
            "请基于以上对话历史回答当前问题。"
        ])
        
        return "\n".join(context_lines)
    
    def _format_compressed_context(self, messages: list, new_question: str) -> str:
        """格式化压缩上下文（用于长对话）"""
        # 策略：保留最近3轮对话 + 早期关键信息摘要
        recent_messages = messages[-6:]  # 最近3轮（6条消息）
        
        context_lines = ["# 对话摘要", ""]
        
        # 添加早期信息摘要
        if len(messages) > 6:
            early_messages = messages[:-6]
            summary_info = self._extract_key_info(early_messages)
            if summary_info:
                context_lines.append("## 早期对话要点")
                context_lines.append(summary_info)
                context_lines.append("")
        
        # 添加最近对话
        context_lines.append("## 最近对话")
        for i, msg in enumerate(recent_messages):
            if msg.role == "user":
                context_lines.append(f"用户: {msg.content}")
            else:
                # 压缩Assistant回复
                content = msg.content[:150] + ("..." if len(msg.content) > 150 else "")
                context_lines.append(f"Claude: {content}")
        
        context_lines.extend([
            "",
            f"## 当前问题",
            new_question,
            "",
            "---",
            "请基于对话摘要和最近对话回答当前问题。"
        ])
        
        return "\n".join(context_lines)
    
    def _extract_key_info(self, messages: list) -> str:
        """从早期消息中提取关键信息"""
        key_info = []
        
        for msg in messages:
            if msg.role == "user":
                # 提取可能的关键信息（姓名、年龄、职业等）
                content = msg.content
                if any(keyword in content for keyword in ["我叫", "我是", "我的名字", "我今年", "我住在"]):
                    key_info.append(content[:100])
        
        return "; ".join(key_info[:3])  # 最多保留3条关键信息
    
    async def _cleanup_expired_sessions(self):
        """清理过期会话"""
        current_time = time.time()
        expired_sessions = []
        
        for session_id, session in self.sessions.items():
            if current_time - session.last_activity > self.session_timeout:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
        
        if expired_sessions:
            logger.info(f"🧹 清理了 {len(expired_sessions)} 个过期会话")
        
        self.last_cleanup = current_time
    
    async def _remove_oldest_sessions(self):
        """移除最旧的会话"""
        if len(self.sessions) <= self.max_sessions:
            return
        
        # 按最后活动时间排序，移除最旧的
        sorted_sessions = sorted(
            self.sessions.items(),
            key=lambda x: x[1].last_activity
        )
        
        sessions_to_remove = len(self.sessions) - self.max_sessions + 5  # 多删除5个，避免频繁清理
        
        for i in range(sessions_to_remove):
            session_id = sorted_sessions[i][0]
            del self.sessions[session_id]
        
        logger.info(f"🗑️ 移除了 {sessions_to_remove} 个最旧会话，当前会话数: {len(self.sessions)}")
    
    def get_session_stats(self) -> Dict[str, Any]:
        """获取会话统计信息"""
        current_time = time.time()
        active_sessions = sum(1 for s in self.sessions.values() 
                            if current_time - s.last_activity < 300)  # 5分钟内活跃
        
        total_messages = sum(len(s.messages) for s in self.sessions.values())
        
        return {
            "total_sessions": len(self.sessions),
            "active_sessions": active_sessions,
            "total_messages": total_messages,
            "max_context_messages": self.max_context_messages,
            "session_timeout_minutes": self.session_timeout // 60
        }
    
    async def clear_session(self, session_id: str) -> bool:
        """清空指定会话的对话历史"""
        if session_id in self.sessions:
            self.sessions[session_id].messages = []
            logger.info(f"🗑️ 已清空会话 {session_id} 的对话历史")
            return True
        return False
    
    async def delete_session(self, session_id: str) -> bool:
        """删除指定会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"🗑️ 已删除会话 {session_id}")
            return True
        return False