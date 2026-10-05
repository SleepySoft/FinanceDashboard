# Linux 生产部署

本文记录 FinanceDashboard 当前的生产拓扑、systemd 安装方式、更新流程和常见故障检查。

## 当前拓扑

```text
Internet
  │  https://www.sleepysoft.dev/dashboard/
  ▼
公网入口主机（Nginx）
  │  Tailscale 反向代理
  ▼
应用主机 100.105.210.96:80（Nginx）
  ├─ /api/*  ─► 127.0.0.1:8010（financedashboard.service / Uvicorn）
  └─ /*      ─► /var/www/financedashboard（Vue 构建产物）
```

后端只监听回环地址，不直接暴露到公网。应用主机的 Nginx 是 API 和静态资源入口；公网入口主机再通过 Tailscale 转发到应用主机。

## 首次安装 systemd 服务

前提：代码位于 `/root/data/FinanceDashboard`，且 `backend/venv` 已安装依赖。

```bash
cd /root/data/FinanceDashboard
sudo ./scripts/install_systemd_service.sh
```

安装脚本会：

1. 根据仓库实际路径生成 `/etc/systemd/system/financedashboard.service`；
2. 默认设置 `FD_HOST=127.0.0.1`、`FD_PORT=8010`；
3. 停止本仓库遗留的手工 `uvicorn --reload` 进程；
4. 启用开机自启并重启服务；
5. 请求 `/api/auth/config` 完成健康检查。

脚本可以重复执行。若需要覆盖默认配置，可在项目根目录创建不会提交到 Git 的 `.env`：

```dotenv
FD_HOST=127.0.0.1
FD_PORT=8010
FD_COOKIE_SECURE=true
```

## Nginx 关键配置

应用主机的 API 上游必须与 systemd 服务端口一致：

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8010;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

修改后执行：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

不要把上游改回 `127.0.0.1:8000`。项目统一使用 8010；上游端口错误会使登录等所有 API 请求返回 502。

## 日常更新

```bash
cd /root/data/FinanceDashboard
git pull --ff-only
git submodule update --init --recursive

# 前端有改动时构建并同步到 Nginx 静态目录
cd frontend
npm install
npm run build
sudo rsync -a --delete dist/ /var/www/financedashboard/

# 后端或服务脚本有改动时重新安装/重启
cd ..
sudo ./scripts/install_systemd_service.sh
```

仅修改后端代码时，可以直接执行：

```bash
sudo systemctl restart financedashboard
```

## Arachne 独立服务

Arachne 位于 `services/arachne`，但作为独立服务运行。不要把它的 FastAPI 路由或 Python 环境合并到 FinanceDashboard。生产环境需要分别运行 Arachne 后端、Neo4j 和 PostgreSQL，并构建 Arachne 前端：

```bash
cd /root/data/FinanceDashboard/services/arachne/frontend
npm install
VITE_PUBLIC_BASE=/arachne/ VITE_API_BASE=/arachne/api/v1 npm run build
sudo mkdir -p /var/www/arachne
sudo rsync -a --delete dist/ /var/www/arachne/
```

FinanceDashboard 服务环境默认值如下；Arachne 在其他主机时通过项目根目录 `.env` 覆盖：

```dotenv
ARACHNE_API_URL=http://127.0.0.1:16060/api/v1
ARACHNE_PUBLIC_BASE=/arachne
ARACHNE_TIMEOUT_SECONDS=3
```

Arachne 公网集成应保持只读：后端设置 `AUTH_MODE=jwt` 和 `JWT_LOCAL_BYPASS=false`。未携带 JWT 的查询与推理仍可用，写操作返回 403。Arachne 后端仅监听内网或回环地址。

应用主机 Nginx 增加更具体的 API location，并把静态文件发布到同源 `/arachne/`：

```nginx
location ^~ /arachne/api/v1/ {
    proxy_pass http://127.0.0.1:16060/api/v1/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location ^~ /arachne/ {
    root /var/www;
    try_files $uri $uri/ /arachne/index.html;
}
```

公网入口主机也必须把 `/arachne/` 转发到应用主机。不要公开代理 Arachne 的 `/integration/config`。发布后验证：

```bash
curl --fail http://127.0.0.1:16060/health
curl --fail 'http://127.0.0.1:16060/api/v1/companies/resolve/by-stock-code?stock_code=300308.SZ'
curl --fail http://127.0.0.1:8010/api/integrations/arachne/stocks/300308.SZ
curl --fail http://127.0.0.1/arachne/embed.html
```

## 运维与验证

```bash
systemctl status financedashboard
systemctl is-enabled financedashboard
journalctl -u financedashboard -f
ss -ltnp | grep 8010

curl --fail http://127.0.0.1:8010/api/auth/config
curl --fail http://127.0.0.1/api/auth/config
curl --fail https://www.sleepysoft.dev/api/auth/config
```

正常状态应满足：

- `financedashboard.service` 为 `enabled` 和 `active`；
- Uvicorn 仅监听 `127.0.0.1:8010`；
- 应用主机 Nginx 的 `/api/` 上游为 `127.0.0.1:8010`；
- 本机直连、应用主机 Nginx 和公网 API 均返回 HTTP 200。

## 502 排查

```bash
ss -ltnp | grep -E ':(80|8010)\b'
systemctl status financedashboard nginx
journalctl -u financedashboard -n 100 --no-pager
tail -n 100 /var/log/nginx/error.log
grep -R "proxy_pass" /etc/nginx/sites-enabled/
```

若日志出现 `connect() failed (111: Connection refused)`：

1. 检查 Nginx 上游端口是否为 8010；
2. 检查 `financedashboard.service` 是否运行；
3. 直接请求 `http://127.0.0.1:8010/api/auth/config`；
4. 修复后重载 Nginx，并从公网重新验证登录流程。
