# FinanceDashboard 文档中心

文档按 **WHY / WHAT / HOW** 三个维度组织，每个维度内部按「总（README）→ 分（专题文档）→ 总（SUMMARY）」编排：

```
docs/
├── README.md        ← 你在这里：文档导航
├── why/             # 为什么这样做 —— 动机、选型权衡、事故复盘
│   ├── README.md        （总）设计决策的动机总览
│   ├── *.md             （分）各专题：框架选型、算法选型、复盘、可行性验证
│   └── SUMMARY.md       （总）关键结论速查
├── what/            # 系统是什么 —— 数据规范、分析规范、模块设计
│   ├── README.md        （总）系统规范总览
│   ├── *.md             （分）各专题：Stock Schema、分析规范、回测设计、powbox
│   └── SUMMARY.md       （总）规范要点速查
└── how/             # 怎么做 —— 安装、启动、部署、运维
    ├── README.md        （总）操作路径导航
    ├── *.md             （分）Windows 开发环境、Linux 生产部署
    └── SUMMARY.md       （总）常用命令速查
```

## 我该看哪一类？

| 我想…… | 去看 |
|--------|------|
| 理解某个设计为什么是这样 | [why/](why/README.md) |
| 写代码 / 写数据前查规范 | [what/](what/README.md) |
| 把系统跑起来 / 部署 / 排查 | [how/](how/README.md) |

## 文档之外的三个"单一事实源"

- **`AGENTS.md`**（项目根目录）：项目当前状态、决策日志、API 清单、工作流——AI 和人都先读它。
- **`schemas/`**：所有数据 JSON 文件的机器可读 schema，改数据后跑 `validate.bat` 校验。
- **`skill/SKILL.md`**：AI Agent 的角色、硬性约束与操作手册。

## 文档维护约定

1. 新文档先想清楚它是 WHY（动机/权衡/复盘）、WHAT（规范/设计）还是 HOW（操作手册），放进对应目录，并在该目录的 README 和 SUMMARY 中登记。
2. 每个目录保持「总-分-总」：新增专题文档时同步更新本目录 README（总起）与 SUMMARY（总结）。
3. 文档与代码冲突时以代码为准，并尽快修正文档；重大决策变化同时记入 `AGENTS.md` 的 Key Design Decisions。
