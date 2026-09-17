#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据文件校验：用 schemas/*.schema.json 检查 data/ 下所有会被后端载入的 JSON 文件。

用法：
    python scripts/validate_data.py           # 校验全部，出错时退出码 1
    python scripts/validate_data.py -v        # 同时列出每个通过的文件
    python scripts/validate_data.py --strict  # 发现「无对应 schema 的数据文件」也视为失败

规则：
- schemas/ 下每个 {文件名}.schema.json 对应 data/ 下的同名 JSON 文件：
  - 顶层文件：data/_xxx.json        ↔ schemas/_xxx.schema.json
  - 个股文件：data/{code}/xxx.json  ↔ schemas/xxx.schema.json
- 顶层文件缺少对应 schema 视为错误（强制为每个新顶层文件补 schema）；
- 个股文件只校验存在 schema 的种类，未知种类给警告（--strict 下视为错误）；
- 校验器为纯 stdlib，支持 JSON Schema 子集：type(含联合)/required/properties/items/enum/pattern/additionalProperties。

改了任何读写数据文件的代码、或手工/批量修改过 data/ 内容后，必须运行本脚本（见 AGENTS.md）。
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
SCHEMA_DIR = os.path.join(ROOT, "schemas")

_TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}


def _type_name(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, dict):
        return "object"
    if isinstance(v, list):
        return "array"
    return "string"


def _is_type(value, t):
    py = _TYPE_MAP[t]
    # bool 是 int 的子类，但 JSON Schema 里 boolean/number/integer 互不相容
    if t in ("number", "integer") and isinstance(value, bool):
        return False
    if t == "integer" and isinstance(value, float) and not value.is_integer():
        return False
    return isinstance(value, py)


def validate(value, schema, path, errors):
    t = schema.get("type")
    if t:
        types = t if isinstance(t, list) else [t]
        if not any(_is_type(value, tt) for tt in types):
            errors.append(f"{path}: 期望类型 {'/'.join(types)}，实际 {_type_name(value)}")
            return
    if isinstance(value, dict):
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path}: 缺少必填字段 '{req}'")
        props = schema.get("properties", {})
        addl = schema.get("additionalProperties")
        for k, v in value.items():
            if k in props:
                validate(v, props[k], f"{path}.{k}", errors)
            elif isinstance(addl, dict):
                validate(v, addl, f"{path}.{k}", errors)
    elif isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(value):
                validate(item, item_schema, f"{path}[{i}]", errors)
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: 值 {value!r} 不在枚举 {schema['enum']}")
    if "pattern" in schema and isinstance(value, str) and not re.match(schema["pattern"], value):
        errors.append(f"{path}: 值 {value!r} 不匹配 pattern {schema['pattern']}")


def _load_schema(name):
    path = os.path.join(SCHEMA_DIR, f"{name}.schema.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    strict = "--strict" in sys.argv
    total, passed, failed, warned = 0, 0, 0, 0

    def report(path, errors):
        nonlocal passed, failed
        if errors:
            failed += 1
            print(f"FAIL {os.path.relpath(path, ROOT)}")
            for e in errors[:10]:
                print(f"     - {e}")
            if len(errors) > 10:
                print(f"     ... 还有 {len(errors) - 10} 个错误")
        else:
            passed += 1
            if verbose:
                print(f"OK   {os.path.relpath(path, ROOT)}")

    # ── 顶层文件：data/_*.json ──
    for path in sorted(glob.glob(os.path.join(DATA_DIR, "_*.json"))):
        name = os.path.basename(path)[:-5]  # 去掉 .json
        schema = _load_schema(name)
        total += 1
        if schema is None:
            failed += 1
            print(f"FAIL {os.path.relpath(path, ROOT)}: 缺少对应 schema schemas/{name}.schema.json")
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            failed += 1
            print(f"FAIL {os.path.relpath(path, ROOT)}: JSON 解析失败 {type(e).__name__}: {e}")
            continue
        errors = []
        validate(data, schema, "$", errors)
        report(path, errors)

    # ── 个股文件：data/{code}/*.json ──
    for stock_dir in sorted(glob.glob(os.path.join(DATA_DIR, "*"))):
        if not os.path.isdir(stock_dir):
            continue
        code = os.path.basename(stock_dir)
        if code.startswith("_"):
            continue
        for path in sorted(glob.glob(os.path.join(stock_dir, "*.json"))):
            name = os.path.basename(path)[:-5]
            schema = _load_schema(name)
            if schema is None:
                warned += 1
                print(f"WARN {os.path.relpath(path, ROOT)}: 无对应 schema（跳过校验）")
                continue
            total += 1
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                failed += 1
                print(f"FAIL {os.path.relpath(path, ROOT)}: JSON 解析失败 {type(e).__name__}: {e}")
                continue
            errors = []
            validate(data, schema, "$", errors)
            report(path, errors)

    print(f"\n校验 {total} 个文件：{passed} 通过，{failed} 失败，{warned} 警告")
    if failed or (strict and warned):
        sys.exit(1)


if __name__ == "__main__":
    main()
