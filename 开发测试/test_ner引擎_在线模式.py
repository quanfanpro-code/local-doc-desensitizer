"""NER 引擎在线模式单元测试

测试 ner引擎.py 的改造：
- _读取llm配置：根据 llm_mode 返回本地/在线配置
- _调用llm：在线模式请求头带 Authorization，本地模式不带
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))

from 主程序.ner引擎 import NER引擎


class Test读取llm配置(unittest.TestCase):
    """根据 settings.json 的 llm_mode 返回本地或在线配置"""

    @patch('主程序.mineru桥接.读取用户设置')
    @patch('主程序.mineru桥接.探测lm_studio地址')
    def test_本地模式(self, mock_探测地址, mock_读取设置):
        mock_读取设置.return_value = {"llm_mode": "local", "lm_port": 1234}
        mock_探测地址.return_value = "http://127.0.0.1:1234/v1"

        引擎 = NER引擎()
        配置 = 引擎._读取llm配置()

        self.assertEqual(配置["mode"], "local")
        self.assertEqual(配置["api_base"], "http://127.0.0.1:1234/v1")
        self.assertEqual(配置["api_key"], "")
        self.assertEqual(配置["model"], "")

    @patch('主程序.mineru桥接.读取用户设置')
    def test_在线模式(self, mock_读取设置):
        mock_读取设置.return_value = {
            "llm_mode": "online",
            "online_api_base": "http://119.6.186.168:40040",
            "online_api_key": "sk-xxx",
            "online_model": "Qwen3-32B-0709",
        }

        引擎 = NER引擎()
        配置 = 引擎._读取llm配置()

        self.assertEqual(配置["mode"], "online")
        self.assertEqual(配置["api_base"], "http://119.6.186.168:40040/v1")
        self.assertEqual(配置["api_key"], "sk-xxx")
        self.assertEqual(配置["model"], "Qwen3-32B-0709")

    @patch('主程序.mineru桥接.读取用户设置')
    @patch('主程序.mineru桥接.探测lm_studio地址')
    def test_旧版无llm_mode字段_默认本地(self, mock_探测地址, mock_读取设置):
        """旧版 settings.json 没有 llm_mode 字段，默认本地模式（向后兼容）"""
        mock_读取设置.return_value = {"lm_port": 1234}
        mock_探测地址.return_value = "http://127.0.0.1:1234/v1"

        引擎 = NER引擎()
        配置 = 引擎._读取llm配置()

        self.assertEqual(配置["mode"], "local")

    @patch('主程序.mineru桥接.读取用户设置')
    def test_在线模式完整地址带chatcompletions_截断(self, mock_读取设置):
        """用户从 curl 复制完整地址，_读取llm配置 应返回截断后的地址"""
        mock_读取设置.return_value = {
            "llm_mode": "online",
            "online_api_base": "http://119.6.186.168:40040/v1/chat/completions",
            "online_api_key": "sk-xxx",
            "online_model": "Qwen3-32B-0709",
        }

        引擎 = NER引擎()
        配置 = 引擎._读取llm配置()

        self.assertEqual(配置["api_base"], "http://119.6.186.168:40040/v1")


class Test调用llm请求头(unittest.TestCase):
    """在线模式请求头带 Authorization，本地模式不带"""

    @patch('主程序.mineru桥接.读取用户设置')
    @patch('requests.post')
    def test_在线模式带Authorization头(self, mock_post, mock_读取设置):
        mock_读取设置.return_value = {
            "llm_mode": "online",
            "online_api_base": "http://119.6.186.168:40040",
            "online_api_key": "sk-xxx",
            "online_model": "Qwen3-32B-0709",
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "[]"}, "finish_reason": "stop"}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        引擎 = NER引擎()
        引擎._可用 = True
        引擎._MODEL = "Qwen3-32B-0709"
        引擎._调用llm("测试文本")

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertIn("headers", kwargs)
        self.assertIn("Authorization", kwargs["headers"])
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sk-xxx")

    @patch('主程序.mineru桥接.读取用户设置')
    @patch('requests.post')
    def test_本地模式不带Authorization头(self, mock_post, mock_读取设置):
        """本地模式向后兼容：请求头不含 Authorization"""
        mock_读取设置.return_value = {"llm_mode": "local", "lm_port": 1234}
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "[]"}, "finish_reason": "stop"}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        引擎 = NER引擎()
        引擎._可用 = True
        引擎._MODEL = "local-model"
        引擎._调用llm("测试文本")

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        头 = kwargs.get("headers", {})
        self.assertNotIn("Authorization", 头)


if __name__ == "__main__":
    unittest.main()
