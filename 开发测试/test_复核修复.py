"""2026-07-25 全面复核发现问题的回归测试

覆盖：
- 注册自定义映射 碰撞超过 10 次后不得静默放弃（原文泄露风险）
- 生成脱敏md 支持传入已提取文本（扫描版 PDF 的 OCR 文本不应被重新提取）
- NER 调试日志默认关闭、开启时异常也要关闭句柄
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from 主程序.ner引擎 import 全局映射表, NER引擎
from 主程序.格式保持器 import 生成脱敏md
from 主程序.脱敏处理器 import 脱敏处理器


class Test映射碰撞兜底(unittest.TestCase):
    """同一代号的简称碰撞超过 ①~⑩ 后，必须用数字后缀继续注册，不能静默放弃"""

    def test_超过10次碰撞仍然全部注册(self):
        映射 = 全局映射表()
        for n in range(12):
            映射.注册自定义映射(f"原文{n}", "[公司1]")
        for n in range(12):
            self.assertIn(f"原文{n}", 映射.正向映射, f"原文{n} 被静默丢弃")
        # 所有替换值可还原
        self.assertEqual(len(映射.反向映射), 12)


class Test生成脱敏md传入文本(unittest.TestCase):
    """扫描版 PDF 没有文字层，必须用 OCR 出的文本生成 md，不能重新从文件提取"""

    def test_传入文本时直接用它(self):
        映射 = 全局映射表()
        映射.查找或创建("秘密公司", "公司")
        with tempfile.TemporaryDirectory() as 目录:
            # 故意给一个不存在的文件路径：若仍尝试从文件提取会直接报错
            假pdf = str(Path(目录) / "扫描件.pdf")
            md路径 = 生成脱敏md(假pdf, 映射, 目录, 原始文本="秘密公司的年度报告")
            内容 = Path(md路径).read_text(encoding="utf-8")
            self.assertIn("[公司1]", 内容)
            self.assertNotIn("秘密公司", 内容)
            self.assertTrue(md路径.endswith("扫描件_脱敏.md"))

    def test_不传文本时保持原行为(self):
        映射 = 全局映射表()
        映射.查找或创建("测试公司", "公司")
        with tempfile.TemporaryDirectory() as 目录:
            原文件 = Path(目录) / "a.txt"
            原文件.write_text("测试公司报告", encoding="utf-8")
            md路径 = 生成脱敏md(str(原文件), 映射, 目录)
            内容 = Path(md路径).read_text(encoding="utf-8")
            self.assertIn("[公司1]", 内容)


class Test调试日志开关(unittest.TestCase):
    """调试日志默认关闭；开启后即使处理抛异常也必须关闭文件句柄"""

    def _造txt(self, 目录: str) -> str:
        p = Path(目录) / "a.txt"
        p.write_text("张三签署合同", encoding="utf-8")
        return str(p)

    def test_默认不产生调试日志(self):
        with tempfile.TemporaryDirectory() as 目录:
            文件 = self._造txt(目录)
            处理器 = 脱敏处理器()
            with patch.object(处理器._ner, "文本脱敏", return_value=""):
                处理器.处理文件列表([文件], 目录)
            日志文件 = list(Path(目录).glob("*_NER调试.log"))
            self.assertEqual(日志文件, [], "默认不应生成 NER 调试日志")

    def test_开启后生成且句柄被关闭(self):
        with tempfile.TemporaryDirectory() as 目录:
            文件 = self._造txt(目录)
            处理器 = 脱敏处理器()
            with patch("主程序.脱敏处理器.读取用户设置", return_value={"debug_ner_log": True}), \
                 patch.object(处理器._ner, "文本脱敏", return_value=""):
                处理器.处理文件列表([文件], 目录)
            日志文件 = list(Path(目录).glob("*_NER调试.log"))
            self.assertEqual(len(日志文件), 1)
            self.assertIsNone(NER引擎._调试日志文件, "调试日志句柄未关闭")

    def test_开启后处理抛异常句柄也被关闭(self):
        with tempfile.TemporaryDirectory() as 目录:
            文件 = self._造txt(目录)
            处理器 = 脱敏处理器()
            with patch("主程序.脱敏处理器.读取用户设置", return_value={"debug_ner_log": True}), \
                 patch.object(处理器._ner, "文本脱敏", side_effect=RuntimeError("质量闸门")):
                结果 = 处理器.处理文件列表([文件], 目录)
            self.assertEqual(结果.失败数, 1)
            self.assertIsNone(NER引擎._调试日志文件, "异常时调试日志句柄未关闭")


if __name__ == "__main__":
    unittest.main()
