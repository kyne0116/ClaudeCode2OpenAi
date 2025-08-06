#!/bin/bash

# AI代理服务启动脚本
# 自动检查并安装uv，创建虚拟环境，安装依赖，启动服务

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

log_info "AI代理服务启动脚本"
log_info "工作目录: $SCRIPT_DIR"

# 检查Python版本
check_python() {
    log_step "检查Python版本..."
    
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3未安装，请先安装Python 3.8或更高版本"
        exit 1
    fi
    
    python_version=$(python3 --version 2>&1 | awk '{print $2}')
    log_info "Python版本: $python_version"
    
    # 检查是否为3.8+
    if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
        log_error "需要Python 3.8或更高版本，当前版本: $python_version"
        exit 1
    fi
}

# 检查并安装uv
install_uv() {
    log_step "检查并安装uv包管理器..."
    
    if command -v uv &> /dev/null; then
        log_info "uv已安装: $(uv --version)"
        return 0
    fi
    
    log_info "uv未安装，正在安装..."
    
    # 根据操作系统选择安装方法
    if [[ "$OSTYPE" == "linux-gnu"* ]] || [[ "$OSTYPE" == "darwin"* ]]; then
        # Linux或macOS
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.cargo/bin:$PATH"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]]; then
        # Windows (Git Bash/MSYS2/Cygwin)
        log_error "请在Windows上使用PowerShell运行以下命令安装uv:"
        log_error "powershell -ExecutionPolicy ByPass -c \"irm https://astral.sh/uv/install.ps1 | iex\""
        exit 1
    else
        log_error "不支持的操作系统: $OSTYPE"
        log_error "请手动安装uv: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
    
    # 验证安装
    if command -v uv &> /dev/null; then
        log_info "uv安装成功: $(uv --version)"
    else
        log_error "uv安装失败，请手动安装"
        exit 1
    fi
}

# 创建虚拟环境
setup_venv() {
    log_step "设置虚拟环境..."
    
    if [ ! -d ".venv" ]; then
        log_info "创建虚拟环境..."
        uv venv
    else
        log_info "虚拟环境已存在"
    fi
    
    # 激活虚拟环境
    if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]]; then
        source .venv/Scripts/activate
    else
        source .venv/bin/activate
    fi
    
    log_info "虚拟环境已激活"
}

# 安装依赖
install_dependencies() {
    log_step "安装项目依赖..."
    
    if [ -f "pyproject.toml" ]; then
        log_info "使用uv安装依赖..."
        uv sync
    else
        log_error "未找到pyproject.toml文件"
        exit 1
    fi
    
    log_info "依赖安装完成"
}

# 检查配置文件
check_config() {
    log_step "检查配置文件..."
    
    if [ ! -f "config.yaml" ]; then
        log_error "配置文件config.yaml不存在"
        exit 1
    fi
    
    log_info "配置文件检查通过"
    
    # 检查API密钥环境变量
    missing_keys=()
    if [ -z "$OPENAI_API_KEY" ]; then
        missing_keys+=("OPENAI_API_KEY")
    fi
    if [ -z "$CLAUDE_API_KEY" ]; then
        missing_keys+=("CLAUDE_API_KEY")
    fi
    
    if [ ${#missing_keys[@]} -gt 0 ]; then
        log_warn "以下API密钥环境变量未设置:"
        for key in "${missing_keys[@]}"; do
            log_warn "  - $key"
        done
        log_warn "请设置相应的环境变量或在配置文件中配置API密钥"
    fi
}

# 启动服务
start_service() {
    log_step "启动AI代理服务..."
    
    # 检查端口是否被占用
    port=${PORT:-8000}
    if command -v lsof &> /dev/null; then
        if lsof -ti:$port &> /dev/null; then
            log_error "端口$port已被占用，请修改PORT环境变量或config.yaml中的端口配置"
            exit 1
        fi
    fi
    
    log_info "服务将在端口$port启动"
    log_info "健康检查端点: http://localhost:$port/health"
    log_info "API文档: http://localhost:$port/docs"
    log_info "按Ctrl+C停止服务"
    echo
    
    # 根据环境选择启动方式
    if [ "${1:-}" = "--dev" ] || [ "$NODE_ENV" = "development" ] || [ "$DEBUG" = "true" ]; then
        log_info "以开发模式启动（热重载）..."
        uv run uvicorn main:app --host 0.0.0.0 --port $port --reload --log-level info
    else
        log_info "以生产模式启动..."
        uv run uvicorn main:app --host 0.0.0.0 --port $port --workers 1 --log-level info
    fi
}

# 显示帮助信息
show_help() {
    echo "AI代理服务启动脚本"
    echo
    echo "用法: $0 [选项]"
    echo
    echo "选项:"
    echo "  --dev       以开发模式启动（启用热重载）"
    echo "  --help, -h  显示此帮助信息"
    echo
    echo "环境变量:"
    echo "  PORT              服务端口（默认：8000）"
    echo "  OPENAI_API_KEY    OpenAI API密钥"
    echo "  CLAUDE_API_KEY    Claude API密钥"
    echo "  GEMINI_API_KEY    Gemini API密钥"
    echo "  DEBUG             启用调试模式（true/false）"
    echo
    echo "示例:"
    echo "  $0                # 启动服务"
    echo "  $0 --dev          # 开发模式启动"
    echo "  PORT=9000 $0      # 在端口9000启动"
}

# 清理函数
cleanup() {
    log_info "正在关闭服务..."
    exit 0
}

# 捕获Ctrl+C信号
trap cleanup SIGINT SIGTERM

# 主函数
main() {
    # 解析命令行参数
    case "${1:-}" in
        --help|-h)
            show_help
            exit 0
            ;;
        --dev)
            DEV_MODE=true
            ;;
        *)
            DEV_MODE=false
            ;;
    esac
    
    # 执行启动流程
    check_python
    install_uv
    setup_venv
    install_dependencies
    check_config
    
    if [ "$DEV_MODE" = true ]; then
        start_service --dev
    else
        start_service
    fi
}

# 如果脚本被直接执行（而非被source），则运行主函数
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi