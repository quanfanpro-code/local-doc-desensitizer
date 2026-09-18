"""X8：用户选择“仅使用正则”后，必须真正关闭模型识别。

- 跳过模型时不再调用 NER 引擎的 识别文档/复查输出（不会对着不可用的 LLM 空转重试）
- 固定规则（手机号等）仍然生效
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from 主程序.脱敏处理器 import 脱敏处理器


class Test仅正则模式(unittest.TestCase):

    def _跑一遍(self, 跳过模型: bool):
        临时目录 = tempfile.mkdtemp(prefix="仅正则测试_")
        源文件 = Path(临时目录) / "测试.txt"
        源文件.write_text("张三的电话是13800138000。\n", encoding="utf-8")
        处理器 = 脱敏处理器(跳过模型=跳过模型)
        with patch.object(处理器._ner, "识别文档", side_effect=AssertionError("不应调用模型识别")) as 识别桩, \
             patch.object(处理器._ner, "复查输出", side_effect=AssertionError("不应调用输出复查")) as 复查桩:
            结果 = 处理器.处理文件列表([str(源文件)], 临时目录)
        输出文件 = Path(临时目录) / "测试_脱敏.txt"
        return 结果, 输出文件, 识别桩, 复查桩

    def test_仅正则时不调用模型(self):
        结果, 输出文件, 识别桩, 复查桩 = self._跑一遍(跳过模型=True)
        self.assertEqual(识别桩.call_count, 0)
        self.assertEqual(复查桩.call_count, 0)
        self.assertTrue(输出文件.exists(), "仅正则模式也必须交付脱敏结果")
        内容 = 输出文件.read_text(encoding="utf-8-sig")
        self.assertNotIn("13800138000", 内容, "固定规则（手机号）在仅正则模式下仍应生效")

    def test_默认仍调用模型(self):
        """对照组：不跳过模型时，识别文档会被调用（桩抛错会被处理器记录为未完成，不影响验证调用次数）"""
        结果, 输出文件, 识别桩, 复查桩 = self._跑一遍(跳过模型=False)
        self.assertGreaterEqual(识别桩.call_count, 1, "默认模式应调用模型识别")


if __name__ == "__main__":
    unittest.main()
