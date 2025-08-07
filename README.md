# Claude Code CLI to OpenAI API 转换服务

**真正的本地Claude推理能力**：将本地Claude Code CLI包装为OpenAI兼容API，提供**真实的Claude思考和推理**，而非模拟响应。

## 🌟 核心特性

- 🧠 **真正的Claude推理**: 直接调用本地Claude Code CLI，获得真实的Claude思考过程和推理能力
- 🔄 **OpenAI完全兼容**: 标准OpenAI API格式，无需修改现有代码
- ⚡ **动态响应**: 每个请求都经过真实推理，无预设模板
- 🎯 **通用处理**: 支持任何类型问题 - 国家介绍、编程、创作、分析等
- 📝 **完整思考链**: 包含Claude的thinking过程，展现推理过程
- 🚀 **高性能**: 异步处理，智能错误处理和回退机制

## ⚙️ 工作原理

```
HTTP请求 → FastAPI包装器 → subprocess调用 → 本地Claude Code CLI → 真实推理 → OpenAI格式返回
```

**关键点**: API服务**仅仅是包装器**，真正的处理由本地Claude Code CLI（你当前的Claude实例）完成。

## 🚀 快速开始

### 1. 启动服务

```bash
# 直接运行（推荐）
python3 main.py

# 或使用uv
uv run main.py
```

服务将在 `http://localhost:8000` 启动

### 2. 测试服务

```bash
# 健康检查
curl http://localhost:8000/health

# 测试德国介绍（真实Claude推理）
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "介绍一下德国"}]
  }'

# 测试编程问题
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "如何用Python实现快速排序？"}]
  }'
```

## 💻 客户端集成

### Python OpenAI客户端

```python
import openai

# 连接到本地Claude服务
client = openai.OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy"  # 不需要真实key，使用本地Claude
)

# 获得真正的Claude推理
response = client.chat.completions.create(
    messages=[
        {"role": "user", "content": "分析人工智能的未来发展趋势"}
    ]
)

print(response.choices[0].message.content)
```

### 支持的模型

| 模型名 | 说明 |
|--------|------|
| `claude` | 本地Claude Code CLI |
| 任何OpenAI格式模型名 | 自动映射到本地Claude |

## 📁 项目结构

```
├── main.py                      # FastAPI应用主入口
├── config.yaml                  # 服务配置
├── CLAUDE.md                   # Claude专用文档
├── src/
│   ├── config.py               # 配置管理
│   └── services/
│       ├── claude_processor.py # 核心：Claude推理处理器
│       ├── rate_limiter.py     # 请求限流
│       └── metrics.py          # 监控指标
└── requirements.txt            # Python依赖
```

## 🔧 配置

编辑 `config.yaml` 自定义设置：

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  debug: false

monitoring:
  log_level: "INFO"
  log_requests: true

rate_limit:
  enabled: true
  requests_per_minute: 60
```

## 📋 API端点

### OpenAI兼容接口
- `POST /v1/chat/completions` - 聊天完成（主要接口）
- `POST /v1/completions` - 文本完成  
- `GET /v1/models` - 模型列表

### 监控接口
- `GET /health` - 健康检查
- `GET /stats` - 使用统计
- `GET /metrics` - Prometheus指标

## 🌍 真实应用示例

### 国家介绍
```bash
# 德国 - 获得详细的历史、文化、经济分析
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "介绍一下德国"}]}'
```

### 编程协助  
```bash
# Python快速排序 - 获得完整代码实现
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "用Python实现快速排序"}]}'
```

### 深度分析
```bash  
# AI趋势分析 - 获得全面的多维度分析
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "人工智能的未来发展趋势"}]}'
```

## 🔍 核心优势

### ✅ 真正的Claude推理
- 每个回答都包含完整的`thinking`思考过程
- 动态生成内容，而非预设模板
- 展现真实的Claude分析和推理能力

### ✅ 完全的通用性
- 支持任何类型的问题和任务
- 无需预设关键词或分类逻辑
- 真正的"问什么答什么"

### ✅ OpenAI无缝兼容
- 标准API格式，现有代码无需修改
- 支持所有OpenAI客户端库
- 完整的错误处理和状态码

## 🛠️ 故障排除

### Claude Code CLI连接问题
如果遇到Claude调用失败，服务会自动降级到备用响应模式，并提供详细的错误信息指导。

### 端口占用
```bash
# 更换端口
PORT=9000 python3 main.py
```

### 依赖问题
```bash
# 手动安装核心依赖
pip install fastapi uvicorn asyncio
```

## 📄 许可证

MIT License - 自由使用和修改

---

**说明**: 这个项目的核心价值在于将强大的本地Claude Code CLI能力封装为标准API，让你能在任何支持OpenAI API的应用中使用真正的Claude推理能力。