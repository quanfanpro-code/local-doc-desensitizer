"""X9：Excel 固定规则的字段提示按列归属。

问题：标签判断把整行内容和前三行表头一起搜，其他列的字段名（如“身份证号”）
会干扰当前列的判断。修复后：固定规则只看当前列的字段提示；
整行上下文仍保留给模型使用，不受影响。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from 主程序.识别结果 import 文本块
from 主程序.固定规则 import 固定规则识别
from 主程序.文档解析器 import 读取文档块


def _造身份证(前17位: str) -> str:
    """按校验位算法造一个格式合法的身份证号"""
    权 = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    return 前17位 + "10X98765432"[sum(int(x) * w for x, w in zip(前17位, 权)) % 11]


# 校验位故意不对的 18 位串：只有字段提示明确时才应被识别为身份证
假身份证 = "11010119900307777X"


def _单元格块(原文: str, 列字段: str | None, 上下文: str) -> 文本块:
    位置 = {"工作表": "S", "单元格": "A2"}
    if 列字段 is not None:
        位置["列字段"] = 列字段
    return 文本块("xlsx:0:A2", 原文, 位置, 上下文)


class Test字段提示按列归属(unittest.TestCase):

    def test_其他列的字段名不干扰当前格(self):
        """本列是“物料编号”，同行另一列叫“身份证号”：不应误判为身份证"""
        块 = _单元格块(假身份证, "物料编号", "工作表：S；表头：物料编号 | 身份证号；本行：x | y")
        命中 = 固定规则识别(块)
        self.assertFalse(any(m.类型 == "id_card" for m in 命中),
                         "其他列的“身份证号”字段名不应影响当前格判断")

    def test_当前列字段提示生效(self):
        """本列字段是“身份证号”：即使校验位不对也应识别（字段明确）"""
        块 = _单元格块(假身份证, "身份证号", "工作表：S；表头：物料编号 | 身份证号；本行：x | y")
        命中 = 固定规则识别(块)
        self.assertTrue(any(m.类型 == "id_card" for m in 命中))

    def test_无列字段时行为不变(self):
        """非 Excel 块（位置里没有列字段）：仍按原逻辑搜索整段上下文"""
        块 = 文本块("text:0", 假身份证, {"行": 0}, "这里登记身份证号")
        命中 = 固定规则识别(块)
        self.assertTrue(any(m.类型 == "id_card" for m in 命中))


class Test解析器给出列字段(unittest.TestCase):

    def test_读取文档块带当前列字段提示(self):
        临时目录 = tempfile.mkdtemp(prefix="列字段测试_")
        文件 = Path(临时目录) / "表.xlsx"
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "S"
        ws.append(["物料编号", "身份证号"])
        ws.append([假身份证, _造身份证("110101199003077")])
        wb.save(文件)
        wb.close()

        块列表 = 读取文档块(str(文件))
        按格 = {b.位置["单元格"]: b for b in 块列表}
        self.assertEqual(按格["A2"].位置.get("列字段"), "物料编号")
        self.assertEqual(按格["B2"].位置.get("列字段"), "身份证号")
        # 整行上下文保留给模型使用，不能删
        self.assertIn("本行", 按格["A2"].上下文)


if __name__ == "__main__":
    unittest.main()
