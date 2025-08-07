# Claude Code CLI to OpenAI API 转换服务

**智能多轮对话API**：将本地Claude Code CLI包装为OpenAI兼容API，提供**真实的Claude推理能力**和**完整的对话记忆功能**。

## 🌟 核心特性

- 🧠 **真正的Claude推理**: 直接调用本地Claude Code CLI，获得真实思考和推理能力
- 💭 **智能对话记忆**: 支持多轮对话上下文，自动管理会话记忆
- 🔄 **OpenAI完全兼容**: 标准OpenAI API格式，无需修改现有代码
- ⚡ **智能上下文压缩**: 解决长对话性能问题，防止记忆幻觉
- 🎯 **会话自动管理**: 基于客户端标识的智能会话创建和维护
- 🚀 **高性能稳定**: 异步处理，智能限流，完整监控

## 🚀 快速开始

### 1. 启动服务

```bash
# 推荐使用uv
uv run main.py

# 或直接运行
python3 main.py
```

服务启动在 `http://localhost:8000`

### 2. 测试多轮对话

```bash
# 第一轮：建立信息
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "User-Agent: my-app/1.0" \
  -d '{
    "model": "claude",
    "messages": [{"role": "user", "content": "你好，我叫张三，是程序员"}]
  }'

# 第二轮：测试记忆
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "User-Agent: my-app/1.0" \
  -d '{
    "model": "claude", 
    "messages": [{"role": "user", "content": "请问我的名字和职业是什么？"}]
  }'
```

## 💻 客户端集成

### Python OpenAI客户端

```python
import openai

# 连接本地Claude服务
client = openai.OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy"  # 本地服务无需真实key
)

# 多轮对话示例
def chat_with_memory():
    # 第一轮
    response1 = client.chat.completions.create(
        model="claude",
        messages=[{"role": "user", "content": "我叫李四，今年25岁"}]
    )
    print("第一轮:", response1.choices[0].message.content)
    
    # 第二轮 - 自动记住之前的信息
    response2 = client.chat.completions.create(
        model="claude", 
        messages=[{"role": "user", "content": "我多大了？"}]
    )
    print("第二轮:", response2.choices[0].message.content)  # 会回答"25岁"

chat_with_memory()
```

### JavaScript/Node.js

```javascript
import OpenAI from 'openai';

const openai = new OpenAI({
  baseURL: 'http://localhost:8000/v1',
  apiKey: 'dummy'
});

// 多轮对话
async function chatExample() {
  // 第一轮
  const response1 = await openai.chat.completions.create({
    model: 'claude',
    messages: [{ role: 'user', content: '我住在北京，有一只猫' }]
  });
  
  // 第二轮 - 自动继承记忆
  const response2 = await openai.chat.completions.create({
    model: 'claude',
    messages: [{ role: 'user', content: '我住在哪里？' }]
  });
  
  console.log(response2.choices[0].message.content); // "你住在北京"
}
```

## 🧠 智能记忆系统

### 自动会话管理
- **会话标识**: 基于客户端IP + User-Agent自动创建会话
- **记忆持续**: 30分钟内的对话自动关联
- **智能压缩**: 长对话自动压缩，保留关键信息

### 记忆策略
| 对话轮次 | 策略 | 效果 |
|---------|------|------|
| ≤ 2轮 | 完整上下文 | 保持详细记忆 |
| > 2轮 | 智能压缩 | 最近3轮+关键摘要 |

### 配置记忆参数

```yaml
# config.yaml
context:
  enabled: true                # 启用上下文管理
  max_context_messages: 20     # 每会话最大消息数
  session_timeout_minutes: 30  # 会话超时时间
  max_sessions: 1000          # 最大并发会话数
```

## 📋 API端点

### 主要接口
- `POST /v1/chat/completions` - 多轮对话（支持记忆）
- `POST /v1/completions` - 单次完成
- `GET /v1/models` - 模型列表

### 监控接口  
- `GET /health` - 健康检查
- `GET /stats` - 使用统计和会话信息

## 🎯 应用场景

### 智能助手
```python
# 连续对话，记住用户偏好
client.chat.completions.create(
    model="claude",
    messages=[{"role": "user", "content": "我喜欢Python编程"}]
)
# 后续对话会记住这个偏好
```

### 技术问答
```python
# 多步骤问题解决
messages = [
    {"role": "user", "content": "我有个React项目需要添加路由"},
    {"role": "user", "content": "用什么库比较好？"},
    {"role": "user", "content": "具体怎么配置？"}
]
# 每个问题都基于前面的上下文回答
```

### 长对话分析
```python
# 复杂需求分析，记住所有细节
# 第1轮：需求描述
# 第2轮：补充细节  
# 第3轮：技术方案
# ...自动记忆所有信息
```

## 🔧 故障排除

### 记忆不工作？
1. **检查User-Agent**: 确保客户端发送一致的User-Agent
2. **会话超时**: 超过30分钟需要重新开始
3. **服务重启**: 重启会清空内存中的会话

### 长对话变慢？
- ✅ **已解决**: 智能压缩机制自动优化长对话性能

### 端口占用
```bash
# 更换端口启动
PORT=9000 python3 main.py
```

## 📊 监控信息

```bash
# 查看会话统计
curl http://localhost:8000/stats

# 健康检查（包含上下文状态）
curl http://localhost:8000/health
```

---

**核心价值**: 将强大的Claude Code CLI包装为支持**智能多轮对话记忆**的标准OpenAI API，让任何应用都能轻松集成真正的Claude推理能力和连续对话功能。