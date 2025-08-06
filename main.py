"""
AI代理服务主程序
支持多后端AI服务的统一接口代理
"""
import asyncio
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
import logging
from datetime import datetime, timedelta
import json

from src.config import get_config, config_manager
from src.services.backend_manager import BackendManager
from src.services.request_logger import RequestLogger
from src.services.rate_limiter import RateLimiter
from src.services.metrics import MetricsCollector


# 配置日志
def setup_logging():
    config = get_config()
    logging.basicConfig(
        level=getattr(logging, config.monitoring.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('app.log', encoding='utf-8')
        ]
    )

setup_logging()
logger = logging.getLogger(__name__)

# 全局组件
backend_manager: Optional[BackendManager] = None
request_logger: Optional[RequestLogger] = None
rate_limiter: Optional[RateLimiter] = None
metrics_collector: Optional[MetricsCollector] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global backend_manager, request_logger, rate_limiter, metrics_collector
    
    logger.info("正在启动AI代理服务...")
    
    # 验证配置
    errors = config_manager.validate_config()
    if errors:
        logger.error("配置验证失败:")
        for error in errors:
            logger.error(f"  - {error}")
        raise RuntimeError("配置验证失败，服务无法启动")
    
    # 初始化组件
    config = get_config()
    backend_manager = BackendManager()
    request_logger = RequestLogger()
    rate_limiter = RateLimiter(config.rate_limit)
    metrics_collector = MetricsCollector()
    
    logger.info(f"已启用后端: {list(config_manager.get_enabled_backends().keys())}")
    logger.info(f"服务将在 {config.server.host}:{config.server.port} 启动")
    
    yield
    
    logger.info("正在关闭AI代理服务...")
    await backend_manager.close()


# 创建FastAPI应用
app = FastAPI(
    title="AI代理服务",
    description="支持多后端AI服务的统一接口代理",
    version="1.0.0",
    lifespan=lifespan
)

# 添加中间件
config = get_config()

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # 记录请求
    if config.monitoring.log_requests:
        logger.info(f"请求: {request.method} {request.url}")
    
    response = await call_next(request)
    
    # 记录响应时间
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    # 收集指标
    if metrics_collector:
        metrics_collector.record_request(
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            response_time=process_time
        )
    
    if config.monitoring.log_requests:
        logger.info(f"响应: {response.status_code} ({process_time:.3f}s)")
    
    return response


# 限流依赖
async def check_rate_limit(request: Request):
    if rate_limiter and rate_limiter.is_enabled():
        client_ip = request.client.host
        if not rate_limiter.check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429,
                detail="请求过于频繁，请稍后再试"
            )


@app.get("/health")
async def health_check():
    """健康检查端点"""
    config = get_config()
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }
    
    if config.health_check.check_backends and backend_manager:
        backend_health = await backend_manager.check_health()
        health_status["backends"] = backend_health
        
        # 如果有后端不健康，整体状态为降级
        if any(not status["healthy"] for status in backend_health.values()):
            health_status["status"] = "degraded"
    
    return health_status


@app.get("/backends")
async def list_backends():
    """列出可用的后端服务"""
    enabled_backends = config_manager.get_enabled_backends()
    backends_info = {}
    
    for name, backend in enabled_backends.items():
        backends_info[name] = {
            "name": backend.name,
            "models": backend.models,
            "enabled": backend.enabled
        }
    
    return {"backends": backends_info}


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    _: None = Depends(check_rate_limit)
):
    """ChatGPT兼容的聊天完成接口"""
    try:
        request_data = await request.json()
        
        # 提取模型信息
        model = request_data.get("model", "")
        if not model:
            raise HTTPException(status_code=400, detail="模型参数不能为空")
        
        # 确定使用哪个后端
        backend_name = await backend_manager.select_backend(model)
        if not backend_name:
            raise HTTPException(
                status_code=400, 
                detail=f"未找到支持模型 '{model}' 的后端服务"
            )
        
        # 记录请求
        if request_logger:
            await request_logger.log_request(request_data, backend_name)
        
        # 转发请求到后端
        response_data = await backend_manager.forward_request(
            backend_name, 
            "/chat/completions", 
            request_data
        )
        
        # 记录响应
        if request_logger and config.monitoring.log_responses:
            await request_logger.log_response(response_data)
        
        return response_data
        
    except httpx.HTTPStatusError as e:
        logger.error(f"后端请求失败: {e}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"后端服务错误: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"请求处理失败: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@app.post("/v1/completions")
async def completions(
    request: Request,
    _: None = Depends(check_rate_limit)
):
    """文本完成接口"""
    try:
        request_data = await request.json()
        
        # 提取模型信息
        model = request_data.get("model", "")
        if not model:
            raise HTTPException(status_code=400, detail="模型参数不能为空")
        
        # 确定使用哪个后端
        backend_name = await backend_manager.select_backend(model)
        if not backend_name:
            raise HTTPException(
                status_code=400, 
                detail=f"未找到支持模型 '{model}' 的后端服务"
            )
        
        # 转发请求到后端
        response_data = await backend_manager.forward_request(
            backend_name, 
            "/completions", 
            request_data
        )
        
        return response_data
        
    except Exception as e:
        logger.error(f"请求处理失败: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@app.get("/v1/models")
async def list_models():
    """列出可用模型"""
    enabled_backends = config_manager.get_enabled_backends()
    models = []
    
    for backend_name, backend in enabled_backends.items():
        for model in backend.models:
            models.append({
                "id": model,
                "object": "model",
                "created": int(time.time()),
                "owned_by": backend_name
            })
    
    return {"object": "list", "data": models}


@app.get("/stats")
async def get_stats():
    """获取使用统计"""
    if not metrics_collector:
        return {"message": "指标收集未启用"}
    
    stats = metrics_collector.get_stats()
    return stats


@app.get("/metrics")
async def get_metrics():
    """获取Prometheus格式指标"""
    if not metrics_collector:
        return Response("指标收集未启用", media_type="text/plain")
    
    metrics = metrics_collector.get_prometheus_metrics()
    return Response(metrics, media_type="text/plain")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP异常处理"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
                "type": "api_error",
                "code": exc.status_code
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理"""
    logger.error(f"未处理的异常: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "内部服务器错误",
                "type": "internal_error",
                "code": 500
            }
        }
    )


def main():
    """主启动函数"""
    config = get_config()
    uvicorn.run(
        "main:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.server.reload,
        log_level=config.monitoring.log_level.lower()
    )


if __name__ == "__main__":
    main()