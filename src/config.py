"""
配置管理模块
专门为Claude Code CLI转OpenAI API服务设计
"""
import os
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ServerConfig(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    reload: bool = False
    cors_origins: List[str] = ["*"]


class ClaudeModelConfig(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    id: str  # Claude模型ID，如 claude-3-5-sonnet-20241022
    name: str  # 映射到OpenAI格式的名称，如 gpt-4o
    family: str  # 模型系列，如 claude-3.5


class ClaudeConfig(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    name: str = "Claude (Anthropic)"
    base_url: str = "https://api.anthropic.com/v1"
    timeout: int = 60
    max_retries: int = 3
    models: List[ClaudeModelConfig] = []


class MonitoringConfig(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    enable_metrics: bool = True
    enable_logging: bool = True
    log_level: LogLevel = LogLevel.INFO
    log_requests: bool = True
    log_responses: bool = False
    metrics_endpoint: str = "/metrics"


class RateLimitConfig(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    enabled: bool = True
    requests_per_minute: int = 60
    burst_size: int = 10


class HealthCheckConfig(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    endpoint: str = "/health"
    check_claude: bool = True


class ContextConfig(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    enabled: bool = True
    max_context_messages: int = 20
    session_timeout_minutes: int = 30
    max_sessions: int = 1000
    cleanup_interval_minutes: int = 10


class AppConfig(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    server: ServerConfig = ServerConfig()
    claude: ClaudeConfig = ClaudeConfig()
    api_key: str = ""
    monitoring: MonitoringConfig = MonitoringConfig()
    rate_limit: RateLimitConfig = RateLimitConfig()
    health_check: HealthCheckConfig = HealthCheckConfig()
    context: ContextConfig = ContextConfig()


class ConfigManager:
    """配置管理器 - 专门为Claude转OpenAI API服务设计"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config.yaml"
        self._config: Optional[AppConfig] = None
    
    def load_config(self) -> AppConfig:
        """加载配置"""
        if self._config is None:
            self._config = self._load_from_file()
            self._apply_env_overrides()
        return self._config
    
    def _load_from_file(self) -> AppConfig:
        """从YAML文件加载配置"""
        config_file = Path(self.config_path)
        if not config_file.exists():
            print(f"配置文件 {self.config_path} 不存在，使用默认配置")
            return AppConfig()
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
            
            # 处理环境变量占位符
            config_data = self._resolve_env_placeholders(config_data)
            
            return AppConfig(**config_data)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return AppConfig()
    
    def _resolve_env_placeholders(self, data: Any) -> Any:
        """解析环境变量占位符 ${VAR_NAME:default_value}"""
        if isinstance(data, dict):
            return {key: self._resolve_env_placeholders(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._resolve_env_placeholders(item) for item in data]
        elif isinstance(data, str) and data.startswith("${") and data.endswith("}"):
            # 解析 ${VAR_NAME:default_value} 格式
            var_spec = data[2:-1]  # 移除 ${ 和 }
            if ":" in var_spec:
                var_name, default_value = var_spec.split(":", 1)
                return os.getenv(var_name, default_value)
            else:
                return os.getenv(var_spec, "")
        else:
            return data
    
    def _apply_env_overrides(self):
        """应用环境变量覆盖"""
        # 服务器配置环境变量覆盖
        if os.getenv("HOST"):
            self._config.server.host = os.getenv("HOST")
        if os.getenv("PORT"):
            self._config.server.port = int(os.getenv("PORT"))
        if os.getenv("DEBUG"):
            self._config.server.debug = os.getenv("DEBUG").lower() == "true"
        
        # Claude API密钥环境变量覆盖
        if os.getenv("CLAUDE_API_KEY"):
            self._config.api_key = os.getenv("CLAUDE_API_KEY")
    
    def get_claude_config(self) -> ClaudeConfig:
        """获取Claude配置"""
        config = self.load_config()
        return config.claude
    
    def get_api_key(self) -> str:
        """获取Claude API密钥"""
        config = self.load_config()
        return config.api_key
    
    def get_openai_model_mapping(self) -> Dict[str, str]:
        """获取OpenAI模型到Claude模型的映射"""
        config = self.load_config()
        mapping = {}
        for model in config.claude.models:
            mapping[model.name] = model.id
        return mapping
    
    def get_claude_to_openai_mapping(self) -> Dict[str, str]:
        """获取Claude模型到OpenAI模型的映射"""
        config = self.load_config()
        mapping = {}
        for model in config.claude.models:
            mapping[model.id] = model.name
        return mapping
    
    def get_supported_models(self) -> List[str]:
        """获取支持的OpenAI格式模型列表"""
        config = self.load_config()
        return [model.name for model in config.claude.models]
    
    def validate_config(self) -> List[str]:
        """验证配置有效性，返回错误信息列表"""
        errors = []
        config = self.load_config()
        
        # 不再需要API密钥验证，因为使用本地Claude Code CLI
        
        # 检查端口范围
        if not (1 <= config.server.port <= 65535):
            errors.append(f"端口号 {config.server.port} 无效")
        
        # 检查模型配置
        if not config.claude.models:
            errors.append("未配置任何Claude模型")
        
        return errors


# 全局配置管理器实例
config_manager = ConfigManager()


def get_config() -> AppConfig:
    """获取应用配置"""
    return config_manager.load_config()