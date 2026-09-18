"""Y5：在线 API / LM Studio 状态探测必须保留错误原因，供界面分类提示。

- 401/403 → 密钥问题
- 404 → 地址问题
- 超时 → 超时
- 连接失败 → 无法连接
- 密钥为空 → 直接提示
- 模型列表能取到但冒烟失败 → 模型已加载=False 且带原因
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

from 主程序.mineru桥接 import 探测在线api状态, 探测lm_studio状态


def _异常响应(状态码):
    r = MagicMock()
    r.status_code = 状态码
    e = requests.HTTPError(f"{状态码} 错误")
    e.response = r
    r.raise_for_status = MagicMock(side_effect=e)
    return r


class Test在线api探测错误原因(unittest.TestCase):

    @patch("requests.get")
    def test_401提示密钥问题(self, mock_get):
        mock_get.return_value = _异常响应(401)
        状态 = 探测在线api状态("http://test/v1", "sk-bad", "m")
        self.assertFalse(状态["已启动"])
        self.assertIn("密钥", 状态["错误原因"])
        self.assertIn("401", 状态["错误原因"])

    @patch("requests.get")
    def test_404提示地址问题(self, mock_get):
        mock_get.return_value = _异常响应(404)
        状态 = 探测在线api状态("http://test/v1", "sk-x", "m")
        self.assertFalse(状态["已启动"])
        self.assertIn("地址", 状态["错误原因"])

    @patch("requests.get")
    def test_超时提示超时(self, mock_get):
        mock_get.side_effect = requests.Timeout("超时")
        状态 = 探测在线api状态("http://test/v1", "sk-x", "m")
        self.assertFalse(状态["已启动"])
        self.assertIn("超时", 状态["错误原因"])

    @patch("requests.get")
    def test_连接失败提示无法连接(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("拒绝连接")
        状态 = 探测在线api状态("http://test/v1", "sk-x", "m")
        self.assertFalse(状态["已启动"])
        self.assertIn("无法连接", 状态["错误原因"])

    def test_密钥为空直接提示(self):
        状态 = 探测在线api状态("http://test/v1", "", "m")
        self.assertFalse(状态["已启动"])
        self.assertIn("密钥", 状态["错误原因"])

    @patch("requests.post")
    @patch("requests.get")
    def test_冒烟失败保留原因(self, mock_get, mock_post):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"data": [{"id": "别的模型"}]}),
            raise_for_status=MagicMock(),
        )
        mock_post.return_value = _异常响应(400)
        状态 = 探测在线api状态("http://test/v1", "sk-x", "m")
        self.assertTrue(状态["已启动"])
        self.assertFalse(状态["模型已加载"])
        self.assertTrue(状态["错误原因"])


class TestLMStudio探测错误原因(unittest.TestCase):

    @patch("requests.get")
    def test_连接失败保留原因(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("拒绝连接")
        状态 = 探测lm_studio状态()
        self.assertFalse(状态["已启动"])
        self.assertTrue(状态["错误原因"])


if __name__ == "__main__":
    unittest.main()
