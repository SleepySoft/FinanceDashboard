# Windows 环境配置与启动说明

本文档说明如何在 Windows 下安装依赖、启动开发环境以及打包部署。

## 前置依赖

| 组件 | 版本要求 | 说明 |
|------|---------|------|
| Python | 3.10+ | 后端运行环境 |
| Node.js | 18+ | 前端构建与开发服务器 |
| Git | 任意 | 克隆仓库 |

安装完成后，请确保 `python`、`pip`、`node`、`npm` 已加入系统 `PATH`。

## 后端依赖配置

后端依赖清单位于：

```
backend/requirements.txt
```

内容如下：

```text
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
pydantic>=2.9.0
```

首次启动时会自动创建 Python 虚拟环境并安装依赖。也可以手动安装：

```powershell
cd backend
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
```

## 前端依赖配置

前端依赖清单位于：

```
frontend/package.json
```

首次启动时会自动运行 `npm install`。也可以手动安装：

```powershell
cd frontend
npm install
```

## 启动方式

### 方式一：一键启动（推荐）

在项目根目录双击运行：

```
start_all.bat
```

该脚本会依次启动后端和前端，分别在新窗口中运行：

- 后端：`http://localhost:8000`
- 前端：`http://localhost:80`

> 注意：前端 Vite 开发服务器配置在 80 端口，Windows 下需要管理员权限。如果无法启动，请右键 `start_all.bat` 选择「以管理员身份运行」。

### 方式二：分别启动

启动后端：

```powershell
cd backend
start.bat
```

启动前端：

```powershell
cd frontend
start.bat
```

前端开发服务器会通过 `vite.config.js` 中的代理将 `/api/*` 请求转发到 `http://localhost:8000`。

## 生产部署

生产环境下，前端需要构建为静态文件，由后端 FastAPI 统一 serve：

1. 构建前端：

```powershell
cd frontend
build.bat
```

构建输出到 `frontend/dist`。

2. 启动生产服务：

```powershell
cd backend
start_production.bat
```

生产服务监听 `0.0.0.0:80`，同时提供 API 和前端静态文件。

## 常见问题

### 1. 端口被占用

- 后端默认 `8000`，前端开发服务器默认 `80`。
- 可在 `backend/start.bat` 或 `frontend/vite.config.js` 中修改端口。

### 2. 80 端口需要管理员权限

Windows 下监听 80 端口需要管理员权限。开发时也可以将 `frontend/vite.config.js` 中的 `port` 改为 `5173`，然后访问 `http://localhost:5173`。

### 3. 虚拟环境已存在但依赖不全

删除 `backend/venv` 目录后重新运行 `backend/start.bat`，会自动重建并安装依赖。
