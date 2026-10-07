# 股票提醒功能设计草案

## 1. 要解决的问题

分析报告经常给出未来需要复核的事项，例如：

- 公司预计在 10 月下旬发布三季报，届时复核收入增速与毛利率；
- 某项政策将在下月公布细则，届时重新判断产业影响；
- 下一份财报发布后检查订单、库存或现金流；
- 到某个日期重新评估当前投资结论。

这些内容目前只存在于报告正文中，用户必须记住并主动回来查找。提醒功能要把它们变成结构化的“在某个时间做某件事”。

第一版的最小对象只有两个必要信息：

1. `remind_at`：什么时候提醒；
2. `action`：提醒时要做什么。

股票、来源报告、状态和创建来源用于管理与追溯，不要求用户每次填写。

## 2. 领域边界

提醒表示未来需要人工复核的事项，不负责自动执行分析，也不等同于现有对象：

- `_tasks.json` 是 Agent 分析任务队列；
- 后台 scheduler 执行价格刷新、异动扫描等周期任务；
- `PriceLevel` 描述价格位置和交易计划；
- reminder 只回答“什么时候回来检查什么”。

第一版只提供站内提醒。浏览器关闭时不会发送系统通知、邮件或微信消息；重新打开 Dashboard 后，已到期事项仍会持续显示，直到完成、取消或改期。

## 3. 数据归属与存储

每只股票使用独立文件：

```text
data/{code}/reminders.json
```

采用逐股票存储的原因：

- 提醒天然属于某只股票，和报告一起迁移、备份和删除；
- 单个文件损坏只影响一只股票；
- 符合现有逐股票数据隔离和故障降级原则；
- 当前股票数量下，全局列表扫描这些小文件成本可控。

全局提醒列表由后端聚合生成，不维护容易失去同步的 `_reminders.json` 索引。

文件结构：

```json
{
  "version": 1,
  "items": [
    {
      "id": "rem_7b8f4a2d",
      "action": "查看三季报，复核收入增速、毛利率和经营现金流",
      "remind_at": "2026-10-30T09:00:00+08:00",
      "state": "active",
      "source": "manual",
      "origin": null,
      "created_by": "admin",
      "created_at": "2026-10-07T13:30:00+08:00",
      "updated_at": "2026-10-07T13:30:00+08:00",
      "completed_at": null
    }
  ]
}
```

字段约束：

| 字段 | 规则 |
|------|------|
| `id` | 后端生成且在该股票内唯一 |
| `action` | 必填，去除首尾空白后 1～500 字 |
| `remind_at` | 必填，带时区的 ISO 8601 时间；前端按本地时区输入和显示 |
| `state` | `proposed / active / completed / cancelled` |
| `source` | `manual / agent` |
| `origin` | Agent 建议时记录 `{task_id, report_ids}`，手工提醒为 `null` |
| `created_by` | 手工提醒记录登录用户；Agent 建议为 `agent` |
| `created_at` | 创建时间 |
| `updated_at` | 最近修改时间 |
| `completed_at` | 完成时写入，其他状态为 `null` |

“待提醒”“今日到期”“已逾期”是根据 `state=active`、当前时间和 `remind_at` 计算出的展示状态，不写回文件。这样不会依赖后台任务在某个时刻修改数据，也避免服务停机期间漏掉提醒。

## 4. 状态与权限

状态流转：

```text
Agent 分析 ──> proposed ──接受/改期──> active ──完成──> completed
                       │                    └─取消──> cancelled
                       └─否决──────────────> cancelled

用户手工创建 ────────────────────────> active
```

- 手工提醒创建后立即生效；
- Agent 只能创建 `proposed`，不能替用户启用提醒；
- 接受 Agent 建议时，用户可以修改时间和事项；
- 已过期的 proposed 建议不能直接接受，必须先改成未来时间；
- active 提醒允许改期，改期就是第一版的“稍后提醒”；
- completed 和 cancelled 默认只在历史筛选中显示；
- 写操作沿用 Dashboard 权限，只有 `admin` 或 `X-API-Key` Agent 能写；readonly 和匿名用户只能在已有读取权限范围内查看。

提醒属于共享股票数据，不按用户私有化。`created_by` 只用于追溯，所有管理员看到相同状态，避免多人看到同一股票却各自拥有互相冲突的提醒。

## 5. Agent 与分析报告的关系

不要从 Markdown 报告正文中解析日期。报告仍可以用自然语言解释原因，但提醒必须作为结构化字段随完成请求提交。

扩展 `POST /api/agent/tasks/{task_id}/complete`：

```json
{
  "reports": [
    {"path": "reports/fundamental_20261007.md", "type": "fundamental"},
    {"path": "reports/technical_20261007.md", "type": "technical"}
  ],
  "reminders": [
    {
      "remind_at": "2026-10-30T09:00:00+08:00",
      "action": "查看三季报，复核收入增速、毛利率和经营现金流"
    }
  ]
}
```

后端将这些条目统一写成 `source=agent, state=proposed`，并记录 task 和报告来源。同一个 `task_id` 的完成请求重试时，替换该任务尚处于 proposed 的建议，不能重复追加；已被用户接受、完成或取消的提醒不受重试影响。

Agent 只有在存在明确未来动作时才建议提醒：

- 有可执行的复核动作；
- 有合理的提醒时间；
- `action` 写明要核对的指标或事件，不能只写“关注”“继续观察”；
- 不确定发布日期时，应选择一个合理的复核日，并在 action 中说明“检查是否已披露”，不能虚构精确公告时间。

示例：

- 好：`2026-10-30 09:00 — 检查三季报是否披露；若已披露，复核收入增速和毛利率。`
- 不好：`未来 — 关注财报。`

## 6. API

### 股票内管理

| Endpoint | Method | 用途 |
|----------|--------|------|
| `/api/stocks/{code}/reminders` | GET | 获取该股票全部提醒，默认排除历史状态 |
| `/api/stocks/{code}/reminders` | POST | 手工创建 active 提醒 |
| `/api/stocks/{code}/reminders/{id}` | PATCH | 修改时间/事项，或接受、完成、取消、恢复 |
| `/api/stocks/{code}/reminders/{id}` | DELETE | 永久删除提醒 |

PATCH 采用部分更新：

```json
{
  "remind_at": "2026-11-01T09:00:00+08:00",
  "action": "查看三季报并更新基本面判断",
  "state": "active"
}
```

### 全局聚合

```text
GET /api/reminders?scope=due&code=&state=&from=&to=
```

`scope` 提供常用筛选：

- `due`：已到期和逾期的 active 提醒；
- `upcoming`：未来 active 提醒；
- `proposed`：Agent 待确认建议；
- `history`：completed/cancelled；
- `all`：全部。

返回项附带股票 `code` 和 `name`，按以下顺序排序：逾期、今日、未来；同组内按 `remind_at` 升序。

## 7. 前端交互

### 首页

顶部增加提醒入口，显示两个独立数量：

- 红色数字：已到期/逾期；
- 黄色数字：Agent 待确认。

点击后进入全局提醒页或抽屉。首页股票卡只在存在已到期提醒时显示一个简短徽章，避免把完整事项塞进卡片。

### 全局提醒页

默认展示“需要处理”：

1. 已逾期；
2. 今日到期；
3. 即将到期；
4. Agent 待确认。

每条显示股票、时间、事项和来源，提供：完成、改期、取消；proposed 提供接受、编辑后接受、否决。

### 股票面板

在股票详情增加“提醒”区块：

- 一个最小创建表单：日期时间 + 要做的事；
- 当前 active 和 proposed 提醒；
- 历史提醒折叠显示；
- Agent 建议显示来源报告链接，方便用户回看上下文。

时间线上可以显示提醒的创建和完成记录，但提醒的编辑与状态管理集中在“提醒”区块，避免时间线承担表单职责。

## 8. 提醒判定

后端统一按服务器当前 UTC 时间与 `remind_at` 比较，前端只负责展示：

- `overdue`：`remind_at < 今天 00:00`；
- `due_today`：本地日期为今天；
- `due_now`：`remind_at <= now`；
- `upcoming`：`remind_at > now`。

日期边界按用户配置时区计算，第一版默认 `Asia/Shanghai`，配置项为 `timezone`。文件中始终保留 ISO 8601 偏移，避免服务器时区影响结果。

首页现有 30 秒 Dashboard 轮询可以刷新提醒数量，不需要把提醒接入后台 scheduler。后续接入邮件、Webhook 或浏览器推送时，再由独立通知投递器消费 active reminder；提醒本体和状态模型无需改变。

## 9. 数据安全与校验

实现时必须同时完成：

- 新增 `schemas/reminders.schema.json`；
- 更新 `scripts/validate_data.py` 可识别的新文件类型；
- 更新 `docs/what/stock-schema.md`、`docs/what/SUMMARY.md` 和 `AGENTS.md`；
- 读取使用 `_safe_json_load()`，单股文件损坏返回空列表并记录 `[data-guard]`；
- 写入使用 `_atomic_json_dump()`；
- 对 code、id、状态和时间做服务端校验；
- 修改数据文件代码后运行 `validate.bat`；
- 前端改动后运行 lint 和 smoke。

## 10. 第一阶段实施范围

第一阶段一次完成可用闭环：

1. reminders 存储模块、schema 和 CRUD；
2. Agent complete 可提交 proposed reminders；
3. 股票面板创建和管理提醒；
4. 全局提醒页与首页数量入口；
5. 到期、逾期、待确认筛选；
6. 数据验证、后端测试、前端 lint/smoke。

第一阶段不实现：重复提醒、农历/交易日规则、自动抓取公告日期、邮件/短信/微信、系统通知、自动启动新分析。这些能力以后都可以引用 reminder id 增加，不需要改变第一版的“时间 + 事项”核心模型。

## 11. 验收场景

1. 用户在股票面板填写明天 09:00 和事项，保存后首页即显示未来提醒；
2. 到达时间后，不依赖 scheduler 写盘，提醒自动进入到期列表；
3. 用户改期后立即离开到期列表，在新时间再次出现；
4. 用户完成提醒后，它只出现在历史记录；
5. Agent 完成分析并提交提醒建议，建议显示为待确认且不计入到期数量；
6. 用户编辑并接受建议后，它成为 active；
7. Agent 完成请求重试不会产生重复建议；
8. 某只股票的 reminders.json 损坏时，其他股票和 Dashboard 仍正常返回；
9. 服务停机跨过提醒时间，恢复后该提醒仍显示为逾期；
10. readonly 用户无法创建、修改或删除提醒。
