"""
后端服务管理器
负责管理多个AI后端服务的连接和请求转发
"""
import asyncio
import httpx
import logging
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta

from ..config import get_config, config_manager, BackendConfig


logger = logging.getLogger(__name__)


class BackendManager:
    """后端服务管理器"""
    
    def __init__(self):
        self.clients: Dict[str, httpx.AsyncClient] = {}
        self.health_status: Dict[str, bool] = {}
        self.last_health_check: Dict[str, datetime] = {}
        self.initialize_clients()
    
    def initialize_clients(self):
        """初始化HTTP客户端"""
        enabled_backends = config_manager.get_enabled_backends()
        
        for name, backend in enabled_backends.items():
            self.clients[name] = httpx.AsyncClient(
                base_url=backend.base_url,
                timeout=httpx.Timeout(backend.timeout),
                headers=self._get_headers(name, backend)
            )
            self.health_status[name] = True  # 假设初始状态健康
            logger.info(f"初始化后端客户端: {name} ({backend.base_url})")
    
    def _get_headers(self, backend_name: str, backend: BackendConfig) -> Dict[str, str]:
        """获取后端请求头"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "AI-Proxy-Service/1.0"
        }
        
        api_key = config_manager.get_api_key(backend_name)
        if api_key:
            if backend_name == "openai":
                headers["Authorization"] = f"Bearer {api_key}"
            elif backend_name == "claude":
                headers["x-api-key"] = api_key
                headers["anthropic-version"] = "2023-06-01"
            elif backend_name == "gemini":
                headers["Authorization"] = f"Bearer {api_key}"
        
        return headers
    
    async def select_backend(self, model: str) -> Optional[str]:
        """根据模型选择合适的后端"""
        enabled_backends = config_manager.get_enabled_backends()
        
        for name, backend in enabled_backends.items():
            if model in backend.models and self.health_status.get(name, False):
                return name
        
        # 如果没有精确匹配，尝试模糊匹配
        for name, backend in enabled_backends.items():
            if self.health_status.get(name, False):
                for backend_model in backend.models:
                    if model.lower() in backend_model.lower() or backend_model.lower() in model.lower():
                        return name
        
        logger.warning(f"未找到支持模型 '{model}' 的健康后端")
        return None
    
    async def forward_request(self, backend_name: str, endpoint: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """转发请求到指定后端"""
        if backend_name not in self.clients:
            raise ValueError(f"后端 '{backend_name}' 不存在")
        
        client = self.clients[backend_name]
        backend_config = config_manager.get_backend_config(backend_name)
        
        # 转换请求格式（如需要）
        converted_data = await self._convert_request(backend_name, request_data)
        
        max_retries = backend_config.max_retries if backend_config else 3
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"转发请求到 {backend_name}{endpoint} (尝试 {attempt + 1}/{max_retries + 1})")
                
                response = await client.post(endpoint, json=converted_data)
                response.raise_for_status()
                
                response_data = response.json()
                
                # 转换响应格式（如需要）
                converted_response = await self._convert_response(backend_name, response_data)
                
                # 标记后端为健康状态
                self.health_status[backend_name] = True
                
                return converted_response
                
            except httpx.HTTPStatusError as e:
                last_exception = e
                logger.warning(f"后端 {backend_name} 返回HTTP错误: {e.response.status_code}")
                
                if e.response.status_code >= 500:
                    # 服务器错误，标记为不健康并重试
                    self.health_status[backend_name] = False
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)  # 指数退避
                        continue
                else:
                    # 客户端错误，不重试
                    raise
            
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exception = e
                logger.warning(f"后端 {backend_name} 连接异常: {e}")
                self.health_status[backend_name] = False
                
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                    continue
        
        # 所有重试都失败了
        raise last_exception
    
    async def _convert_request(self, backend_name: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """转换请求格式以适应不同的后端API"""
        if backend_name == "claude":
            # 转换为Claude格式
            return await self._convert_to_claude_format(request_data)
        elif backend_name == "gemini":
            # 转换为Gemini格式
            return await self._convert_to_gemini_format(request_data)
        else:
            # OpenAI格式或其他兼容格式
            return request_data
    
    async def _convert_to_claude_format(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """转换为Claude API格式"""
        messages = request_data.get("messages", [])
        
        # Claude需要明确区分system和user/assistant消息
        system_messages = []
        conversation_messages = []
        
        for msg in messages:
            if msg.get("role") == "system":
                system_messages.append(msg["content"])
            else:
                conversation_messages.append(msg)
        
        claude_request = {
            "model": request_data.get("model", "claude-3-sonnet-20240229"),
            "max_tokens": request_data.get("max_tokens", 1000),
            "messages": conversation_messages
        }
        
        if system_messages:
            claude_request["system"] = "\n".join(system_messages)
        
        # 传递其他参数
        for key in ["temperature", "top_p", "stream"]:
            if key in request_data:
                claude_request[key] = request_data[key]
        
        return claude_request
    
    async def _convert_to_gemini_format(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """转换为Gemini API格式"""
        messages = request_data.get("messages", [])
        
        # Gemini使用contents数组
        contents = []
        for msg in messages:
            role = "user" if msg.get("role") in ["user", "system"] else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })
        
        gemini_request = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": request_data.get("max_tokens", 1000),
                "temperature": request_data.get("temperature", 1.0),
                "topP": request_data.get("top_p", 1.0)
            }
        }
        
        return gemini_request
    
    async def _convert_response(self, backend_name: str, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """转换响应格式为OpenAI兼容格式"""
        if backend_name == "claude":
            return await self._convert_from_claude_format(response_data)
        elif backend_name == "gemini":
            return await self._convert_from_gemini_format(response_data)
        else:
            return response_data
    
    async def _convert_from_claude_format(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """从Claude格式转换为OpenAI格式"""
        content = response_data.get("content", [])
        if content and isinstance(content, list):
            text_content = content[0].get("text", "")
        else:
            text_content = ""
        
        return {
            "id": response_data.get("id", ""),
            "object": "chat.completion",
            "created": int(datetime.now().timestamp()),
            "model": response_data.get("model", ""),
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text_content
                },
                "finish_reason": response_data.get("stop_reason", "stop")
            }],
            "usage": response_data.get("usage", {})
        }
    
    async def _convert_from_gemini_format(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """从Gemini格式转换为OpenAI格式"""
        candidates = response_data.get("candidates", [])
        content = ""
        
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                content = parts[0].get("text", "")
        
        return {
            "id": f"gemini-{int(datetime.now().timestamp())}",
            "object": "chat.completion",
            "created": int(datetime.now().timestamp()),
            "model": "gemini-pro",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
    
    async def check_health(self) -> Dict[str, Dict[str, Any]]:
        """检查所有后端的健康状态"""
        health_results = {}
        
        for name, client in self.clients.items():
            try:
                # 发送简单的健康检查请求
                start_time = datetime.now()
                
                # 不同后端可能有不同的健康检查端点
                if name == "openai":
                    response = await client.get("/models")
                else:
                    # 对于其他后端，尝试发送一个简单的请求
                    test_request = {
                        "model": "test",
                        "messages": [{"role": "user", "content": "Hello"}],
                        "max_tokens": 1
                    }
                    response = await client.post("/chat/completions", json=test_request)
                
                response_time = (datetime.now() - start_time).total_seconds()
                
                health_results[name] = {
                    "healthy": True,
                    "response_time": response_time,
                    "last_check": datetime.now().isoformat()
                }
                
                self.health_status[name] = True
                
            except Exception as e:
                logger.warning(f"后端 {name} 健康检查失败: {e}")
                health_results[name] = {
                    "healthy": False,
                    "error": str(e),
                    "last_check": datetime.now().isoformat()
                }
                self.health_status[name] = False
        
        self.last_health_check = {name: datetime.now() for name in self.clients.keys()}
        return health_results
    
    async def close(self):
        """关闭所有客户端连接"""
        for name, client in self.clients.items():
            try:
                await client.aclose()
                logger.info(f"关闭后端客户端: {name}")
            except Exception as e:
                logger.error(f"关闭后端客户端 {name} 时发生错误: {e}")
        
        self.clients.clear()
        self.health_status.clear()