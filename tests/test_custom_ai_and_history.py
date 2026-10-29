# -*- coding: utf-8 -*-
"""测试自定义云端 API URL、本地 Ollama 端点探测以及 SQLite 历史 API"""

import unittest
from unittest.mock import patch, Mock
from core.deepseek_client import generate_from_evidence
from web.app import app
from fastapi.testclient import TestClient

client = TestClient(app)


class CustomAiAndHistoryTests(unittest.TestCase):

    @patch('core.deepseek_client.requests.post')
    def test_custom_api_url_and_custom_model(self, mock_post):
        mock_post.return_value = Mock(status_code=200)
        mock_post.return_value.json.return_value = {
            'choices': [{
                'finish_reason': 'stop',
                'message': {'content': '这是自定义端点回答。[1]'}
            }]
        }
        res = generate_from_evidence(
            query="图书馆在哪里？",
            chunks=[{"text": "晴川图书馆位于中心湖畔。"}],
            citations=[{"index": 1, "evidence_text": "晴川图书馆位于中心湖畔。"}],
            api_key="test-custom-key",
            model="custom-qwen-max",
            api_url="https://api.siliconflow.cn/v1"
        )
        self.assertEqual(res.status, "success")
        self.assertEqual(res.model, "custom-qwen-max")
        self.assertEqual(res.content, "这是自定义端点回答。[1]")
        
        # 验证 endpoint 自动补全了 /chat/completions
        endpoint_called = mock_post.call_args[0][0]
        self.assertEqual(endpoint_called, "https://api.siliconflow.cn/v1/chat/completions")

    @patch('requests.get')
    def test_test_ollama_success(self, mock_get):
        mock_get.return_value = Mock(status_code=200)
        mock_get.return_value.json.return_value = {
            "models": [{"name": "deepseek-r1:latest"}, {"name": "qwen2.5:7b"}]
        }
        resp = client.post("/api/test_ollama", json={
            "ollama_url": "http://localhost:11434",
            "model": "deepseek-r1:latest"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertIn("已检测到模型", data["message"])

    @patch('requests.get')
    def test_test_ollama_model_missing(self, mock_get):
        mock_get.return_value = Mock(status_code=200)
        mock_get.return_value.json.return_value = {
            "models": [{"name": "llama3:latest"}]
        }
        resp = client.post("/api/test_ollama", json={
            "ollama_url": "http://localhost:11434",
            "model": "deepseek-r1:latest"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["ok"])
        self.assertIn("未找到模型", data["message"])

    def test_history_endpoints(self):
        # 1. 验证获取历史
        resp = client.get("/api/history?limit=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total", data)
        self.assertIn("history", data)
        self.assertIsInstance(data["history"], list)

        # 2. 验证清空历史
        resp_del = client.delete("/api/history?session_id=test_non_existent")
        self.assertEqual(resp_del.status_code, 200)
        data_del = resp_del.json()
        self.assertEqual(data_del["status"], "success")
