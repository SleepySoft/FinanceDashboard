#!/bin/bash
# FinanceDashboard 前端启动脚本
# 默认使用开发模式 (vite dev)，支持热重载

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
MODE="${1:-dev}"
PORT="${2:-80}"

cd "$FRONTEND_DIR"

case "$MODE" in
  dev)
    echo "🚀 启动前端开发服务器 (vite dev)"
    echo "   地址: http://0.0.0.0:$PORT"
    echo "   特性: 热重载 / 源码映射 / 自动刷新"
    echo ""
    echo "   提示: 修改代码后自动刷新，无需手动 build"
    echo "   生产模式请用: $0 preview"
    echo ""
    exec npx vite --host 0.0.0.0 --port "$PORT"
    ;;
  preview)
    echo "🏭 启动前端生产预览 (vite preview)"
    echo "   地址: http://0.0.0.0:$PORT"
    echo "   特性: 高性能 / 静态文件 / 无热重载"
    echo ""
    echo "   提示: 改代码后需要重新 build: npm run build"
    echo ""
    # 检查 dist 是否存在
    if [ ! -d "dist" ]; then
      echo "⚠️  dist 目录不存在，先执行构建..."
      npm run build
    fi
    exec npx vite preview --host 0.0.0.0 --port "$PORT"
    ;;
  build)
    echo "🔨 构建生产版本..."
    exec npm run build
    ;;
  *)
    echo "用法: $0 [dev|preview|build] [端口]"
    echo ""
    echo "  dev     - 开发模式 (默认)，热重载，改代码立即生效"
    echo "  preview - 生产预览，性能更好，需先 build"
    echo "  build   - 仅构建，不启动服务器"
    echo ""
    echo "示例:"
    echo "  $0           # 开发模式，端口80"
    echo "  $0 dev 8080  # 开发模式，端口8080"
    echo "  $0 preview   # 生产预览，端口80"
    exit 1
    ;;
esac
