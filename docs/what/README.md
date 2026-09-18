# WHAT —— 系统是什么

本目录回答"**是什么**"：系统的数据规范、分析规范、模块设计——写代码或写数据之前的"施工图"。
WHY（为什么）在 [../why/](../why/README.md)，HOW（怎么操作）在 [../how/](../how/README.md)。

## 总览：系统的规范体系

| 层次 | 规范载体 | 作用 |
|------|---------|------|
| 数据结构 | [stock-schema.md](stock-schema.md) + 机器可读的 `schemas/*.schema.json` | `data/` 下每个 JSON 文件的字段、类型、枚举 |
| 分析产出 | [analysis-spec.md](analysis-spec.md) | AI 生成的基本面/技术面报告的内容规范 |
| 子系统设计 | [backtest-design.md](backtest-design.md)、[powbox-design.md](powbox-design.md) | 回测系统与 POW 防刷模块的设计文档 |

## 专题文档（分）

| 文档 | 内容 |
|------|------|
| [stock-schema.md](stock-schema.md) | `meta.json` / `state.json` 的完整 schema、维度取值、迁移规则；`dimensions` 只能由 `tags` 计算，禁止落盘 |
| [analysis-spec.md](analysis-spec.md) | 个股分析规范：分析是情报工作而非数字罗列；报告的立场、因果分析要求 |
| [backtest-design.md](backtest-design.md) | 回测系统设计：架构、数据源、参数与结果模型 |
| [powbox-design.md](powbox-design.md) | powbox 可复用 POW（工作量证明）模块：协议、模块边界，供留言/反馈防刷及其他项目复用 |

## 相关但不在本目录

- 价格阶梯（ladder）结构：`backend/ladder.py` 文件头 docstring 是唯一事实源；
- 顶层数据文件（`_dashboard.json` 等）结构：`schemas/` 目录；
- API 清单与运行状态：`AGENTS.md`。

## 总结

要点速查见 [SUMMARY.md](SUMMARY.md)。
