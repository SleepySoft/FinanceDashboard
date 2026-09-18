# WHAT 总结 —— 规范要点速查

> 本文件是 what/ 目录的收口（总-分-总的第二个"总"）。完整内容回到各专题文档。

## 数据规范（写数据前必读）

- **meta.json**（静态）：`code`（必须带交易所后缀）、`name`、`sector`、`type`、`added_at`。
- **state.json**（可变）：`tags`（维度唯一存储地）、`status`、`price_marks`、`notes`、`record_prices`、`holdings`。
  - 维度值只允许 `green / yellow / red / none`；`watchlist`、`unread` 为布尔。
  - `price_marks` 每项必须有 `label`(string) + `price`(number)；`id` 缺失时后端自动生成。
- **`dimensions` 永不落盘**：API 响应里的 `dimensions` 由 `_normalize_dimensions()` 从 `tags` 计算。
- 机器可读版本在 `schemas/`；改完数据跑 `validate.bat`。

## 分析产出规范

- 基本面与技术报告**必须拆成两个文件**：`fundamental_YYYYMMDD.md` / `technical_YYYYMMDD.md`，禁止合并为 full 单文件。
- 报告要有明确观点（看好/观望/回避）和因果链，不做数据罗列（见 [analysis-spec.md](analysis-spec.md)）。

## 子系统一句话

- **回测**：vectorbt 内核，策略注册表 + 记录持久化（[backtest-design.md](backtest-design.md)）。
- **powbox**：Hashcash 风格 POW，前后端自包含模块，可直接拷去其他项目（[powbox-design.md](powbox-design.md)）。

## 修改规范时

1. 改专题文档；2. 同步 `schemas/`（如涉及数据文件）；3. 更新本 SUMMARY 与 what/README；
4. 若影响 AI 行为，同步 `skill/SKILL.md` 硬性约束。
