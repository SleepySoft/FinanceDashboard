# FinanceDashboard

个人定制化的股票分析看板，支持多维度标签评估、技术分析、基本面分析、以及持仓管理。

## 功能

### 1. 股票跟踪与评估
- 多维度标签系统：质量、估值、时机、风险、综合 verdict
- 价格标记：在关键价位设置买入/卖出/关注标记
- 状态分组：跟踪中、看好、观望、回避、归档

### 2. 分析报告
- 基本面分析（财务指标、行业对比、竞争力）
- 技术面分析（均线、MACD、KDJ、RSI、BOLL）
- 每日简报（基于当天走势和新闻的简短更新）
- 报告自动缓存，避免重复分析

### 3. 持仓管理（新）
- 逐笔成交录入，支持幂等保护
- 智能匹配算法：日内做T自动识别，跨天走FIFO
- 自动计算手续费（万2.5，最低5元）
- 实时显示：持仓数量、成本、浮动盈亏、做T利润

### 4. 前端看板
- 分组视图（按状态/评级/行业）
- 矩阵视图（质量 × 估值）
- 股票详情弹窗/独立页面
- 支持手机端访问

## 技术栈

- **Backend**: FastAPI + Python
- **Frontend**: Vue 3 + Vite
- **数据源**: Sina实时行情、kimi_finance（同花顺）、Tushare
- **部署**: 单VM，Uvicorn 直接 serve 前端静态文件，端口 80

## 目录结构

```
FinanceDashboard/
├── backend/           # FastAPI 服务
├── frontend/          # Vue3 前端
├── data/             # 股票数据（每只股票一个目录）
│   ├── {code}/
│   │   ├── meta.json        # 元数据、标签、缓存
│   │   ├── reports/         # 分析报告
│   │   ├── briefs.json      # 每日简报
│   │   ├── holdings.json    # 持仓记录
│   │   └── notes.md         # 笔记
│   ├── _dashboard.json      # 价格缓存
│   └── _tasks.json          # 分析任务队列
├── skill/            # AI Agent Skill 定义
└── docs/             # 设计文档
```

## 快速开始

### Linux / macOS

```bash
# 构建前端（如有代码改动）
cd frontend
npm run build

# 启动后端（同时 serve API + 前端静态文件）
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 80
```

### Windows

项目已提供 Windows 批处理脚本，详见 [docs/windows-setup.md](docs/windows-setup.md)。

```powershell
# 一键启动后端 + 前端（推荐）
start_all.bat

# 或分别启动
cd backend && start.bat
cd frontend && start.bat

# 生产部署：先构建前端，再由后端统一 serve
cd frontend && build.bat
cd backend && start_production.bat
```

## AI Agent 使用

Agent 负责深度分析，用户可以通过微信直接交互：

| 命令 | 功能 |
|------|------|
| "分析 {code}" | 生成基本面+技术面报告 |
| "刷新价格" | 更新所有股票价格 |
| "标记 {code} {label} {price}" | 添加价格标记 |
| "录入 {code} 买入/卖出 {price} {qty}" | 录入成交 |
| "持仓 {code}" | 查看持仓分析 |

详见 [skill/SKILL.md](skill/SKILL.md)
