# HOW —— 怎么做

本目录回答"**怎么做**"：安装、启动、部署、运维的操作手册。
动机与设计约束见 [../why/](../why/README.md)，数据与接口规范见 [../what/](../what/README.md)。

## 总览：按场景找手册

| 场景 | 手册 |
|------|------|
| Windows 本机开发（装依赖、起服务、打包） | [windows-setup.md](windows-setup.md) |
| Linux 生产部署（拓扑、systemd、更新、502 排查） | [linux-deployment.md](linux-deployment.md) |

## 专题文档（分）

### [windows-setup.md](windows-setup.md)
- 前置依赖（Python venv、Node）
- 一键脚本：`start_all.bat` / `stop_all.bat` / `restart_all.bat`
- 生产模式：`frontend/build.bat` + `backend/start_production.bat`

### [linux-deployment.md](linux-deployment.md)
- 生产拓扑：公网 Tailscale 主机 → 应用主机 Nginx → `127.0.0.1:8010` Uvicorn
- systemd 服务安装与更新流程
- 常见故障检查清单

## 最常用的命令（速记）

```cmd
start_all.bat        :: Windows 一键启动（后端 8010 + 前端）
restart_all.bat      :: 重启
lint.bat             :: 前端 ESLint（改 .vue/.js 后必跑）
smoke.bat            :: 冒烟测试（提交前必跑）
validate.bat         :: 数据文件 schema 校验（改 data/ 后必跑）
```

## 总结

命令速查与排障入口汇总见 [SUMMARY.md](SUMMARY.md)。
