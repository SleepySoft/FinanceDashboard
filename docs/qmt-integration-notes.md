# 国金 QMT 外部接口验证记录（2026-09-11 实测）

本机环境：`D:\国金证券QMT交易端`（国金QMT智能策略交易终端 **2.1.19.0**）。
目的：验证「外部 Python 程序通过 xtquant 连接 QMT」的可行路径。

## TL;DR — 实测结论

| 路径 | 行情 xtdata | 交易 xttrader | 结论 |
|------|------------|--------------|------|
| 完整版 QMT（XtItClient，已登录） | ❌ 行情 handler 全缺失（200005），仅静态信息可查 | ❌ `connect()` 返回 **-1** | 只能查板块成分股等静态数据，不能取行情、不能交易 |
| miniQMT（XtMiniQmt.exe） | 未验证到 | 未验证到 | 登录失败（疑似与完整版账号互踢），待排除冲突后重试 |
| xtquant-big-convert 桥接 | 可行（待实施） | 可行（待实施） | 完整版内置 Python 跑桥接策略，转发给外部 |
| xtdatacenter 独立数据中心 | 可行（需投研 token） | ❌ 不含交易 | 不依赖 QMT 客户端的纯行情方案 |

**一句话：国金这版完整客户端对外只暴露静态信息查询；行情和交易接口必须走 miniQMT 或桥接。**

## 验证过程与关键发现

### 1. xtquant 库不在安装目录里

笔记中说的 `bin.x64/Lib/site-packages/xtquant` 在本机**不存在**（`bin.x64/Lib` 都没有）。
整个安装目录搜索无 xtquant Python 包，只有服务端的 `XtQuantServer.dll`。

**替代方案（已采用）**：PyPI 有官方 xtquant，直接装：

```bash
pip install xtquant   # 实测版本 250807.1.2
```

whl 自带 cp36~cp313 的预编译 `.pyd`，Python 3.8（conda dev 环境，已装）和 3.12（项目 venv）都能用。
完整版内置编辑器用的是它自己的 Python 3.6（`bin.x64/python36.dll`），与外部无关。

### 2. 服务发现机制（排障必备）

xtdata 不固定连某个端口，按顺序发现服务：

1. `xtdatacenter` 本地服务（如果起过独立数据中心）
2. 扫描 `%USERPROFILE%\.xtquant\<实例id>\xtdata.cfg`（QMT/miniQMT 启动服务后写入）
3. 兜底 `127.0.0.1:58610`

国金完整版实际监听的是 **58600**（`netstat -ano | grep <PID>` 可查），且不会写 xtdata.cfg，
所以自动发现失败时报：`无法连接xtquant服务，请检查QMT-投研版或QMT-极简版是否开启`。
此时可显式连接：`xtdata.connect('127.0.0.1', 58600)`。

### 3. 完整版直连实测（已登录状态）

`xtdata.connect('127.0.0.1', 58600)` **连接成功**，但逐项测试结果：

```
[EMPTY] get_instrument_detail          # 无报错但无数据
[FAIL]  get_full_tick                  # 200005 未找到处理函数
[FAIL]  get_market_data_ex(1d)         # getTradingDatesByMarket 200005
[FAIL]  get_local_data(1d)             # 同上（连交易日历都要 RPC）
[FAIL]  download_history_data          # supplyHistoryData 200005
[OK ]   get_stock_list_in_sector       # 沪深A股 5220 只 ✓
```

**结论：RPC 通道正常，但行情类 handler 服务端压根没注册。** 不是版本不匹配，是国金完整版不加载投研行情子系统。

### 4. 交易接口实测（完整版 userdata）

```python
from xtquant import xttrader
t = xttrader.XtQuantTrader(r'D:\国金证券QMT交易端\userdata', 919001)
t.start()
t.connect()   # -> -1
```

返回 **-1**，精确复现笔记预告的国金问题。xttrader 的服务端点配置在 miniQMT 的
`userdata_mini` 里，完整版客户端不对外提供交易 RPC。

**坑提醒**：`XtQuantTrader(path, session)` 第一个参数是 userdata 路径（str）、第二个是会话号（int），
顺序写反会报 `incompatible constructor arguments` 而不是清晰的参数错误。

### 5. miniQMT 登录情况

- `bin.x64\XtMiniQmt.exe` 可正常启动，登录窗需要 资金账号 + 密码 + 图形验证码
- 未登录时：进程在线、连券商服务器正常，但**本地服务端口不起**，xtdata 连不上
- 本次登录失败的高度可疑原因：**完整版 QMT 同时在线，同账号互踢**
  （证据：userdata_mini 全部文件都是当天生成，说明从未登录成功过）
- 待办：完全退出完整版（托盘右键退出，关窗口不算）→ 单独登录 miniQMT → 重跑测试脚本

### 6. 完整版客户端的正面信息

- 账号有 **Level-2 行情权限**（日志：`level2 auth SH:2 SZ:2`）
- 内置 Python 策略环境完整（模型研究/模型交易，含 python 示例策略）——桥接方案的基础
- 注意：QMT 是自绘界面，外部合成的鼠标点击基本不响应，UI 操作只能手动

## 可行方案对比

**A. xtquant-big-convert 桥接**（行情+交易都要时推荐）
在完整版「模型研究」新建 Python 策略 → 粘贴桥接代码 → 运行。
内置环境有完整行情+交易能力，桥接策略转发成本地 socket 服务供外部连接。
需要一次性 GUI 操作（建策略/粘贴/运行）。

**B. xtdatacenter 独立数据中心**（只要行情）
xtquant 自带，不依赖 QMT 客户端，直连迅投数据服务器；需投研 token（官网可申请试用）。
无交易能力。适合给 FinanceDashboard 供行情。

**C. miniQMT 标准路径**（官方推荐，最省心）
先退完整版再登 miniQMT 排除互踢；若报「无权限」类错误则需找国金开通量化/miniQMT 权限。

## 复测脚本

已入库，miniQMT 登录成功或环境变化后直接重跑：

```bash
# 行情（默认连 127.0.0.1:58600；miniQMT 起来后端口可能不同，先 netstat 查）
python scripts/qmt_test_xtdata.py [host] [port]

# 交易（不下单，只查资产/持仓）
set QMT_ACCOUNT=资金账号
python scripts/qmt_test_xttrader.py
```

## 参考资料

- xtquant 官方文档：http://dict.thinktrader.net/nativeApi/start_now.html
- 桥接方案：https://github.com/ 搜 `xtquant-big-convert`
- 本机 QMT 日志：`D:\国金证券QMT交易端\userdata\log\`（完整版）、`userdata_mini\log\`（miniQMT）
