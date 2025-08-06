"""
速率限制器
防止API滥用，控制请求频率
"""
import time
from collections import defaultdict, deque
from typing import Dict, Deque
from datetime import datetime, timedelta
import threading

from ..config import RateLimitConfig


class RateLimiter:
    """基于滑动窗口的速率限制器"""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.requests: Dict[str, Deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()
    
    def is_enabled(self) -> bool:
        """检查限流是否启用"""
        return self.config.enabled
    
    def check_rate_limit(self, client_id: str) -> bool:
        """
        检查客户端是否超过速率限制
        
        Args:
            client_id: 客户端标识（通常是IP地址）
            
        Returns:
            True: 允许请求
            False: 超过限制，拒绝请求
        """
        if not self.config.enabled:
            return True
        
        current_time = time.time()
        window_start = current_time - 60  # 60秒窗口
        
        with self.lock:
            # 清理过期的请求记录
            client_requests = self.requests[client_id]
            while client_requests and client_requests[0] < window_start:
                client_requests.popleft()
            
            # 检查是否超过限制
            if len(client_requests) >= self.config.requests_per_minute:
                return False
            
            # 检查突发限制
            recent_requests = sum(1 for req_time in client_requests if req_time > current_time - 10)
            if recent_requests >= self.config.burst_size:
                return False
            
            # 记录当前请求
            client_requests.append(current_time)
            return True
    
    def get_remaining_requests(self, client_id: str) -> int:
        """获取客户端剩余请求数"""
        if not self.config.enabled:
            return float('inf')
        
        current_time = time.time()
        window_start = current_time - 60
        
        with self.lock:
            client_requests = self.requests[client_id]
            # 清理过期记录
            while client_requests and client_requests[0] < window_start:
                client_requests.popleft()
            
            return max(0, self.config.requests_per_minute - len(client_requests))
    
    def get_reset_time(self, client_id: str) -> datetime:
        """获取限制重置时间"""
        if not self.config.enabled:
            return datetime.now()
        
        current_time = time.time()
        window_start = current_time - 60
        
        with self.lock:
            client_requests = self.requests[client_id]
            if not client_requests:
                return datetime.now()
            
            # 找到最早的请求时间
            earliest_request = None
            for req_time in client_requests:
                if req_time > window_start:
                    earliest_request = req_time
                    break
            
            if earliest_request:
                reset_time = earliest_request + 60  # 60秒后重置
                return datetime.fromtimestamp(reset_time)
            else:
                return datetime.now()
    
    def clear_client(self, client_id: str):
        """清除客户端的请求记录"""
        with self.lock:
            if client_id in self.requests:
                del self.requests[client_id]
    
    def get_stats(self) -> Dict[str, any]:
        """获取限流统计信息"""
        with self.lock:
            stats = {
                "enabled": self.config.enabled,
                "requests_per_minute": self.config.requests_per_minute,
                "burst_size": self.config.burst_size,
                "active_clients": len(self.requests),
                "total_tracked_requests": sum(len(reqs) for reqs in self.requests.values())
            }
            return stats