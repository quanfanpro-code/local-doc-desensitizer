"""X2：扩展请求参数 chat_template_kwargs 的兼容性处理。

- 默认附带扩展参数（保持已验证的 vLLM 配置行为）
- 服务端明确拒绝该参数（400 且错误文本点名 chat_template_kwargs）时，去掉后重试
- 普通 400、鉴权失败等其他错误保留各自原因，不盲目重试
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

from 主程序.ner引擎 import NER引擎
from 主程序.文档识别 import 请求模型


def _响应(状态码=200, 消息=None, 错误文本=""):
    r = MagicMock()
    r.status_code = 状态码
    r.text = 错误文本
    if 状态码 == 200:
        r.json.return_value = {
            "choices": [{"message": 消息 or {"content": "{}"}, "finish_reason": "stop"}],
            "usage": {},
        }
        r.raise_for_status = MagicMock()
    else:
        e = requests.HTTPError(f"{状态码} 错误")
        e.response = r
        r.raise_for_status = MagicMock(side_effect=e)
    return r


class Test扩展参数兼容(unittest.TestCase):

    def _引擎(self):
        引擎 = NER引擎()
        引擎._读取llm配置 = lambda: {
            "mode": "online", "api_base": "http://test/v1",
            "api_key": "sk-x", "model": "m",
        }
        return 引擎

    @patch("requests.post")
    def test_支持扩展参数的后端保持附带(self, mock_post):
        """默认行为不变：请求负载含 chat_template_kwargs"""
        mock_post.return_value = _响应(200)
        引擎 = self._引擎()
        请求模型(引擎, [{"role": "user", "content": "hi"}])
        负载 = mock_post.call_args.kwargs["json"]
        self.assertIn("chat_template_kwargs", 负载)
        self.assertEqual(负载["chat_template_kwargs"], {"enable_thinking": False})

    @patch("requests.post")
    def test_明确拒绝扩展参数时去掉后重试成功(self, mock_post):
        """400 且错误文本点名 chat_template_kwargs：去掉该参数重试，最终成功"""
        mock_post.side_effect = [
            _响应(400, 错误文本='{"error":{"message":"Unrecognized request argument supplied: chat_template_kwargs"}}'),
            _响应(200),
        ]
        引擎 = self._引擎()
        返回 = 请求模型(引擎, [{"role": "user", "content": "hi"}])
        self.assertEqual(mock_post.call_count, 2)
        第一次负载 = mock_post.call_args_list[0].kwargs["json"]
        第二次负载 = mock_post.call_args_list[1].kwargs["json"]
        self.assertIn("chat_template_kwargs", 第一次负载)
        self.assertNotIn("chat_template_kwargs", 第二次负载)
        self.assertEqual(返回["content"], "{}")

    @patch("requests.post")
    def test_确认拒绝后同引擎后续请求不再附带(self, mock_post):
        """同一引擎已确认后端不支持后，后续请求直接不带扩展参数"""
        mock_post.side_effect = [
            _响应(400, 错误文本="chat_template_kwargs is not supported"),
            _响应(200),
            _响应(200),
        ]
        引擎 = self._引擎()
        请求模型(引擎, [{"role": "user", "content": "hi"}])
        请求模型(引擎, [{"role": "user", "content": "hi2"}])
        self.assertEqual(mock_post.call_count, 3)
        第三次负载 = mock_post.call_args_list[2].kwargs["json"]
        self.assertNotIn("chat_template_kwargs", 第三次负载)

    @patch("requests.post")
    def test_普通400保留原因不盲目重试(self, mock_post):
        """错误文本未点名扩展参数的 400：原样抛出，不重试"""
        mock_post.return_value = _响应(400, 错误文本='{"error":{"message":"max_tokens is too large"}}')
        引擎 = self._引擎()
        with self.assertRaises(requests.HTTPError):
            请求模型(引擎, [{"role": "user", "content": "hi"}])
        self.assertEqual(mock_post.call_count, 1)

    @patch("requests.post")
    def test_鉴权失败不重试(self, mock_post):
        """401 鉴权错误：原样抛出，不重试"""
        mock_post.return_value = _响应(401, 错误文本="invalid api key")
        引擎 = self._引擎()
        with self.assertRaises(requests.HTTPError):
            请求模型(引擎, [{"role": "user", "content": "hi"}])
        self.assertEqual(mock_post.call_count, 1)


if __name__ == "__main__":
    unittest.main()
