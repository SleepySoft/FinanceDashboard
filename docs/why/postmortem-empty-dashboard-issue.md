# 复盘报告：Dashboard "没有股票" 故障为什么这么难修

**日期：** 2026-07-25
**症状：** 前端启动后 Dashboard 始终显示"没有匹配的股票"，且页面完全失去交互
**根因：** `frontend/src/views/Dashboard.vue` 中 `autoTimer` 变量未声明（少一行 `let autoTimer = null`）
**修复成本：** 一行代码
**定位成本：** 约 1.5 小时、40+ 次工具调用、多种假设逐一排除

---

## 一、故障时间线（简化）

1. `onMounted(() => { load(); startAutoRefresh() })` 执行；
2. 首屏渲染时股票数据尚未返回，**合法地**显示空状态；
3. `startAutoRefresh()` 引用未声明的 `autoTimer`，ES 模块严格模式下抛出 `ReferenceError`；
4. 异常发生在 Vue 调度器的 `flushPostFlushCbs` 阶段，**毒化了全局更新队列**（组件 job 的 QUEUED 标志永久卡死、flush 永久停摆）；
5. 此后整个应用的响应式渲染管线冻结：API 明明返回了 31 只股票，DOM 永远不更新，连路由切换都失效；
6. 用户看到的就是"没有股票"。

## 二、为什么难修：五个层面的"距离"

### 1. 因果距离：一行漏声明 → 全局渲染瘫痪

根因是**一行变量声明缺失**，但症状是**整个应用的渲染系统死亡**。两者之间的距离极远：

- 错误抛出点：`startAutoRefresh`（一个副作用函数）
- 受害对象：Vue 的 job 队列 / flush 调度器（框架内部状态）
- 可见症状：Dashboard 空列表（业务 UI 层）

普通的 bug 是"错在哪就坏在哪"，这个 bug 是"错在 A 处，毁掉了框架的基础设施 B，表现为 C 处数据不显示"。排查者被迫横跨业务代码 → 框架内部 → 浏览器运行时三个层面。

### 2. 错误的"隐身"：最该报警的地方一片安静

正常情况下，`ReferenceError` 应该在控制台留下鲜红的报错。但本次排查中：

- 异常被 Vue 的 `callWithAsyncErrorHandling` 捕获后又以 **unhandledrejection** 形式逃逸，出现在 `resolvedPromise.then(flushJobs)` 的 Promise 链上，堆栈完全位于框架内部，不指向业务代码；
- 通过 WebBridge 注入的 `console`/`error` 钩子**在页面刷新后会被清除**，而错误只在**首次挂载**的瞬间发生一次，之后不再复现——后期注入的钩子永远抓不到"案发时刻"；
- 组件 state 一切正常（31 只股票、无筛选、loading=false），`app.config.errorHandler` 装好后再也收不到任何错误——给人一种"系统没病"的假象。

最终是靠在 `index.html` 的 `<head>` 里**前置注入全局错误捕获**（保证在任何模块执行前就位），才抓到了那行决定性的 `autoTimer is not defined`。

### 3. 症状的"污染"：冻结制造了无数假线索

渲染管线冻结后，所有后续观察都是"不可信"的：

| 观察到的现象 | 当时的假设 | 真相 |
|---|---|---|
| `/api/stocks` 返回正常但页面空 | 前端过滤条件问题 | 过滤器默认全关，无关 |
| `stocks.value` 有 31 条但 `filteredStocks` 渲染为 0 | computed 依赖链损坏 | 渲染 effect 根本没被调度 |
| 订阅链表单向断裂（effect.deps 有、dep.subs 没有） | Vue 3.5 双向链表 bug | 是冻结的**结果**而非原因 |
| 切换路由 hash 页面不变 | vue-router 5 与 Vue 3.5 不兼容 | 整个 App 的渲染全冻结 |
| 手动 `instance.update()` 能渲染出数据 | 响应式丢依赖 | 渲染函数本身完全健康 |

每一个现象都看起来像一个独立的 bug，引出了对 Vue 版本（3.5.40→3.5.13）、vue-router（5→4）的降级实验——全部无效。这些"假线索"消耗了排查的大部分时间。

### 4. 环境的"噪音"：多个真实问题叠加

排查起点处同时存在多个**真实的**环境问题，容易把根本原因淹没：

- 后端没启动（端口 8000 无监听）→ 第一假设"API 挂了"合情合理；
- 机器上 Python venv、node_modules 都不存在，依赖安装就花了十几分钟；
- 后台任务 60 秒超时反复杀掉 uvicorn/vite，造成"服务时好时坏"的假象；
- `data/_dashboard.json` 缺失（价格为空）——是干扰项但不致命；
- `index.html` 与 `App.vue` 根节点都是 `<div id="app">`，出现嵌套双 `#app` 的诡异 DOM 结构——又是一个看似可疑实则无害的线索。

### 5. 工具的"盲区"：框架内部状态不可见

Vue 3.5 的调度器队列、批处理深度、job 标志位全部是**模块私有状态**，无法从页面直接读取。定位卡死点只能靠间接证据拼图：

- `instance.job.flags === 5`（QUEUED|ALLOW_RECURSE 永久卡死）
- 手动调用 `effect.scheduler()` 后 flags 变化但 flush 不执行
- 微任务、Promise、批处理机制全部验证正常，逐段排除

这要求排查者**阅读 Vue 3.5 调度器源码**（`queueJob`/`flushJobs`/`batch`/`endBatch`）才能理解观察到的状态，门槛很高。

## 三、关键转折：怎么最终找到的

1. **确认数据链路完好**：WebBridge 抓网络包，`/api/dashboard` 返回 200 且含 31 只股票 → 排除后端；
2. **确认组件状态完好**：读取 Vue 实例 `setupState`，`filteredStocks = 31`、无筛选 → 排除业务逻辑；
3. **确认渲染函数完好**：手动 `instance.update()` 强制渲染，UI 正常显示股票 → 问题收敛到"触发→调度"链路；
4. **确认队列卡死**：`instance.job.flags` 永久停在 5（QUEUED 卡死），手动清理后再次被卡回 → 曾有异常破坏了调度器；
5. **前置埋点抓第一现场**：在 `index.html` 注入最早执行的错误捕获，刷新后拿到 `ReferenceError: autoTimer is not defined`，堆栈直指 `flushJobs` 中的 mounted 钩子 → 真相大白。

## 四、经验教训

### 给项目的可执行改进

1. **加 ESLint（`no-undef`）** —— ✅ 已完成（2026-07-25）：`frontend/eslint.config.js`（flat config，`no-undef: error`），`npm run lint`。首次运行即发现 StockPanel.vue 中 3 个同类未声明变量（`expandedReportId`/`fundExpandedIndex`/`techExpandedIndex`），已修复。
2. **加冒烟测试** —— ✅ 已完成（2026-07-25）：`frontend/tests/smoke.mjs`（playwright-core + 系统 Chrome，免下载浏览器），`npm run smoke`。负向验证通过：重新引入 autoTimer bug 时测试如期失败。
3. **给 App 配置全局 `errorHandler`/`warnHandler`**（`main.js`），把错误持久化到 `localStorage` 或上报，而不是只打 console——页面一刷新证据就没了。（待做）
4. **顺带修复**：`index.html` 的挂载点 `<div id="app">` 与 `App.vue` 根节点 `id="app"` 重复，建议 App.vue 根节点改名（如 `id="app-root"`），消除嵌套同 id 的隐患。（待做）
5. `start_all.bat` 首次运行依赖安装较慢且无进度提示，建议文档注明或加镜像源说明。（待做）

### 给排查者的方法论

1. **先切分"数据层 / 状态层 / 渲染层"，逐层确认健康度**，不要直接在症状层找原因；
2. 当"状态正确但 UI 不更新"时，**手动强制渲染一次**——能渲染说明问题在触发/调度，不能渲染说明问题在渲染函数，一刀两半；
3. 对"只在启动瞬间发生一次"的错误，**埋点必须在任何业务代码执行之前**（`index.html` 内联脚本），事后注入的钩子永远抓不到案发时刻；
4. **UI 冻结会污染所有后续观察**——看到的任何"异常"都可能是冻结的结果而非原因，警惕被假线索带偏去降级依赖；
5. 怀疑框架调度器时，直接读 `node_modules` 里的 dist 源码确认机制，比凭记忆推理可靠得多。

## 五、一句话总结

> 这是一个**修复成本一行、定位成本极高**的 bug：漏声明的变量在 Vue 调度器最脆弱的时刻（mounted 钩子 flush 阶段）爆炸，把异常从"业务错误"升级成"框架基础设施损坏"，于是症状（没股票）、第一现场（ReferenceError）、真实损坏（调度队列卡死）三者完全分离——只有把它们重新拼在一起，答案才浮现。
