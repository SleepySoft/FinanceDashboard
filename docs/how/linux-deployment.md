# Linux 生产部署

本文记录 FinanceDashboard 与 Arachne 的生产拓扑、systemd 安装方式、更新流程和常见故障检查。

> 本地调试与生产发布的启动方式不同：本地由 Vite 开发服务器代理 `/arachne/` 到
> `localhost:3000`；生产环境不运行 Vite，而是由 Nginx 直接提供两个项目的构建产物。

## 当前拓扑

```text
Internet
  │  https://www.sleepysoft.dev/dashboard/
  ▼
公网入口主机（Nginx）
  │  /dashboard/* 去掉 /dashboard 后经 Tailscale 反向代理
  ▼
应用主机 100.105.210.96:80（Nginx）
  ├─ /api/*             ─► 127.0.0.1:8010（financedashboard.service / Uvicorn）
  ├─ /arachne/api/v1/*  ─► 127.0.0.1:16060（arachne.service / Uvicorn）
  ├─ /arachne/*         ─► /var/www/arachne（Arachne React 构建产物）
  └─ /*                 ─► /var/www/financedashboard（Vue 构建产物）

独立依赖：

  arachne.service ─► Neo4j :7687 + PostgreSQL :5433
```

两个 FastAPI 后端只监听回环地址，不直接暴露到公网。应用主机的 Nginx 是 API 和静态资源入口；公网入口主机再通过 Tailscale 转发到应用主机。

## 本地调试与生产发布

| 项目 | 本地调试 | 生产环境 |
| --- | --- | --- |
| FinanceDashboard 前端 | Vite 开发服务器 | 构建到 `/var/www/financedashboard`，由 Nginx 提供 |
| Arachne 前端 | Vite `:3000`，Finance Vite 将 `/arachne/*` 代理到它 | 构建到 `/var/www/arachne`，由 Nginx 提供 |
| FinanceDashboard 后端 | 手工启动或开发脚本 | `financedashboard.service`，监听 `127.0.0.1:8010` |
| Arachne 后端 | `scripts/start-all.ps1` 或手工 Uvicorn | `arachne.service`，监听 `127.0.0.1:16060` |
| Arachne 数据库 | 本地 Neo4j、PostgreSQL | 独立且开机自启的 Neo4j、PostgreSQL 服务 |

生产机不能依赖 Arachne Vite `:3000`。若 Nginx 出现连接 `:3000` 被拒绝，说明误用了开发代理配置；生产应改为读取 `/var/www/arachne` 的静态文件。

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
npm ci
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

Arachne 位于 `services/arachne`，但作为独立服务运行。不要把它的 FastAPI 路由或 Python 环境合并到 FinanceDashboard。生产环境需要分别运行 Arachne 后端、Neo4j 和 PostgreSQL；Arachne 前端只在发布时构建，不常驻运行 Vite。

### 首次安装

先初始化子模块，并准备 Arachne 的 Python 环境、Neo4j 和 PostgreSQL。两个数据库可由系统服务或 Docker Compose 管理，但必须在 `arachne.service` 前启动并设为开机自启。

```bash
cd /root/data/FinanceDashboard
git submodule update --init --recursive

cd services/arachne/backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

全新数据库或需要完整重建时，应从嵌套子模块的规范快照一次性恢复，不能靠逐个重放业务批次或编写临时回填脚本补外键：

```bash
cd /root/data/FinanceDashboard/services/arachne
backend/venv/bin/python scripts/import_db.py \
  --input-dir data/ArachneData/newest \
  --clear --yes
```

`--clear` 会清空 Arachne 的 Neo4j 与 PostgreSQL 数据，只能用于首次安装或明确的整库重建。日常更新保留现有数据库，由正式批次或迁移脚本增量更新。

在 `services/arachne/.env` 写入实际的数据库连接信息与生产权限模式（此文件不入库）：

```dotenv
NEO4J_URI=bolt://127.0.0.1:7687
POSTGRES_URL=postgresql://<user>:<password>@127.0.0.1:5433/arachne
AUTH_MODE=header
AUTH_SCOPE_HEADER=X-Arachne-Scope
```

创建 `/etc/systemd/system/arachne.service`：

```ini
[Unit]
Description=Arachne API
After=network-online.target neo4j.service postgresql.service
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/data/FinanceDashboard/services/arachne/backend
EnvironmentFile=-/root/data/FinanceDashboard/services/arachne/.env
ExecStart=/root/data/FinanceDashboard/services/arachne/backend/venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 16060
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

将示例中的 `User=root` 改为实际部署账号，再启用服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now arachne.service
sudo systemctl status arachne.service
```

### 发布 Arachne 前端与更新服务

当前公网入口只发布 `/dashboard/`，并在转发到应用主机时去掉 `/dashboard`。因此两个路径必须区分：浏览器看到的是 `/dashboard/arachne/`，应用主机 Nginx 收到的是 `/arachne/`。Arachne 构建产物中的资源和 API 地址必须使用公网路径，否则 HTML 虽然返回 200，浏览器仍会因请求根路径 `/arachne/assets/*` 和 `/arachne/api/*` 得到 404 而显示黑屏。

```bash
cd /root/data/FinanceDashboard/services/arachne/frontend
npm ci
VITE_PUBLIC_BASE=/dashboard/arachne/ VITE_API_BASE=/dashboard/arachne/api/v1 npm run build
sudo mkdir -p /var/www/arachne
sudo rsync -a --delete dist/ /var/www/arachne/

# Arachne 后端或其 Python 依赖变动后执行
sudo systemctl restart arachne.service
```

完整发布顺序为：更新父仓库和子模块 → 更新 Arachne 依赖/重启 `arachne.service`（如有后端改动）→ 构建两个前端并同步静态文件 → 重启 FinanceDashboard（如有后端改动）→ `nginx -t` 并 reload。根目录旧版 `deploy.sh` 尚未编排 Arachne，不能作为这套集成的完整发布命令。

FinanceDashboard 服务环境默认值如下；Arachne 在其他主机时通过项目根目录 `.env` 覆盖：

```dotenv
ARACHNE_API_URL=http://127.0.0.1:16060/api/v1
ARACHNE_PUBLIC_BASE=/dashboard/arachne
ARACHNE_TIMEOUT_SECONDS=3
```

`ARACHNE_PUBLIC_BASE` 是返回给浏览器的公网前缀，不能填写应用主机内部的 `/arachne`。systemd 服务需要通过 `Environment=` 或 `EnvironmentFile=` 注入该值，修改后执行 `systemctl daemon-reload && systemctl restart financedashboard`。

Arachne 生产集成使用 FinanceDashboard 登录会话决定写权限。Arachne 后端设置 `AUTH_MODE=header` 和 `AUTH_SCOPE_HEADER=X-Arachne-Scope`，并且只监听内网或回环地址。浏览器不能直接访问后端端口，可信的 Nginx 会通过内部鉴权子请求注入该请求头。

应用主机 Nginx 增加更具体的 API location，并把静态文件发布到同源 `/arachne/`。`/arachne/api/v1/` 必须位于 `/arachne/` 静态 location 之前：

```nginx
location = /_arachne_auth_scope {
    internal;
    proxy_pass http://127.0.0.1:8010/api/integrations/arachne/auth-scope;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
    proxy_set_header Cookie $http_cookie;
}

location ^~ /arachne/api/v1/ {
    auth_request /_arachne_auth_scope;
    auth_request_set $arachne_scope $upstream_http_x_arachne_scope;
    proxy_pass http://127.0.0.1:16060/api/v1/;
    proxy_http_version 1.1;
    proxy_set_header X-Arachne-Scope $arachne_scope;
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

`GET /api/integrations/arachne/auth-scope` 对未登录请求返回 `read_only`，对任何已登录 FinanceDashboard 用户返回 `read_write`。因此所有用户都能读取和载入 Arachne 服务端视图，登录用户才能推送、重命名、删除或设置默认视图。该端点只输出权限级别，不返回会话 token。

公网入口主机继续按现有规则转发 `/dashboard/*`；浏览器访问 `/dashboard/arachne/*`，转发到应用主机时对应 `/arachne/*`。不要额外公开 Arachne 的 `/integration/config`。发布后验证：

```bash
curl --fail http://127.0.0.1:16060/health
curl --fail 'http://127.0.0.1:16060/api/v1/companies/resolve/by-stock-code?stock_code=300308.SZ'
curl --fail http://127.0.0.1:8010/api/integrations/arachne/stocks/300308.SZ
curl --fail -D- http://127.0.0.1:8010/api/integrations/arachne/auth-scope
curl --fail http://127.0.0.1/arachne/embed.html
curl --fail https://www.sleepysoft.dev/dashboard/arachne/embed.html
curl --fail https://www.sleepysoft.dev/dashboard/arachne/api/v1/query/health
```

## 运维与验证

```bash
systemctl status financedashboard
systemctl is-enabled financedashboard
journalctl -u financedashboard -f
systemctl status arachne
systemctl is-enabled arachne
journalctl -u arachne -f
ss -ltnp | grep -E ':(8010|16060|7687|5433)\b'

curl --fail http://127.0.0.1:8010/api/auth/config
curl --fail http://127.0.0.1/api/auth/config
curl --fail https://www.sleepysoft.dev/dashboard/api/auth/config
```

正常状态应满足：

- `financedashboard.service` 为 `enabled` 和 `active`；
- `arachne.service`、Neo4j 与 PostgreSQL 为 `enabled` 和 `active`；
- Uvicorn 仅监听 `127.0.0.1:8010`；
- Arachne Uvicorn 仅监听 `127.0.0.1:16060`；
- 应用主机 Nginx 的 `/api/` 上游为 `127.0.0.1:8010`；
- 应用主机 Nginx 的 `/arachne/api/v1/` 上游为 `127.0.0.1:16060`，静态 `/arachne/` 来自 `/var/www/arachne`；
- 本机直连、应用主机 Nginx 和公网 API 均返回 HTTP 200。

## 502 排查

```bash
ss -ltnp | grep -E ':(80|8010|16060|7687|5433)\b'
systemctl status financedashboard arachne nginx
journalctl -u financedashboard -n 100 --no-pager
journalctl -u arachne -n 100 --no-pager
tail -n 100 /var/log/nginx/error.log
grep -R "proxy_pass" /etc/nginx/sites-enabled/
```

若日志出现 `connect() failed (111: Connection refused)`：

1. 检查 Nginx 上游端口是否为 8010；
2. 检查 `financedashboard.service` 是否运行；
3. 直接请求 `http://127.0.0.1:8010/api/auth/config`；
4. 修复后重载 Nginx，并从公网重新验证登录流程。

若错误中的上游为 `127.0.0.1:3000`，这是开发环境 Arachne Vite 未启动；生产 Nginx 不应把 `/arachne/` 代理到该端口，应改为上述 `/var/www/arachne` 静态 location。若上游为 `127.0.0.1:16060`，检查 `arachne.service` 与其 Neo4j、PostgreSQL 依赖。
