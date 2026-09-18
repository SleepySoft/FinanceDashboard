# WHY 总结 —— 关键结论速查

> 本文件是 why/ 目录的收口（总-分-总的第二个"总"）。细节回到各专题文档。

## 决策结论一览

| 问题 | 结论 | 出处 |
|------|------|------|
| 回测框架选型 | **vectorbt**：向量化性能领先、维护活跃、适合参数扫描 | [backtest-framework-comparison](backtest-framework-comparison.md) |
| 回测系统定位 | Playground（快速验证）+ 算法库（可维护复用）双层结构 | [backtest-proposal](backtest-proposal.md) |
| 持仓配对算法 | **智能 FIFO + 日内 LIFO**：同日买卖先按做T配对，跨天走 FIFO | [holdings-matching-algorithm](holdings-matching-algorithm.md) |
| QMT 外部接口 | 可行路径已实测确认，结论与注意事项见验证记录 | [qmt-integration-notes](qmt-integration-notes.md) |

## 血泪教训（为什么有现在的防护）

- **2026-07-25 看板白屏事故**：一行未声明的 `let autoTimer` 让整个首页失去交互，且极难定位。
  → 从此引入前端 `npm run lint` + `npm run smoke` 强制门禁（[postmortem](postmortem-empty-dashboard-issue.md)）。
- **价格标记删除 500（2026-09-17）**：Agent 绕过 API 直接写脏数据（缺 `id`、字段名错）。
  → 从此有了 `_normalize_price_marks` 读取规范化、`schemas/` + `validate.bat` 强制校验、以及"写数据优先走 API"的硬性约束。

## 给未来的 AI / 开发者

想推翻这里的任何结论时，先读对应专题文档确认当时的约束条件是否还成立；
推翻后请更新专题文档、本 SUMMARY，并在 `AGENTS.md` 的 Key Design Decisions 记录新决策。
