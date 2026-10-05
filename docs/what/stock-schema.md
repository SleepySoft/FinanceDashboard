# Stock Metadata Schema

## Overview

This document defines the canonical data schema for stock metadata in FinanceDashboard.
All stock data is stored under `data/{code}/` with the following files:

- `meta.json` — static fields (code, name, sector, type, added_at)
- `state.json` — mutable fields (tags, status, dimensions, price_marks, notes, etc.)
- `reports/` — analysis report markdown files
- `notes.md` — free-form notes

## Schema Definition

### meta.json (Static)

```json
{
  "code": "688018.SH",
  "name": "乐鑫科技",
  "sector": "半导体/物联网芯片",
  "type": "stock",
  "added_at": "2026-07-23T05:12:52+00:00"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| code | string | yes | Stock code with exchange suffix (e.g., 688018.SH) |
| name | string | yes | Company name |
| sector | string | no | Industry sector |
| type | string | no | Asset type (default: "stock") |
| added_at | string | no | ISO 8601 timestamp when added |

### state.json (Mutable)

```json
{
  "tags": {
    "overall": "yellow",
    "watchlist": false,
    "quality": "green",
    "valuation": "red",
    "timing": "yellow",
    "risk": "none",
    "verdict": "yellow"
  },
  "status": "neutral",
  "price_marks": [],
  "notes": [],
  "record_prices": {
    "notes": {"2026-09-03 12:34": 12.34},
    "reports": {"technical_20260903": 12.34}
  },
  "holdings": null
}
```

`record_prices` 是内部快照索引：写笔记时以笔记时间戳为键，Agent 完成分析时以报告文件名主干为键，记录当时 `_dashboard.json` 中可用的正数价格。取价失败不会阻止保存；旧记录或无快照记录在时间线显示 `--`。

#### tags (Evaluation Dimensions)

**Canonical location for all dimension evaluations.** The `_normalize_dimensions()` function reads dimensions exclusively from `tags`.

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| overall | string | "green", "yellow", "red", "none" | Overall investment rating |
| watchlist | boolean | true, false | Whether on watchlist |
| quality | string | "green", "yellow", "red", "none" | Business quality (moat) |
| valuation | string | "green", "yellow", "red", "none" | Valuation attractiveness |
| timing | string | "green", "yellow", "red", "none" | Entry timing |
| risk | string | "green", "yellow", "red", "none" | Risk level |
| verdict | string | "green", "yellow", "red", "none" | Final verdict |
| unread | boolean | true, false | 未读标记：分析完成（agent complete）后自动置 true，用户打开个股面板/详情页后自动清除 |

#### status

| Value | Label |
|-------|-------|
| tracking | 跟踪中 |
| bullish | 看好 |
| neutral | 观望 |
| waiting | 伺机 |
| avoid | 回避 |
| no_interest | 无兴趣 |
| blacklist | 黑名单 |
| archive | 归档 |
| core_position | 底仓备选 |

#### price_marks

```json
[
  {
    "id": "mark-001",
    "label": "目标买入",
    "price": 100.0,
    "type": "target_buy",
    "created_at": "2026-07-23T10:00:00+00:00"
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique mark ID（缺失时后端按内容哈希生成） |
| label | string | 兼容显示字段；新写入的语义名称由类型注册表决定，自由说明使用 `note` |
| price | number | Mark price |
| type | string | `_config.json.price_level_types` 中 `family=analysis` 的注册 key |
| source | string | `manual`（用户手工，默认）/ `agent`（AI 技术面标记：阻力位/支撑位/筹码密集区等，经 `PUT /api/agent/stocks/{code}/price-marks` 整体替换，手工标记不受影响） |
| note | string | 可选备注（AI 标记的理由等） |
| created_at | string | ISO 8601 timestamp |

兼容存储中的 `price_marks` 对应统一价格水位模型的 `family=analysis`。新增字段：

| Field | Type | Description |
|-------|------|-------------|
| state | string | proposed / active / retired / invalidated / expired；旧数据缺失视为 active |
| valid_from | string/null | 可选生效时间 |
| valid_until | string/null | 可选有效期；读取时超过日期表现为 expired |
| updated_at | string | 最近更新时间 |

统一读取接口 `GET /api/stocks/{code}/price-levels` 同时聚合：

- `family=analysis`：来自 `state.json.price_marks`；
- `family=plan`：来自 `ladder.json.levels`，扩展字段 `plan={side, qty}`；
- `family=fact`：从 `holdings.json` 投影最后买入、最后卖出和持仓成本，不另行存储。

类型语义来自 `_config.json.price_level_types` 注册表，而不是单条水位的自由文本 `label`。历史 label 与标准名称不同时，统一接口将其作为兼容说明返回在 `note` 中。
AI 经 `PUT /api/agent/stocks/{code}/price-marks` 写入的新增分析水位必须为 `state=proposed`；用户接受后才转为 `active`。成交事实只读，不能复制成手工标记。

### API Response Format

The `/api/stocks/{code}` and `/api/dashboard` endpoints return stock objects with the following structure:

```json
{
  "code": "688018.SH",
  "name": "乐鑫科技",
  "sector": "半导体/物联网芯片",
  "tags": { "overall": "yellow", "watchlist": false },
  "status": "neutral",
  "dimensions": {
    "quality": "green",
    "valuation": "red",
    "timing": "yellow",
    "risk": "none",
    "verdict": "yellow"
  },
  "watchlist": false,
  "overall": "yellow",
  "price_marks": [],
  "report_count": 2,
  "last_analysis": "2026-07-23",
  "last_price": 105.11,
  "change_pct": -6.54
}
```

**Important**: The `dimensions` field in API responses is **computed** from `tags` via `_normalize_dimensions()`. It is NOT stored in state.json. Do NOT write dimensions to a top-level `dimensions` field in state.json.

## Migration Notes

### Legacy Formats

Some older entries may have dimensions stored in:
- `tags.moat` → maps to `tags.quality`
- `tags.fundamental` → maps to `tags.quality`
- `tags.technical` → maps to `tags.timing`
- Top-level `dimensions` field in state.json → should be migrated to `tags`

### Migration Script

Run the following to fix inconsistent entries:

```python
import os, json
from backend.main import _load_meta, _save_meta, REPORTS_DIR

for entry in os.listdir(REPORTS_DIR):
    if entry.startswith("_"):
        continue
    meta_path = os.path.join(REPORTS_DIR, entry, "meta.json")
    if not os.path.exists(meta_path):
        continue
    try:
        meta = _load_meta(entry)
    except Exception:
        continue
    
    # Migrate top-level dimensions to tags
    if "dimensions" in meta and isinstance(meta["dimensions"], dict):
        dims = meta["dimensions"]
        for key in ["quality", "valuation", "timing", "risk", "verdict"]:
            if key in dims and dims[key]:
                meta["tags"][key] = dims[key]
        # Remove stale top-level dimensions
        del meta["dimensions"]
        _save_meta(entry, meta)
        print(f"Migrated {entry}")
```

## Validation Rules

1. `code` must include exchange suffix (`.SH`, `.SZ`, `.BJ`)
2. `tags` must contain at minimum: `overall` and `watchlist`
3. Dimension values must be one of: "green", "yellow", "red", "none"
4. `status` must be one of the valid status values
5. `notes` must always be an array (legacy string format is auto-converted)

## Backend Implementation Notes

### _normalize_dimensions()

This function is the **single source of truth** for dimension extraction:

```python
def _normalize_dimensions(meta: dict) -> dict:
    tags = meta.get("tags", {})
    dims = {}
    
    # New format: direct dimension fields in tags
    if "quality" in tags:
        dims["quality"] = tags["quality"]
    else:
        # Legacy fallback
        dims["quality"] = tags.get("moat") or tags.get("fundamental") or "none"
    
    dims["valuation"] = tags.get("valuation", "none")
    
    if "timing" in tags:
        dims["timing"] = tags["timing"]
    else:
        dims["timing"] = tags.get("technical", "none")
    
    dims["risk"] = tags.get("risk", "none")
    
    if "verdict" in tags:
        dims["verdict"] = tags["verdict"]
    else:
        dims["verdict"] = tags.get("overall", "none")
    
    return dims
```

**Never** modify this function to read from top-level `dimensions`. Instead, migrate data to `tags`.
