import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ladder
import price_levels


class PriceLevelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.code = "000001.SZ"
        stock_dir = self.data_dir / self.code
        stock_dir.mkdir()
        (stock_dir / "meta.json").write_text(
            json.dumps({"code": self.code, "name": "测试"}), encoding="utf-8"
        )
        (stock_dir / "state.json").write_text(
            json.dumps({
                "price_marks": [{
                    "id": "m1", "label": "旧标签", "price": 10,
                    "type": "support", "source": "agent", "state": "proposed",
                }]
            }), encoding="utf-8"
        )
        (stock_dir / "ladder.json").write_text(
            json.dumps({
                "levels": [{
                    "id": "l1", "side": "sell", "price": 12, "qty": 100,
                    "source": "manual", "enabled": True, "type": "take_profit",
                }]
            }), encoding="utf-8"
        )
        (stock_dir / "holdings.json").write_text(
            json.dumps({
                "trades": [{"id": "t1", "type": "buy", "price": 9.5}],
                "summary": {"avg_cost": 9.5, "total_quantity": 100},
            }), encoding="utf-8"
        )
        self.dashboard = self.data_dir / "_dashboard.json"
        self.dashboard.write_text(
            json.dumps({"prices": {self.code: {"price": 10.5}}}), encoding="utf-8"
        )
        self.patchers = [
            patch.object(price_levels, "DATA_DIR", str(self.data_dir)),
            patch.object(ladder, "DATA_DIR", str(self.data_dir)),
            patch.object(ladder, "DASHBOARD_FILE", str(self.dashboard)),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tmp.cleanup()

    def test_aggregates_analysis_plan_and_fact_levels(self):
        payload = price_levels.list_price_levels(self.code)
        levels = {item["id"]: item for item in payload["levels"]}

        self.assertEqual(levels["analysis:m1"]["label"], "支撑位")
        self.assertEqual(levels["analysis:m1"]["state"], "proposed")
        self.assertEqual(levels["plan:l1"]["plan"], {"side": "sell", "qty": 100})
        self.assertEqual(levels["fact:last_buy"]["price"], 9.5)
        self.assertEqual(levels["fact:average_cost"]["price"], 9.5)

    def test_unified_create_and_update_routes_to_existing_stores(self):
        price_levels.create_price_level(
            self.code,
            price_levels.PriceLevelCreate(
                family="analysis", type="resistance", price=11, note="平台高点"
            ),
        )
        created = price_levels.create_price_level(
            self.code,
            price_levels.PriceLevelCreate(
                family="plan", type="add", price=9, qty=200
            ),
        )
        plan = next(item for item in created["levels"] if item["type"] == "add")
        updated = price_levels.update_price_level(
            self.code,
            plan["id"],
            price_levels.PriceLevelPatch(state="retired"),
        )
        changed = next(item for item in updated["levels"] if item["id"] == plan["id"])

        self.assertEqual(changed["state"], "retired")
        self.assertEqual(changed["plan"]["qty"], 200)
        state = json.loads((self.data_dir / self.code / "state.json").read_text(encoding="utf-8"))
        self.assertTrue(any(item["type"] == "resistance" for item in state["price_marks"]))

    def test_fact_levels_are_read_only(self):
        with self.assertRaisesRegex(Exception, "事实水位"):
            price_levels.delete_price_level(self.code, "fact:last_buy")


if __name__ == "__main__":
    unittest.main()
