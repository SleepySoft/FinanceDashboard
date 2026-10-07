import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import reminders


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.code = "000001.SZ"
        stock_dir = self.data_dir / self.code
        stock_dir.mkdir()
        (stock_dir / "meta.json").write_text(
            json.dumps({"code": self.code, "name": "测试公司"}), encoding="utf-8"
        )
        self.patcher = patch.object(reminders, "DATA_DIR", str(self.data_dir))
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def future(self, days=1):
        return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

    def test_agent_retry_replaces_only_pending_proposals(self):
        first = [reminders.AgentReminderInput(action="查看财报", remind_at=self.future())]
        reminders.replace_agent_proposals(self.code, "task-1", first, ["fundamental_20261007"])
        stored = reminders._load(self.code)
        stored["items"][0]["state"] = "active"
        reminders._save(self.code, stored)

        second = [reminders.AgentReminderInput(action="复核现金流", remind_at=self.future(2))]
        reminders.replace_agent_proposals(self.code, "task-1", second, ["fundamental_20261008"])
        result = reminders._load(self.code)["items"]

        self.assertEqual(len(result), 2)
        self.assertEqual(sum(item["state"] == "active" for item in result), 1)
        self.assertEqual(sum(item["action"] == "复核现金流" for item in result), 1)

    def test_global_aggregation_includes_stock_context(self):
        reminders.replace_agent_proposals(
            self.code, "task-2",
            [reminders.AgentReminderInput(action="检查公告", remind_at=self.future())],
            [],
        )
        payload = reminders.list_all_reminders(scope="proposed")
        self.assertEqual(payload["counts"]["proposed"], 1)
        self.assertEqual(payload["items"][0]["stock_name"], "测试公司")
        self.assertEqual(payload["items"][0]["code"], self.code)


if __name__ == "__main__":
    unittest.main()
