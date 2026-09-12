# powbox — 可复用的 POW（工作量证明）与消息/反馈机制

本文档描述协议与模块边界，供其它项目复用。代码位置：

- 后端：`backend/powbox/`（`pow.py` 协议核心、`routes.py` FastAPI 路由）
- 前端：`frontend/src/powbox/`（`sha256.js`、`solver.js`、`PowPanel.vue`、`api.js`）

设计目标：POW 与业务（消息、反馈）完全解耦；不引入第三方依赖；不记录 challenge 历史。

## 1. 协议（Hashcash 风格，内容绑定）

```
客户端                                服务端
  │  POST /api/pow/challenge {scope}    │
  │ ──────────────────────────────────> │  签发自包含 HMAC challenge：
  │   {challenge, min_difficulty, ...}  │  fd1.<scope>.<username>.<expiry>.<rand>.<hmac>
  │                                     │
  │  本地求解（Web Worker，纯 JS）：      │
  │  找 nonce 使                        │
  │  sha256(challenge + ":" +           │
  │         sha256hex(content) + ":" +  │
  │         nonce)                      │
  │  的前 difficulty 个 bit 全为 0       │
  │                                     │
  │  POST 业务接口 {..., pow:           │
  │    {challenge, nonce, difficulty}}  │
  │ ──────────────────────────────────> │  校验：签名 / 过期 / scope / 用户 /
  │                                     │  difficulty ≥ 当前最低配置 /
  │                                     │  哈希前 difficulty bit 全为 0
```

要点：

- **内容绑定**：哈希材料包含 `sha256hex(content)`。content 由业务层规范化：
  消息 = 消息正文；反馈 = `{code}|{vote}|{comment}`。换掉任何内容校验即失败，
  一份 POW 只对一份内容有效。
- **难度声明在客户端**：`pow.difficulty` 是客户端实际求解的难度。服务端只要求
  `difficulty ≥ 配置最低值` 且哈希满足声明难度——报高难度只会让伪造更难，
  因此无需信任客户端之外的任何声明。用户主动提高难度 = 更高的可信度。
- **challenge 无状态**：HMAC 签名内含 scope/用户/过期时间，服务端不存签发记录。
  密钥由站点注入（本项目：从 `data/_secrets.json` 的 api_key 派生）。

## 2. 防重放（不记历史）

challenge 有效期短（默认 10 分钟）+ POW 绑定内容 ⇒ 重放只能原样重复同一份内容：

- **反馈类（幂等业务）**：每用户一条当前记录，upsert 覆盖。重放 = 无害的自我覆盖。
- **消息类（追加业务）**：插入前扫描最近 10 分钟内同用户同内容的消息，重复则拒绝。
  用的是消息本身的时间戳，不新增历史存储。

若未来业务对重复极度敏感（如转账），可在业务层自行加 nonce 去重表；
powbox 不强制。

## 3. 难度与耗时

难度单位 = 哈希前导零 bit 数，期望计算量 = 2^N 次哈希。
浏览器纯 JS SHA-256 约 0.5–2 MH/s（面板会实测算力并记忆，用于下次预估）。

| 难度(bit) | 期望哈希次数 | 约耗时@1MH/s |
|---|---|---|
| 16 | 6.5 万 | <0.1s |
| 18 | 26 万 | ~0.3s |
| 20（默认） | 105 万 | ~1s |
| 22 | 419 万 | ~4s |
| 24 | 1678 万 | ~17s |
| 26 | 6711 万 | ~1min |
| 28 | 2.7 亿 | ~4.5min |
| 30 | 10.7 亿 | ~18min |
| 32（默认上限） | 42.9 亿 | ~1.2h |
| 40 | 1.1 万亿 | ~13d |
| 48 | 281 万亿 | ~9y |
| 64（硬上限） | 1844 亿亿 | ~580k y |

合法范围为 8–64。本项目在「设置 → 防刷屏验证（POW）」配置 `_config.json` 的
`pow_difficulty`（最低难度）和 `pow_max_difficulty`（滑块上限，默认 32）；最低难度不能高于上限。

## 4. 模块接口

### 后端 `backend/powbox/`

```python
from powbox import pow as powbox_pow
from powbox import routes as powbox_routes

powbox_pow.init(
    secret_fn=lambda: ...,      # () -> str，HMAC 密钥来源（站点级秘密）
    difficulty_fn=lambda: ...,  # () -> int，当前最低难度
    max_difficulty_fn=lambda: ...,  # () -> int，前端滑块可选的最高难度
)
powbox_routes.init(
    get_current_user_fn=...,        # (Request) -> Optional[str]
    anonymous_identity_fn=...,      # (scope, Request, Response) -> Optional[str]
)
app.include_router(powbox_routes.router, prefix="/api/pow")
```

业务侧校验一行：

```python
try:
    difficulty = powbox_pow.verify_pow(req.pow, content_str, scope="xxx", username=user)
except powbox_pow.PowError as e:
    raise HTTPException(400, str(e))
```

### 前端 `frontend/src/powbox/`

```html
<PowPanel ref="powPanel" scope="xxx" />
```
```js
const pow = await powPanel.value.obtainPow(contentString)  // 取消/失败 throw
await api.submit({ ..., pow })
```

面板内置：POW 说明文案、站点最低要求与耗时预估（按实测算力校准）、
默认 0 bit 的难度滑块（用户必须手动拖到最低难度及以上才能提交，
实时显示倍数与耗时影响）、计算进度/速度/取消。计算中显示平均目标距离和鼓励阶段；
完成后按 `2^difficulty / 实际步数` 得出幸运倍率，分为天选、幸运、稳健、坚持四档，
并使用不同结果动画给出正向反馈。

复用到其它项目：整个 `powbox/` 目录拷走；后端替换两个 `init` 钩子；
前端仅需保证 `api.js` 里的 `API_PREFIX` 与后端挂载前缀一致。

## 5. 本项目的业务挂载

| 业务 | scope | 存储 | 接口 |
|---|---|---|---|
| 消息箱 | `message` | `data/_messages.json` | `GET/POST /api/messages`、`DELETE /api/messages/{id}`（admin） |
| 股票反馈 | `feedback` | `data/{code}/feedback.json` | `GET/POST/DELETE /api/stocks/{code}/feedback`、`DELETE .../feedback/all`（admin）、`DELETE .../feedback/{username}`（admin） |

权限：发消息始终需登录；反馈默认需登录（只读账号可以——中间件对 `/api/pow`、`/api/messages`、
`/api/stocks/*/feedback` 前缀放行了只读写）；消息 GET 端点内强制登录
（消息私密：admin 看全部，用户只看自己）；反馈 GET 跟随全局读权限。
反馈可见性由 `comments_visibility` 控制：`public` 时可见汇总和列表，`admin` 时仅管理员可见；
非管理员仍可提交并更新/撤回自己的反馈。

当本项目把 `comments_require_login` 设为 `false` 时，未登录访客可读取 POW 配置、获取
`scope=feedback` 的 challenge，并提交/撤回股票反馈；业务层会用 `anonymous_identity_fn`
签发或读取游客 Cookie（`guest:<随机 ID>`）。`scope=message` 不会获得匿名身份，消息箱继续要求登录。
