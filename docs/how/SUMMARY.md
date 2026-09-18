# HOW 总结 —— 命令速查与排障入口

> 本文件是 how/ 目录的收口（总-分-总的第二个"总"）。步骤细节回到各专题手册。

## 日常命令速查

| 目的 | 命令 | 说明 |
|------|------|------|
| 启动全部（Windows） | `start_all.bat` | 后端 8010 + 前端，可传前端端口 |
| 重启 | `restart_all.bat` | 改动后端代码后必须重启 |
| 停止 | `stop_all.bat` | 含 `--reload` 派生的 worker |
| 前端质量门禁 | `lint.bat` + `smoke.bat` | 改 `.vue`/`.js` 后、提交前必跑 |
| 数据校验门禁 | `validate.bat` | 改 `data/` 或读写数据的代码后必跑 |
| 前端生产构建 | `cd frontend && build.bat` | 部署前执行 |
| Linux 生产更新 | 见 [linux-deployment.md](linux-deployment.md) | systemd 单元 `financedashboard.service` |

## 出问题了先看哪

| 症状 | 第一步 |
|------|--------|
| 主页白屏/报错 | F12 看是哪个接口挂了；后端日志搜 `[data-guard]` 定位坏数据文件 |
| 接口 500 | 后端返回的 `detail` 已带异常类型与消息（全局 exception handler） |
| 价格不更新 | 「设置 → 自动更新」检查间隔配置；`GET /api/scheduler/status` 看上次运行结果 |
| 401 | 未登录或缺 `X-API-Key`；本机 Agent 读项目根目录 `agent_token.txt` |
| 数据校验失败 | 跑 `validate.bat -v`，按 `schemas/` 中对应 schema 修数据或修 schema |

## 部署拓扑一句话

Windows 本机开发：`backend(8010)` + `vite dev`；
Linux 生产：公网 Tailscale 主机反代 → 应用主机 Nginx → `127.0.0.1:8010`（systemd 常驻，禁止 `--reload`）。
