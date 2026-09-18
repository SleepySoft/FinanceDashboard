# WHY —— 为什么这样做

本目录回答"**为什么**"：每个重要决策背后的动机、被否决的方案、以及踩过的坑。
读这里的目的是：改代码前先理解约束的来历，避免重复历史上已经否定的做法。

## 总览：本项目最关键的几条"为什么"

1. **为什么文件存储而不是数据库？** 个人项目、单用户、数据量小；文件可直接查看/备份/git 跟踪，省去运维成本。代价是必须做防护：原子写 + 安全读取 + schema 校验（见 AGENTS.md 决策 8、15）。
2. **为什么 AI 只写报告不写笔记？** 笔记是用户的私人思考区，AI 污染会破坏信任（AGENTS.md 决策 13）。
3. **为什么选 vectorbt 做回测？** 见 [backtest-framework-comparison.md](backtest-framework-comparison.md) 的多框架对比。
4. **为什么持仓匹配用"智能 FIFO + 日内 LIFO"？** 见 [holdings-matching-algorithm.md](holdings-matching-algorithm.md) 的算法对比。
5. **为什么前端有 lint + smoke 硬门禁？** 因为一行未声明的 `autoTimer` 曾让整个看板白屏——见 [postmortem-empty-dashboard-issue.md](postmortem-empty-dashboard-issue.md)。

## 专题文档（分）

| 文档 | 回答的问题 |
|------|-----------|
| [backtest-framework-comparison.md](backtest-framework-comparison.md) | 回测框架为什么选 vectorbt（架构/性能/维护性对比） |
| [backtest-proposal.md](backtest-proposal.md) | 回测系统的定位权衡：Playground 快速验证 vs 算法库可维护复用 |
| [holdings-matching-algorithm.md](holdings-matching-algorithm.md) | 成交配对算法的候选方案对比，为什么选智能 FIFO + 日内 LIFO |
| [postmortem-empty-dashboard-issue.md](postmortem-empty-dashboard-issue.md) | "看板空白"事故复盘：为什么难修、如何防止再犯 |
| [qmt-integration-notes.md](qmt-integration-notes.md) | QMT 外部接口可行性验证：哪条路通、哪条路不通、为什么 |

## 总结

关键结论与速查见 [SUMMARY.md](SUMMARY.md)。
