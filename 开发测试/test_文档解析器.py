import tempfile
import unittest
from pathlib import Path

from 主程序.文档解析器 import 提取文本, 收集支持的文件, SUPPORTED_EXTENSIONS


class Test收集支持的文件(unittest.TestCase):
    def test_空目录返回空列表(self):
        with tempfile.TemporaryDirectory() as 目录:
            self.assertEqual(收集支持的文件(目录), [])

    def test_筛选支持的格式(self):
        with tempfile.TemporaryDirectory() as 目录:
            (Path(目录) / "a.txt").write_text("hello", encoding="utf-8")
            (Path(目录) / "b.xyz").write_text("hello", encoding="utf-8")
            结果 = 收集支持的文件(目录)
            self.assertEqual(len(结果), 1)
            self.assertTrue(结果[0].endswith("a.txt"))

    def test_支持所有目标后缀(self):
        for 后缀 in [".txt", ".md", ".docx", ".xlsx", ".pptx", ".pdf"]:
            self.assertIn(后缀, SUPPORTED_EXTENSIONS)


class Test提取文本_txt(unittest.TestCase):
    def test_读取txt(self):
        with tempfile.TemporaryDirectory() as 目录:
            文件 = Path(目录) / "test.txt"
            文件.write_text("测试文本内容", encoding="utf-8")
            结果 = 提取文本(str(文件))
            self.assertEqual(结果, "测试文本内容")

    def test_读取md(self):
        with tempfile.TemporaryDirectory() as 目录:
            文件 = Path(目录) / "test.md"
            文件.write_text("# 标题\n正文", encoding="utf-8")
            结果 = 提取文本(str(文件))
            self.assertIn("标题", 结果)
            self.assertIn("正文", 结果)


if __name__ == "__main__":
    unittest.main()
