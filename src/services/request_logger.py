"""
请求日志记录器
记录API请求和响应，用于监控和调试
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path


logger = logging.getLogger(__name__)


class RequestLogger:
    """请求日志记录器"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # 创建专门的请求日志记录器
        self.request_logger = logging.getLogger("request_logger")
        self.request_logger.setLevel(logging.INFO)
        
        # 添加文件处理器
        log_file = self.log_dir / "requests.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(message)s')
        )
        self.request_logger.addHandler(file_handler)
        
        # 创建JSON格式的详细日志
        self.detail_logger = logging.getLogger("request_detail_logger")
        self.detail_logger.setLevel(logging.INFO)
        
        detail_log_file = self.log_dir / "requests_detail.jsonl"
        detail_file_handler = logging.FileHandler(detail_log_file, encoding='utf-8')
        detail_file_handler.setFormatter(logging.Formatter('%(message)s'))
        self.detail_logger.addHandler(detail_file_handler)
    
    async def log_request(self, request_data: Dict[str, Any], backend_name: str):
        """记录请求"""
        try:
            timestamp = datetime.now()
            
            # 基本日志记录
            model = request_data.get("model", "unknown")
            message_count = len(request_data.get("messages", []))
            
            log_message = (
                f"请求 - 后端: {backend_name}, 模型: {model}, "
                f"消息数: {message_count}"
            )
            self.request_logger.info(log_message)
            
            # 详细日志记录（JSON格式）
            detail_log = {
                "timestamp": timestamp.isoformat(),
                "type": "request",
                "backend": backend_name,
                "model": model,
                "message_count": message_count,
                "max_tokens": request_data.get("max_tokens"),
                "temperature": request_data.get("temperature"),
                "stream": request_data.get("stream", False)
            }
            
            # 可选：记录完整请求内容（注意隐私）
            if logger.level <= logging.DEBUG:
                detail_log["full_request"] = self._sanitize_request(request_data)
            
            self.detail_logger.info(json.dumps(detail_log, ensure_ascii=False))
            
        except Exception as e:
            logger.error(f"记录请求日志失败: {e}")
    
    async def log_response(self, response_data: Dict[str, Any]):
        """记录响应"""
        try:
            timestamp = datetime.now()
            
            # 提取响应信息
            model = response_data.get("model", "unknown")
            choices = response_data.get("choices", [])
            usage = response_data.get("usage", {})
            
            finish_reason = choices[0].get("finish_reason") if choices else "unknown"
            
            log_message = (
                f"响应 - 模型: {model}, 完成原因: {finish_reason}, "
                f"使用量: {usage}"
            )
            self.request_logger.info(log_message)
            
            # 详细日志记录
            detail_log = {
                "timestamp": timestamp.isoformat(),
                "type": "response",
                "model": model,
                "finish_reason": finish_reason,
                "usage": usage,
                "choices_count": len(choices)
            }
            
            # 可选：记录完整响应内容
            if logger.level <= logging.DEBUG:
                detail_log["full_response"] = self._sanitize_response(response_data)
            
            self.detail_logger.info(json.dumps(detail_log, ensure_ascii=False))
            
        except Exception as e:
            logger.error(f"记录响应日志失败: {e}")
    
    async def log_error(self, error: Exception, backend_name: str, request_data: Optional[Dict[str, Any]] = None):
        """记录错误"""
        try:
            timestamp = datetime.now()
            
            log_message = f"错误 - 后端: {backend_name}, 错误: {str(error)}"
            self.request_logger.error(log_message)
            
            # 详细错误日志
            detail_log = {
                "timestamp": timestamp.isoformat(),
                "type": "error",
                "backend": backend_name,
                "error_type": type(error).__name__,
                "error_message": str(error)
            }
            
            if request_data:
                detail_log["model"] = request_data.get("model", "unknown")
                detail_log["request_id"] = request_data.get("id")
            
            self.detail_logger.error(json.dumps(detail_log, ensure_ascii=False))
            
        except Exception as e:
            logger.error(f"记录错误日志失败: {e}")
    
    def _sanitize_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """清理请求数据，移除敏感信息"""
        sanitized = request_data.copy()
        
        # 截断过长的消息内容
        if "messages" in sanitized:
            messages = []
            for msg in sanitized["messages"]:
                sanitized_msg = msg.copy()
                content = sanitized_msg.get("content", "")
                if len(content) > 500:
                    sanitized_msg["content"] = content[:500] + "... (截断)"
                messages.append(sanitized_msg)
            sanitized["messages"] = messages
        
        return sanitized
    
    def _sanitize_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """清理响应数据，移除敏感信息"""
        sanitized = response_data.copy()
        
        # 截断过长的响应内容
        if "choices" in sanitized:
            choices = []
            for choice in sanitized["choices"]:
                sanitized_choice = choice.copy()
                if "message" in sanitized_choice:
                    message = sanitized_choice["message"].copy()
                    content = message.get("content", "")
                    if len(content) > 500:
                        message["content"] = content[:500] + "... (截断)"
                    sanitized_choice["message"] = message
                choices.append(sanitized_choice)
            sanitized["choices"] = choices
        
        return sanitized