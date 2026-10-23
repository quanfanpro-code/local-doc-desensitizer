"""纯正则机构脱敏：不调用模型，识别机构全称、简称并登记出现位置。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from 主程序.识别结果 import 文本块
from 主程序.正则机构识别 import 识别正则机构


class Test正则机构识别(unittest.TestCase):

    def test_识别机构全称并登记位置(self):
        块 = [文本块("b0", "特变电工新疆新能源股份有限公司已中标。", {})]
        结果 = 识别正则机构(块)
        self.assertEqual(len(结果.机构), 1)
        机构 = next(iter(结果.机构.values()))
        self.assertEqual(机构["canonical"], "特变电工新疆新能源股份有限公司")
        位置 = {(m.开始, m.结束, m.原词) for m in 结果.出现}
        self.assertIn((0, 15, "特变电工新疆新能源股份有限公司"), 位置)

    def test_同一机构多次出现全部登记(self):
        块 = [文本块("b0", "特变电工新疆新能源股份有限公司中标。特变电工新疆新能源股份有限公司随后公告。", {})]
        结果 = 识别正则机构(块)
        同名 = [m for m in 结果.出现 if m.原词 == "特变电工新疆新能源股份有限公司"]
        self.assertEqual(len(同名), 2)
        self.assertEqual({m.机构编号 for m in 同名}, {"正则机构1"})

    def test_非机构文本不产生登记(self):
        块 = [文本块("b0", "本次会议讨论了明年的采购计划。", {})]
        结果 = 识别正则机构(块)
        self.assertEqual(结果.机构, {})
        self.assertEqual(结果.出现, [])

    def test_从全称脱壳生成简称并登记出现(self):
        块 = [文本块("b0", "特变电工新疆新能源股份有限公司中标，特变电工随后公告。", {})]
        结果 = 识别正则机构(块)
        机构 = next(iter(结果.机构.values()))
        self.assertIn("特变电工新疆新能源股份有限公司", 机构["names"])
        self.assertIn("特变电工", 机构["names"])
        位置 = {(m.开始, m.结束, m.原词) for m in 结果.出现}
        self.assertIn((0, 15, "特变电工新疆新能源股份有限公司"), 位置)
        self.assertIn((18, 22, "特变电工"), 位置)

    def test_声明简称并入同一机构(self):
        文本 = "星海新能源股份有限公司（以下简称“XHNE”）于二〇二四年成立。"
        块 = [文本块("b0", 文本, {})]
        结果 = 识别正则机构(块)
        机构 = next(iter(结果.机构.values()))
        self.assertIn("星海新能源股份有限公司", 机构["names"])
        self.assertIn("XHNE", 机构["names"])
        位置 = {(m.开始, m.结束, m.原词) for m in 结果.出现}
        self.assertIn((文本.index("XHNE"), 文本.index("XHNE") + 4, "XHNE"), 位置)

    def test_过短简称不脱壳(self):
        块 = [文本块("b0", "京海科技有限公司在京海经营。", {})]
        结果 = 识别正则机构(块)
        机构 = next(iter(结果.机构.values()))
        self.assertNotIn("京", 机构["names"])

    def test_与机构无关的声明不记未完成(self):
        文本 = "双方签订本协议（以下简称“协议”），星海科技有限公司支付款项。"
        块 = [文本块("b0", 文本, {})]
        结果 = 识别正则机构(块)
        机构 = next(iter(结果.机构.values()))
        self.assertEqual(机构["canonical"], "星海科技有限公司")
        self.assertEqual(结果.未完成, [], "与机构无关的声明不应报未完成")

    def test_声明简称已属其他机构时记未完成(self):
        文本 = "明州电力集团有限公司（以下简称“星海”），星海新能源有限公司亦参与。"
        块 = [文本块("b0", 文本, {})]
        结果 = 识别正则机构(块)
        self.assertTrue(any("已归属其他机构" in 问题["原因"] for 问题 in 结果.未完成),
                        f"应报告简称归属冲突，实际：{结果.未完成}")


class Test处理器纯正则模式(unittest.TestCase):

    def test_纯正则模式脱敏机构且不调用模型(self):
        import tempfile
        from unittest.mock import patch
        from 主程序.脱敏处理器 import 脱敏处理器
        临时目录 = tempfile.mkdtemp(prefix="纯正则处理_")
        源文件 = Path(临时目录) / "样例.txt"
        源文件.write_text(
            "特变电工新疆新能源股份有限公司（以下简称“特变电工”）中标，电话13800138000。\n",
            encoding="utf-8")
        处理器 = 脱敏处理器(跳过模型=True)
        with patch.object(处理器._ner, "识别文档", side_effect=AssertionError("不应调用模型识别")) as 识别桩:
            结果 = 处理器.处理文件列表([str(源文件)], 临时目录)
        输出 = (Path(临时目录) / "样例_脱敏.txt").read_text(encoding="utf-8-sig")
        self.assertEqual(识别桩.call_count, 0)
        self.assertNotIn("特变电工新疆新能源股份有限公司", 输出)
        self.assertNotIn("13800138000", 输出)
        self.assertIn("[公司1]", 输出)
        self.assertTrue(结果.成功文件, 结果.未完成环节)

    def test_映射表可分别还原全称与简称(self):
        import tempfile
        from 主程序.脱敏处理器 import 脱敏处理器
        from 主程序.ner引擎 import 全局映射表
        原文 = "星海新能源股份有限公司（以下简称“XHNE”）与XHNE签约。\n"
        临时目录 = tempfile.mkdtemp(prefix="纯正则还原_")
        源文件 = Path(临时目录) / "样例.txt"
        源文件.write_text(原文, encoding="utf-8")
        处理结果 = 脱敏处理器(跳过模型=True).处理文件列表([str(源文件)], 临时目录)
        脱敏文本 = (Path(临时目录) / "样例_脱敏.txt").read_text(encoding="utf-8-sig")
        self.assertNotIn("XHNE", 脱敏文本)
        映射 = 全局映射表()
        映射.从文件加载(处理结果.映射表路径列表[0])
        self.assertEqual(映射.批量还原文本(脱敏文本), 原文)


class Test界面识别方式(unittest.TestCase):

    def _替身(self, 识别方式):
        from types import MethodType, SimpleNamespace
        from 主程序 import app
        界面 = SimpleNamespace()
        界面.cancel_flag = False
        界面.is_processing = True
        界面._processor = None
        界面.日志 = []
        界面.状态 = []
        界面.询问 = []
        控件 = SimpleNamespace(configure=lambda **kw: None, set=lambda value: None)
        界面.progressbar = 界面.progress_text = 界面.status_label = 界面.计时标签 = 控件
        if 识别方式 is not None:
            界面.识别方式_var = SimpleNamespace(get=lambda: 识别方式)
        界面.run_desensitize = MethodType(app.脱敏工具GUI.run_desensitize, 界面)
        界面.after = lambda delay, fn, *a: fn(*a)
        界面.append_log = 界面.日志.append
        界面.update_status_text = 界面.状态.append
        界面.reset_ui = lambda: None
        界面._启动计时 = lambda: None
        界面._主线程询问 = lambda t, c: (界面.询问.append((t, c)), True)[1]
        return 界面

    def _跑预检(self, 界面, 输入, 输出, ocr):
        from unittest.mock import patch
        from 主程序 import app
        from 主程序.ner引擎 import NER引擎
        探测记录 = []
        模型请求 = []
        with patch.object(app, "messagebox",
                          SimpleNamespace(showwarning=lambda *a: None, showerror=lambda *a: None)), \
             patch.object(app, "探测lm_studio状态",
                          side_effect=lambda *a, **k: (探测记录.append(1),
                                                       {"已启动": False, "模型已加载": False})[1]), \
             patch("主程序.mineru桥接.探测在线api状态",
                   side_effect=lambda *a, **k: (探测记录.append(1),
                                                {"已启动": False, "模型已加载": False})[1]), \
             patch("主程序.脱敏处理器.默认ocr引擎", ocr), \
             patch.object(NER引擎, "_请求文档模型",
                          side_effect=lambda *a, **k: 模型请求.append(1)):
            app.脱敏工具GUI._预检并启动脱敏(
                界面, str(输入), str(输出), False, True, False, False, False, "", "", "")
        return 探测记录, 模型请求

    def test_纯正则模式不探测模型不弹窗(self):
        import tempfile
        目录 = Path(tempfile.mkdtemp(prefix="纯正则界面_"))
        源 = 目录 / "普通.txt"
        源.write_text("特变电工新疆新能源股份有限公司来电13800138000", encoding="utf-8")
        输出 = 目录 / "输出"
        界面 = self._替身("纯正则")
        探测记录, 模型请求 = self._跑预检(界面, 源, 输出,
                                    __import__("types").SimpleNamespace(是否可用=lambda: False))
        self.assertEqual(界面.询问, [], "纯正则模式不应弹模型不可用询问")
        self.assertEqual(探测记录, [], "纯正则模式不应探测模型")
        self.assertEqual(模型请求, [])
        正文 = (输出 / "普通_脱敏.txt").read_text(encoding="utf-8-sig")
        self.assertNotIn("特变电工新疆新能源股份有限公司", 正文)
        self.assertNotIn("13800138000", 正文)

    def test_未设识别方式按LLM处理并提示改用纯正则(self):
        import tempfile
        目录 = Path(tempfile.mkdtemp(prefix="默认界面_"))
        源 = 目录 / "普通.txt"
        源.write_text("电话13800138000", encoding="utf-8")
        界面 = self._替身(None)
        self._跑预检(界面, 源, 目录 / "输出",
                  __import__("types").SimpleNamespace(是否可用=lambda: False))
        self.assertTrue(界面.询问, "模型不可用时应弹窗询问")
        self.assertTrue(any("纯正则" in 内容 for _, 内容 in 界面.询问))


if __name__ == "__main__":
    unittest.main()
