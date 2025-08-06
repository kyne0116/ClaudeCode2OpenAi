# AI代理服务

基于FastAPI的多后端AI服务统一代理，支持OpenAI、Claude、Gemini等多个AI后端的无缝集成。

## 特性

- 🔄 **多后端支持**: 支持OpenAI、Claude、Gemini等主流AI服务
- 🔀 **智能路由**: 根据模型自动选择合适的后端服务  
- 📊 **监控统计**: 内置请求监控、指标收集和健康检查
- ⚙️ **灵活配置**: 支持YAML配置文件和环境变量
- 🚀 **高性能**: 异步处理、连接池复用
- 🔧 **开发友好**: 支持热重载、详细日志

## 快速开始

### 安装依赖

```bash
# 使用uv (推荐)
uv sync
uv run .

# 或使用pip
pip install -r requirements.txt
python main.py
```

### 环境变量

```bash
export OPENAI_API_KEY="your-openai-api-key"
export CLAUDE_API_KEY="your-claude-api-key"
export GEMINI_API_KEY="your-gemini-api-key"  # 可选
```

### 启动服务

```bash
# 方式1: 使用uv
uv run .

# 方式2: 直接运行
python main.py

# 方式3: 模块方式
python __main__.py
```

服务启动后访问：
- API文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

## 配置

编辑 `config.yaml` 文件自定义配置：

```yaml
server:
  host: "0.0.0.0"
  port: 8000

backends:
  openai:
    enabled: true
    models: ["gpt-4", "gpt-3.5-turbo"]
  claude:
    enabled: true  
    models: ["claude-3-opus-20240229", "claude-3-sonnet-20240229"]

monitoring:
  enable_logging: true
  log_level: "INFO"
```

## API使用

### 聊天完成

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7
  }'
```

### Python客户端

```python
import openai

client = openai.OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy-key"  # 使用环境变量中的真实密钥
)

response = client.chat.completions.create(
    model="claude-3-sonnet-20240229",  # 自动路由到Claude
    messages=[{"role": "user", "content": "解释量子计算"}]
)

print(response.choices[0].message.content)
```

## 项目结构

```
├── main.py                 # 主程序入口
├── __main__.py             # 模块入口
├── config.yaml             # 配置文件
├── requirements.txt        # Python依赖
├── pyproject.toml         # 项目配置
└── src/
    ├── config.py          # 配置管理
    └── services/          # 核心服务
        ├── backend_manager.py    # 后端管理
        ├── request_logger.py     # 请求日志
        ├── rate_limiter.py       # 速率限制
        └── metrics.py            # 指标收集
```

## 故障排除

### 常见问题

1. **端口占用**: 设置环境变量 `PORT=9000`
2. **uv命令不存在**: 使用 `python main.py` 替代
3. **依赖安装失败**: 手动安装核心依赖 `pip install fastapi uvicorn httpx pydantic pyyaml`

### 健康检查

```bash
curl http://localhost:8000/health
```

## 许可证

MIT License