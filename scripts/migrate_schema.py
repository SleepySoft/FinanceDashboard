#!/usr/bin/env python3
"""
Migrate inconsistent stock metadata to canonical schema.

Run from FinanceDashboard root:
    python3 scripts/migrate_schema.py

What it fixes:
1. Top-level `dimensions` in state.json → moved to `tags`
2. Numeric dimension values (1, 0) → mapped to string values
3. Missing required fields → set defaults
4. Legacy string `notes` → converted to array
"""

import os, sys, json

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from main import _load_meta, _save_meta, REPORTS_DIR

VALID_DIMENSIONS = {"green", "yellow", "red", "none"}
DIMENSION_KEYS = ["quality", "valuation", "timing", "risk", "verdict"]
NUMERIC_MAP = {1: "green", 0: "none", -1: "red"}

def migrate_stock(code: str) -> bool:
    """Migrate a single stock. Returns True if changes were made."""
    try:
        meta = _load_meta(code)
    except Exception as e:
        print(f"  SKIP {code}: {e}")
        return False
    
    changed = False
    tags = meta.setdefault("tags", {})
    
    # 1. Migrate top-level dimensions to tags
    if "dimensions" in meta and isinstance(meta["dimensions"], dict):
        dims = meta["dimensions"]
        for key in DIMENSION_KEYS:
            if key in dims:
                val = dims[key]
                # Map numeric values
                if isinstance(val, (int, float)):
                    val = NUMERIC_MAP.get(val, "none")
                # Validate
                if val not in VALID_DIMENSIONS:
                    val = "none"
                # Only update if not already in tags
                if key not in tags or tags[key] == "none":
                    tags[key] = val
                    changed = True
        # Remove stale top-level dimensions
        del meta["dimensions"]
        changed = True
        print(f"  Migrated top-level dimensions → tags")
    
    # 2. Ensure tags has required fields
    if "overall" not in tags:
        tags["overall"] = "none"
        changed = True
    if "watchlist" not in tags:
        tags["watchlist"] = False
        changed = True
    
    # 3. Validate dimension values in tags
    for key in DIMENSION_KEYS:
        if key in tags:
            val = tags[key]
            if isinstance(val, (int, float)):
                tags[key] = NUMERIC_MAP.get(val, "none")
                changed = True
            elif val not in VALID_DIMENSIONS:
                tags[key] = "none"
                changed = True
    
    # 4. Ensure status exists
    if "status" not in meta:
        meta["status"] = "neutral"
        changed = True
    
    # 5. Fix legacy string notes
    if "notes" in meta and isinstance(meta["notes"], str):
        meta["notes"] = []
        changed = True
    
    if changed:
        _save_meta(code, meta)
        print(f"  UPDATED {code}")
    else:
        print(f"  OK {code}")
    
    return changed


def main():
    print(f"Scanning {REPORTS_DIR}...")
    updated = 0
    total = 0
    
    for entry in sorted(os.listdir(REPORTS_DIR)):
        if entry.startswith("_"):
            continue
        meta_path = os.path.join(REPORTS_DIR, entry, "meta.json")
        if not os.path.exists(meta_path):
            continue
        
        total += 1
        print(f"\n[{total}] {entry}:")
        if migrate_stock(entry):
            updated += 1
    
    print(f"\n{'='*50}")
    print(f"Total stocks scanned: {total}")
    print(f"Stocks updated: {updated}")
    print(f"Done.")


if __name__ == "__main__":
    main()
