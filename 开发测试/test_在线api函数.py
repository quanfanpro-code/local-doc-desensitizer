"""在线 API 函数单元测试

测试 mineru桥接.py 新增的3个函数：
- 规范化在线api地址（地址智能规范化）
- 获取在线api模型列表（GET /v1/models 带 Authorization）
- 探测在线api状态（连通性检测）
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))

from 主程序.mineru桥接 import (
    规范化在线api地址,
    获取在线api模型列表,
    探测在线api状态,
)


class Test规范化在线api地址(unittest.TestCase):
    """地址智能规范化：正则 r'^(https?://.*?/v1)' 非贪婪提取到 /v1 为止"""

    def test_只填到端口_补v1(self):
        self.assertEqual(
            规范化在线api地址("http://119.6.186.168:40040"),
            "http://119.6.186.168:40040/v1",
        )

    def test_已含v1_不补(self):
        self.assertEqual(
            规范化在线api地址("http://119.6.186.168:40040/v1"),
            "http://119.6.186.168:40040/v1",
        )

    def test_v1带尾斜杠_去斜杠不补(self):
        self.assertEqual(
            规范化在线api地址("http://119.6.186.168:40040/v1/"),
            "http://119.6.186.168:40040/v1",
        )

    def test_完整地址含chatcompletions_截断(self):
        """用户从 curl 直接复制完整地址，应截断到 /v1"""
        self.assertEqual(
            规范化在线api地址("http://119.6.186.168:40040/v1/chat/completions"),
            "http://119.6.186.168:40040/v1",
        )

    def test_https保留协议(self):
        self.assertEqual(
            规范化在线api地址("https://api.openai.com"),
            "https://api.openai.com/v1",
        )

    def test_无协议头_补https(self):
        self.assertEqual(
            规范化在线api地址("api.openai.com"),
            "https://api.openai.com/v1",
        )

    def test_空字符串_返回空(self):
        self.assertEqual(规范化在线api地址(""), "")

    def test_去除首尾空白(self):
        self.assertEqual(
            规范化在线api地址("  http://119.6.186.168:40040  "),
            "http://119.6.186.168:40040/v1",
        )

    def test_通义千问compatiblemode_补v1(self):
        self.assertEqual(
            规范化在线api地址("https://dashscope.aliyuncs.com/compatible-mode"),
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    def test_通义千问compatiblemode_v1_不补(self):
        self.assertEqual(
            规范化在线api地址("https://dashscope.aliyuncs.com/compatible-mode/v1"),
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    def test_https完整地址带chatcompletions_截断(self):
        self.assertEqual(
            规范化在线api地址("https://api.openai.com/v1/chat/completions"),
            "https://api.openai.com/v1",
        )


class Test获取在线api模型列表(unittest.TestCase):
    """GET {api_base}/models 带 Authorization 头"""

    @patch('requests.get')
    def test_成功返回模型列表(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": [{"id": "Qwen3-32B-0709"}, {"id": "gpt-4o"}]}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        结果 = 获取在线api模型列表("http://119.6.186.168:40040", "sk-xxx")

        self.assertEqual(len(结果), 2)
        self.assertEqual(结果[0]["id"], "Qwen3-32B-0709")
        # 验证请求头含 Authorization
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], "http://119.6.186.168:40040/v1/models")
        self.assertIn("Authorization", kwargs["headers"])
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sk-xxx")

    @patch('requests.get')
    def test_空data字段_返回空列表(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        结果 = 获取在线api模型列表("http://119.6.186.168:40040", "sk-xxx")
        self.assertEqual(结果, [])

    def test_空地址_抛异常(self):
        with self.assertRaises(ValueError):
            获取在线api模型列表("", "sk-xxx")

    def test_空密钥_抛异常(self):
        with self.assertRaises(ValueError):
            获取在线api模型列表("http://119.6.186.168:40040", "")


class Test探测在线api状态(unittest.TestCase):
    """连通性检测，返回格式与 探测lm_studio状态() 对齐"""

    @patch('主程序.mineru桥接.获取在线api模型列表')
    def test_成功且模型在列表里(self, mock_获取):
        mock_获取.return_value = [{"id": "Qwen3-32B-0709"}, {"id": "gpt-4o"}]

        状态 = 探测在线api状态("http://119.6.186.168:40040", "sk-xxx", "Qwen3-32B-0709")

        self.assertTrue(状态["已启动"])
        self.assertTrue(状态["模型已加载"])
        self.assertEqual(状态["模型名称"], "Qwen3-32B-0709")

    @patch('主程序.mineru桥接.获取在线api模型列表')
    def test_成功但模型不在列表里(self, mock_获取):
        """模型不在 /models 返回里（有些 API 不全），已启动但模型未加载"""
        mock_获取.return_value = [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]

        状态 = 探测在线api状态("http://119.6.186.168:40040", "sk-xxx", "不存在的模型")

        self.assertTrue(状态["已启动"])
        self.assertFalse(状态["模型已加载"])
        self.assertEqual(状态["模型名称"], "不存在的模型")

    @patch('主程序.mineru桥接.获取在线api模型列表')
    def test_没填模型名_取第一个(self, mock_获取):
        mock_获取.return_value = [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]

        状态 = 探测在线api状态("http://119.6.186.168:40040", "sk-xxx", "")

        self.assertTrue(状态["已启动"])
        self.assertTrue(状态["模型已加载"])
        self.assertEqual(状态["模型名称"], "gpt-4o")

    @patch('主程序.mineru桥接.获取在线api模型列表')
    def test_空模型列表(self, mock_获取):
        mock_获取.return_value = []

        状态 = 探测在线api状态("http://119.6.186.168:40040", "sk-xxx", "")

        self.assertTrue(状态["已启动"])
        self.assertFalse(状态["模型已加载"])

    @patch('主程序.mineru桥接.获取在线api模型列表')
    def test_网络异常_返回未启动(self, mock_获取):
        mock_获取.side_effect = Exception("连接失败")

        状态 = 探测在线api状态("http://119.6.186.168:40040", "sk-xxx", "Qwen3-32B-0709")

        self.assertFalse(状态["已启动"])
        self.assertFalse(状态["模型已加载"])


if __name__ == "__main__":
    unittest.main()
