#!/bin/bash
# ============================================================
# FinanceDashboard 生产环境部署脚本
# 用法: ./deploy.sh
# ============================================================

set -euo pipefail

PROJECT_DIR="/root/data/FinanceDashboard"
FRONTEND_DIR="$PROJECT_DIR/frontend"
BACKEND_DIR="$PROJECT_DIR/backend"
NGINX_ROOT="/var/www/financedashboard"
BACKEND_PORT=8010
BACKEND_HOST=127.0.0.1

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[DEPLOY]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ─── 1. 检查环境 ──────────────────────────────────────────
log "检查环境..."

if ! command -v nginx &>/dev/null; then
    error "nginx 未安装"
fi

if [ ! -d "$FRONTEND_DIR" ]; then
    error "前端目录不存在: $FRONTEND_DIR"
fi

if [ ! -d "$BACKEND_DIR/venv" ]; then
    error "后端虚拟环境不存在，请先初始化"
fi

# ─── 2. 确保端口 80 没有被开发服务器占用 ──────────────────
log "检查端口占用..."

VITE_PIDS=$(ss -tlnp | grep ':80 ' | grep -E 'vite|node' | awk '{print $7}' | cut -d',' -f2 | cut -d'=' -f2 | sort -u | tr '\n' ' ')
if [ -n "$VITE_PIDS" ]; then
    warn "发现 vite/node 占用端口 80 (PID: $VITE_PIDS)，正在停止..."
    kill $VITE_PIDS 2>/dev/null || true
    sleep 1
fi

# ─── 3. 停止现有服务 ─────────────────────────────────────
log "停止现有服务..."

# 停止后端（通过端口查找）
BACKEND_PID=$(ss -tlnp | grep ":$BACKEND_PORT " | grep python | awk '{print $7}' | cut -d',' -f2 | cut -d'=' -f2 | head -1)
if [ -n "$BACKEND_PID" ]; then
    kill "$BACKEND_PID" 2>/dev/null || true
    sleep 1
fi

# 停止 nginx
systemctl stop nginx 2>/dev/null || true
sleep 1

# 确认端口释放
for port in 80 $BACKEND_PORT; do
    if ss -tln | grep -q ":$port "; then
        error "端口 $port 仍被占用，请手动检查"
    fi
done
log "端口已释放"

# ─── 4. 拉取最新代码（可选）───────────────────────────────
if [ -d "$PROJECT_DIR/.git" ]; then
    log "拉取最新代码..."
    cd "$PROJECT_DIR"
    git pull origin main 2>/dev/null || warn "git pull 失败，使用本地代码"
fi

# ─── 5. 构建前端 ─────────────────────────────────────────
log "构建前端..."
cd "$FRONTEND_DIR"

# 确保是生产构建，不是开发服务器
if [ -f package-lock.json ]; then
    npm ci 2>/dev/null || npm install
else
    npm install
fi

# 清理旧构建
rm -rf dist/

# 生产构建
npm run build

if [ ! -f "dist/index.html" ]; then
    error "前端构建失败，dist/index.html 不存在"
fi

log "前端构建完成"

# ─── 6. 部署到 nginx ─────────────────────────────────────
log "部署静态文件到 nginx..."

mkdir -p "$NGINX_ROOT"
rm -rf "$NGINX_ROOT"/*
cp -r "$FRONTEND_DIR"/dist/* "$NGINX_ROOT/"

# 设置权限
chown -R www-data:www-data "$NGINX_ROOT" 2>/dev/null || true
chmod -R 755 "$NGINX_ROOT"

# 验证
echo "  部署文件:"
ls -la "$NGINX_ROOT"/
echo ""
echo "  JS/CSS 文件:"
ls -la "$NGINX_ROOT"/assets/

# ─── 7. 启动后端 ─────────────────────────────────────────
log "启动后端..."
cd "$BACKEND_DIR"
source venv/bin/activate

# 检查 .env 文件
if [ ! -f ".env" ]; then
    warn "后端 .env 文件不存在"
fi

# 用 nohup 启动后端
nohup python3 -m uvicorn main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" > /tmp/backend.log 2>&1 &
BACKEND_NEW_PID=$!

sleep 2

if ! kill -0 $BACKEND_NEW_PID 2>/dev/null; then
    error "后端启动失败，检查 /tmp/backend.log"
fi

log "后端启动成功 (PID: $BACKEND_NEW_PID)"

# ─── 8. 启动 nginx ───────────────────────────────────────
log "启动 nginx..."
systemctl start nginx

sleep 1

if ! systemctl is-active nginx &>/dev/null; then
    error "nginx 启动失败"
fi

# ─── 9. 健康检查 ─────────────────────────────────────────
log "健康检查..."

# 检查端口
for port in 80 $BACKEND_PORT; do
    if ! ss -tln | grep -q ":$port "; then
        error "端口 $port 未监听"
    fi
    log "  端口 $port ✓"
done

# 检查前端
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/)
if [ "$HTTP_CODE" != "200" ]; then
    error "前端返回 HTTP $HTTP_CODE"
fi
log "  前端 HTTP 200 ✓"

# 检查 API
API_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/api/stocks || echo "000")
# API 可能需要认证，所以 401 也是正常的
if [ "$API_CODE" = "200" ] || [ "$API_CODE" = "401" ]; then
    log "  API 代理正常 ✓"
else
    warn "API 返回 HTTP $API_CODE"
fi

# ─── 10. 完成 ────────────────────────────────────────────
echo ""
echo "============================================================"
echo -e "${GREEN}部署成功！${NC}"
echo "============================================================"
echo ""
echo "  前端: http://<your-domain>/"
echo "  API:  http://<your-domain>/api/"
echo "  后端日志: tail -f /tmp/backend.log"
echo ""
echo "  构建时间: $(stat -c '%y' $NGINX_ROOT/assets/*.js | head -1)"
echo ""

exit 0
