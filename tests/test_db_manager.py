# -*- coding: utf-8 -*-
"""SQLite 数据库管理模块测试"""

import unittest
import tempfile
import os
import json
from pathlib import Path

from core.db_manager import (
    init_db,
    log_chat_turn,
    get_recent_history,
    clear_chat_history,
    get_db_connection
)


class TestDbManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_chat.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_init_db_creates_table(self):
        init_db(self.db_path)
        self.assertTrue(self.db_path.exists())
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_history';")
            self.assertIsNotNone(cursor.fetchone())

    def test_log_and_query_history(self):
        init_db(self.db_path)
        record_id = log_chat_turn(
            user_query="图书馆几点关门？",
            rewritten_query="图书馆 闭馆时间",
            mode="bge",
            answer="开闭馆时间为周一至周日 07:30 — 22:00 [1]",
            llm_provider="BGE 稠密语义 · 本地事实证据抽取",
            latency_ms=125.4,
            refused=False,
            citations=[{"index": 1, "title": "开闭馆时间"}],
            session_id="session_1",
            db_path=self.db_path
        )
        self.assertGreater(record_id, 0)

        history = get_recent_history(limit=10, session_id="session_1", db_path=self.db_path)
        self.assertEqual(len(history), 1)
        item = history[0]
        self.assertEqual(item["user_query"], "图书馆几点关门？")
        self.assertEqual(item["mode"], "bge")
        self.assertEqual(item["llm_provider"], "BGE 稠密语义 · 本地事实证据抽取")
        self.assertEqual(item["refused"], 0)
        self.assertIn("07:30", item["answer"])
        citations = json.loads(item["citations_json"])
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]["title"], "开闭馆时间")

    def test_clear_history(self):
        init_db(self.db_path)
        log_chat_turn("问1", "改写1", "hybrid", "答1", "本地", 10.0, db_path=self.db_path)
        log_chat_turn("问2", "改写2", "hybrid", "答2", "本地", 12.0, db_path=self.db_path)
        self.assertEqual(len(get_recent_history(limit=10, db_path=self.db_path)), 2)

        deleted = clear_chat_history(db_path=self.db_path)
        self.assertEqual(deleted, 2)
        self.assertEqual(len(get_recent_history(limit=10, db_path=self.db_path)), 0)


if __name__ == '__main__':
    unittest.main()
