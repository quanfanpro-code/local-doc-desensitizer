"""Y1：耗时预检期间用户取消必须生效。

- 检查扫描版PDF 的循环要响应取消标记，取消后不再继续逐个打开 PDF
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from 主程序.脱敏处理器 import 脱敏处理器


class Test预检取消(unittest.TestCase):

    def test_检查扫描版pdf响应取消(self):
        处理器 = 脱敏处理器()
        调用次数 = []

        def 假判断(路径):
            调用次数.append(路径)
            处理器.请求取消()  # 模拟用户在预检期间点了取消
            return False

        with patch("主程序.脱敏处理器.判断是否扫描版pdf", side_effect=假判断):
            结果 = 处理器.检查扫描版pdf(["a.pdf", "b.pdf", "c.pdf"])

        self.assertEqual(len(调用次数), 1, "取消后不应继续检查剩余 PDF")
        self.assertEqual(结果, [])


if __name__ == "__main__":
    unittest.main()
