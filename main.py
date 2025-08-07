"""
真正的Claude Code CLI to OpenAI API转换服务
使用本地Claude Code CLI的真实推理能力
"""
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from datetime import datetime
import json

from src.config import get_config
from src.services.claude_processor import RealClaudeProcessor
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
            logging.FileHandler('claude_api.log', encoding='utf-8')
        ]
    )

setup_logging()
logger = logging.getLogger(__name__)

# 全局组件
claude_processor: Optional[RealClaudeProcessor] = None
rate_limiter: Optional[RateLimiter] = None
metrics_collector: Optional[MetricsCollector] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global claude_processor, rate_limiter, metrics_collector
    
    logger.info("🚀 启动真正的Claude Code CLI转OpenAI API服务...")
    
    # 初始化组件
    config = get_config()
    claude_processor = RealClaudeProcessor()
    rate_limiter = RateLimiter(config.rate_limit)
    metrics_collector = MetricsCollector()
    
    logger.info("✅ 真正的Claude处理器已就绪")
    logger.info(f"🌐 服务将在 {config.server.host}:{config.server.port} 启动")
    logger.info("💡 现在使用真正的Claude推理能力处理请求")
    
    yield
    
    logger.info("🔄 正在关闭Claude API服务...")


# 创建FastAPI应用
app = FastAPI(
    title="Claude Code CLI to OpenAI API",
    description="使用真正的Claude Code CLI推理能力的OpenAI兼容API服务",
    version="2.0.0",
    lifespan=lifespan
)

# 添加CORS中间件
config = get_config()
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
    
    if config.monitoring.log_requests:
        logger.info(f"📥 请求: {request.method} {request.url}")
    
    response = await call_next(request)
    
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
        logger.info(f"📤 响应: {response.status_code} ({process_time:.3f}s)")
    
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


@app.get("/")
async def root():
    """根路径信息"""
    return {
        "service": "Claude Code CLI to OpenAI API",
        "version": "2.0.0",
        "description": "使用真正Claude推理能力的OpenAI兼容API服务",
        "endpoints": {
            "chat": "/v1/chat/completions",
            "completions": "/v1/completions", 
            "models": "/v1/models",
            "health": "/health"
        },
        "powered_by": "真正的Claude Code CLI"
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "service": "real-claude-processor"
    }
    
    if claude_processor:
        claude_health = await claude_processor.check_health()
        health_status["claude"] = claude_health
        
        if not claude_health.get("healthy", False):
            health_status["status"] = "degraded"
    
    return health_status


@app.get("/v1/models")
async def list_models():
    """列出可用模型（OpenAI格式）"""
    if not claude_processor:
        raise HTTPException(status_code=503, detail="Claude处理器未初始化")
    
    return claude_processor.list_models()


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    _: None = Depends(check_rate_limit)
):
    """聊天完成接口 - 使用真正的Claude推理"""
    if not claude_processor:
        raise HTTPException(status_code=503, detail="Claude处理器未初始化")
    
    try:
        request_data = await request.json()
        
        # 提取请求参数
        messages = request_data.get("messages", [])
        
        if not messages:
            raise HTTPException(status_code=400, detail="消息不能为空")
        
        logger.info(f"🧠 开始Claude推理处理")
        
        # 使用真正的Claude处理器进行推理（不需要model参数）
        response_data = await claude_processor.process_chat_completion(messages=messages)
        
        logger.info(f"✅ Claude推理完成，生成{response_data['usage']['completion_tokens']}个token")
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 聊天完成处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"内部处理错误: {str(e)}")


@app.post("/v1/completions")
async def completions(
    request: Request,
    _: None = Depends(check_rate_limit)
):
    """文本完成接口 - 转换为聊天格式后用Claude处理"""
    if not claude_processor:
        raise HTTPException(status_code=503, detail="Claude处理器未初始化")
    
    try:
        request_data = await request.json()
        
        # 提取参数
        prompt = request_data.get("prompt", "")
        
        if not prompt:
            raise HTTPException(status_code=400, detail="提示不能为空")
        
        # 转换为聊天格式
        messages = [{"role": "user", "content": prompt}]
        
        logger.info(f"🔄 文本完成请求转换为聊天格式")
        
        # 使用聊天完成处理
        chat_response = await claude_processor.process_chat_completion(messages=messages)
        
        # 转换回文本完成格式
        completion_response = {
            "id": chat_response["id"].replace("chatcmpl", "cmpl"),
            "object": "text_completion", 
            "created": chat_response["created"],
            "model": "claude-via-openai-api",
            "choices": [{
                "text": chat_response["choices"][0]["message"]["content"],
                "index": 0,
                "finish_reason": chat_response["choices"][0]["finish_reason"]
            }],
            "usage": chat_response["usage"]
        }
        
        return completion_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 文本完成处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"内部处理错误: {str(e)}")


@app.get("/stats")
async def get_stats():
    """获取使用统计"""
    if not metrics_collector:
        return {"message": "指标收集未启用"}
    
    stats = metrics_collector.get_stats()
    stats["processor"] = "real-claude-processor"
    stats["capabilities"] = "full_reasoning"
    return stats


@app.get("/metrics") 
async def get_metrics():
    """获取Prometheus格式指标"""
    if not metrics_collector:
        return JSONResponse(
            content="指标收集未启用",
            media_type="text/plain"
        )
    
    metrics = metrics_collector.get_prometheus_metrics()
    return JSONResponse(content=metrics, media_type="text/plain")


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
    logger.error(f"❌ 未处理的异常: {exc}")
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
    logger.info("🎯 使用真正的Claude Code CLI推理能力启动服务")
    
    uvicorn.run(
        "main:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.server.reload,
        log_level=config.monitoring.log_level.lower()
    )


if __name__ == "__main__":
    main()