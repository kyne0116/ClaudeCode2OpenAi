"""
指标收集器
收集和提供API使用统计和监控指标
"""
import time
from collections import defaultdict, Counter
from typing import Dict, List, Any
from datetime import datetime, timedelta
import threading
from dataclasses import dataclass, field


@dataclass
class RequestMetric:
    """单个请求的指标"""
    timestamp: float
    method: str
    path: str
    status_code: int
    response_time: float
    backend: str = ""
    model: str = ""


@dataclass
class BackendMetric:
    """后端服务指标"""
    name: str
    total_requests: int = 0
    success_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    last_request_time: float = 0.0
    models_used: Counter = field(default_factory=Counter)


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self):
        self.requests: List[RequestMetric] = []
        self.backend_metrics: Dict[str, BackendMetric] = defaultdict(lambda: BackendMetric(name=""))
        self.hourly_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.lock = threading.Lock()
        self.start_time = time.time()
    
    def record_request(self, method: str, path: str, status_code: int, response_time: float, backend: str = "", model: str = ""):
        """记录请求指标"""
        with self.lock:
            metric = RequestMetric(
                timestamp=time.time(),
                method=method,
                path=path,
                status_code=status_code,
                response_time=response_time,
                backend=backend,
                model=model
            )
            
            self.requests.append(metric)
            
            # 更新后端指标
            if backend:
                backend_metric = self.backend_metrics[backend]
                backend_metric.name = backend
                backend_metric.total_requests += 1
                backend_metric.last_request_time = metric.timestamp
                
                if 200 <= status_code < 400:
                    backend_metric.success_requests += 1
                else:
                    backend_metric.failed_requests += 1
                
                # 更新平均响应时间
                if backend_metric.total_requests == 1:
                    backend_metric.avg_response_time = response_time
                else:
                    backend_metric.avg_response_time = (
                        (backend_metric.avg_response_time * (backend_metric.total_requests - 1) + response_time)
                        / backend_metric.total_requests
                    )
                
                # 记录使用的模型
                if model:
                    backend_metric.models_used[model] += 1
            
            # 记录小时统计
            hour_key = datetime.fromtimestamp(metric.timestamp).strftime("%Y-%m-%d-%H")
            self.hourly_stats[hour_key]["total_requests"] += 1
            if 200 <= status_code < 400:
                self.hourly_stats[hour_key]["success_requests"] += 1
            else:
                self.hourly_stats[hour_key]["failed_requests"] += 1
            
            # 定期清理旧数据（保留24小时）
            if len(self.requests) > 10000:  # 限制内存使用
                cutoff_time = time.time() - 86400  # 24小时前
                self.requests = [r for r in self.requests if r.timestamp > cutoff_time]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            current_time = time.time()
            uptime = current_time - self.start_time
            
            # 基础统计
            total_requests = len(self.requests)
            if not self.requests:
                return {
                    "uptime_seconds": uptime,
                    "total_requests": 0,
                    "requests_per_second": 0,
                    "backend_stats": {},
                    "hourly_stats": dict(self.hourly_stats)
                }
            
            # 计算最近1小时的请求
            hour_ago = current_time - 3600
            recent_requests = [r for r in self.requests if r.timestamp > hour_ago]
            
            # 状态码统计
            status_codes = Counter(r.status_code for r in self.requests)
            
            # 响应时间统计
            response_times = [r.response_time for r in self.requests]
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            # 路径统计
            path_stats = Counter(r.path for r in self.requests)
            
            stats = {
                "uptime_seconds": uptime,
                "total_requests": total_requests,
                "requests_per_second": total_requests / uptime if uptime > 0 else 0,
                "requests_last_hour": len(recent_requests),
                "avg_response_time": avg_response_time,
                "status_codes": dict(status_codes),
                "path_stats": dict(path_stats.most_common(10)),
                "backend_stats": {
                    name: {
                        "total_requests": metric.total_requests,
                        "success_requests": metric.success_requests,
                        "failed_requests": metric.failed_requests,
                        "success_rate": metric.success_requests / metric.total_requests if metric.total_requests > 0 else 0,
                        "avg_response_time": metric.avg_response_time,
                        "models_used": dict(metric.models_used),
                        "last_request_time": datetime.fromtimestamp(metric.last_request_time).isoformat() if metric.last_request_time else None
                    }
                    for name, metric in self.backend_metrics.items()
                },
                "hourly_stats": dict(self.hourly_stats)
            }
            
            return stats
    
    def get_prometheus_metrics(self) -> str:
        """获取Prometheus格式的指标"""
        stats = self.get_stats()
        
        metrics = []
        
        # 基础指标
        metrics.append(f"# HELP ai_proxy_uptime_seconds Total uptime in seconds")
        metrics.append(f"# TYPE ai_proxy_uptime_seconds counter")
        metrics.append(f"ai_proxy_uptime_seconds {stats['uptime_seconds']}")
        
        metrics.append(f"# HELP ai_proxy_total_requests Total number of requests")
        metrics.append(f"# TYPE ai_proxy_total_requests counter")
        metrics.append(f"ai_proxy_total_requests {stats['total_requests']}")
        
        metrics.append(f"# HELP ai_proxy_requests_per_second Average requests per second")
        metrics.append(f"# TYPE ai_proxy_requests_per_second gauge")
        metrics.append(f"ai_proxy_requests_per_second {stats['requests_per_second']}")
        
        metrics.append(f"# HELP ai_proxy_avg_response_time Average response time in seconds")
        metrics.append(f"# TYPE ai_proxy_avg_response_time gauge")
        metrics.append(f"ai_proxy_avg_response_time {stats['avg_response_time']}")
        
        # 状态码指标
        metrics.append(f"# HELP ai_proxy_requests_by_status Total requests by status code")
        metrics.append(f"# TYPE ai_proxy_requests_by_status counter")
        for status_code, count in stats['status_codes'].items():
            metrics.append(f"ai_proxy_requests_by_status{{status_code=\"{status_code}\"}} {count}")
        
        # 后端指标
        for backend_name, backend_stats in stats['backend_stats'].items():
            metrics.append(f"# HELP ai_proxy_backend_requests Total requests by backend")
            metrics.append(f"# TYPE ai_proxy_backend_requests counter")
            metrics.append(f"ai_proxy_backend_requests{{backend=\"{backend_name}\"}} {backend_stats['total_requests']}")
            
            metrics.append(f"# HELP ai_proxy_backend_success_rate Success rate by backend")
            metrics.append(f"# TYPE ai_proxy_backend_success_rate gauge")
            metrics.append(f"ai_proxy_backend_success_rate{{backend=\"{backend_name}\"}} {backend_stats['success_rate']}")
            
            metrics.append(f"# HELP ai_proxy_backend_avg_response_time Average response time by backend")
            metrics.append(f"# TYPE ai_proxy_backend_avg_response_time gauge")
            metrics.append(f"ai_proxy_backend_avg_response_time{{backend=\"{backend_name}\"}} {backend_stats['avg_response_time']}")
        
        return "\n".join(metrics)
    
    def get_health_metrics(self) -> Dict[str, Any]:
        """获取健康状况指标"""
        with self.lock:
            current_time = time.time()
            five_minutes_ago = current_time - 300
            
            # 最近5分钟的请求
            recent_requests = [r for r in self.requests if r.timestamp > five_minutes_ago]
            
            if not recent_requests:
                return {
                    "healthy": True,
                    "recent_requests": 0,
                    "error_rate": 0.0,
                    "avg_response_time": 0.0
                }
            
            error_requests = [r for r in recent_requests if r.status_code >= 400]
            error_rate = len(error_requests) / len(recent_requests)
            avg_response_time = sum(r.response_time for r in recent_requests) / len(recent_requests)
            
            # 健康状况判断
            healthy = error_rate < 0.1 and avg_response_time < 30  # 错误率小于10%，平均响应时间小于30秒
            
            return {
                "healthy": healthy,
                "recent_requests": len(recent_requests),
                "error_rate": error_rate,
                "avg_response_time": avg_response_time,
                "backend_health": {
                    name: {
                        "requests": sum(1 for r in recent_requests if r.backend == name),
                        "errors": sum(1 for r in recent_requests if r.backend == name and r.status_code >= 400),
                        "avg_response_time": sum(r.response_time for r in recent_requests if r.backend == name) / 
                                           len([r for r in recent_requests if r.backend == name]) 
                                           if [r for r in recent_requests if r.backend == name] else 0
                    }
                    for name in self.backend_metrics.keys()
                }
            }