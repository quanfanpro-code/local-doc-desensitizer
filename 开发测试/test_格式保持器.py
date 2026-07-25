import tempfile
import unittest
from pathlib import Path

from 主程序.ner引擎 import 全局映射表
from 主程序.格式保持器 import 脱敏并保存原格式, 还原并保存原格式, 生成脱敏md


class Test文本脱敏还原(unittest.TestCase):
    def test_txt脱敏和还原(self):
        映射 = 全局映射表()
        映射.查找或创建("测试公司", "公司")
        映射.查找或创建("张三", "Nh")
        with tempfile.TemporaryDirectory() as 目录:
            原文件 = Path(目录) / "test.txt"
            原文件.write_text("测试公司的张三签署了合同", encoding="utf-8")
            脱敏路径 = 脱敏并保存原格式(str(原文件), 映射, 目录)
            脱敏内容 = Path(脱敏路径).read_text(encoding="utf-8")
            self.assertIn("[公司1]", 脱敏内容)
            self.assertIn("[人物1]", 脱敏内容)
            还原路径 = 还原并保存原格式(脱敏路径, 映射, 目录)
            还原内容 = Path(还原路径).read_text(encoding="utf-8")
            self.assertEqual(还原内容, "测试公司的张三签署了合同")

    def test_md额外输出(self):
        映射 = 全局映射表()
        映射.查找或创建("测试公司", "公司")
        with tempfile.TemporaryDirectory() as 目录:
            原文件 = Path(目录) / "test.txt"
            原文件.write_text("测试公司报告", encoding="utf-8")
            md路径 = 生成脱敏md(str(原文件), 映射, 目录)
            self.assertTrue(md路径.endswith("_脱敏.md"))
            md内容 = Path(md路径).read_text(encoding="utf-8")
            self.assertIn("[公司1]", md内容)

    def test_md文件脱敏还原(self):
        映射 = 全局映射表()
        映射.查找或创建("测试协会", "协会")
        with tempfile.TemporaryDirectory() as 目录:
            原文件 = Path(目录) / "test.md"
            原文件.write_text("# 测试协会年度报告\n测试协会于2024年成立", encoding="utf-8")
            脱敏路径 = 脱敏并保存原格式(str(原文件), 映射, 目录)
            脱敏内容 = Path(脱敏路径).read_text(encoding="utf-8")
            self.assertIn("[协会1]", 脱敏内容)
            self.assertNotIn("测试协会", 脱敏内容)
            还原路径 = 还原并保存原格式(脱敏路径, 映射, 目录)
            还原内容 = Path(还原路径).read_text(encoding="utf-8")
            self.assertIn("测试协会", 还原内容)


if __name__ == "__main__":
    unittest.main()
