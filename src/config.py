"""
配置管理模块
支持从YAML文件和环境变量加载配置
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


class BackendConfig(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    name: str
    base_url: str
    enabled: bool = True
    timeout: int = 30
    max_retries: int = 3
    models: List[str] = []


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
    check_backends: bool = True


class AppConfig(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    server: ServerConfig = ServerConfig()
    backends: Dict[str, BackendConfig] = {}
    api_keys: Dict[str, str] = {}
    monitoring: MonitoringConfig = MonitoringConfig()
    rate_limit: RateLimitConfig = RateLimitConfig()
    health_check: HealthCheckConfig = HealthCheckConfig()


class ConfigManager:
    """配置管理器"""
    
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
        
        # API密钥环境变量覆盖
        for backend_name in self._config.backends.keys():
            env_key = f"{backend_name.upper()}_API_KEY"
            if os.getenv(env_key):
                self._config.api_keys[backend_name] = os.getenv(env_key)
    
    def get_backend_config(self, backend_name: str) -> Optional[BackendConfig]:
        """获取指定后端配置"""
        config = self.load_config()
        return config.backends.get(backend_name)
    
    def get_enabled_backends(self) -> Dict[str, BackendConfig]:
        """获取启用的后端配置"""
        config = self.load_config()
        return {name: backend for name, backend in config.backends.items() if backend.enabled}
    
    def get_api_key(self, backend_name: str) -> Optional[str]:
        """获取指定后端的API密钥"""
        config = self.load_config()
        return config.api_keys.get(backend_name)
    
    def validate_config(self) -> List[str]:
        """验证配置有效性，返回错误信息列表"""
        errors = []
        config = self.load_config()
        
        # 检查启用的后端是否有API密钥
        for name, backend in config.backends.items():
            if backend.enabled and not self.get_api_key(name):
                errors.append(f"后端 '{name}' 已启用但缺少API密钥")
        
        # 检查端口范围
        if not (1 <= config.server.port <= 65535):
            errors.append(f"端口号 {config.server.port} 无效")
        
        return errors


# 全局配置管理器实例
config_manager = ConfigManager()


def get_config() -> AppConfig:
    """获取应用配置"""
    return config_manager.load_config()