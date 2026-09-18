import importlib
import unittest
from 主程序.识别结果 import 文本块


class 固定规则测试(unittest.TestCase):
    def test_外币复合单位和已有模糊金额不误改(self):
        from 主程序.固定规则 import 金额模糊值
        self.assertEqual(金额模糊值("123万美元"),"100万余美元")
        self.assertFalse(self.识别("100万余美元；200万余元",金额=True))
        self.assertTrue(any(m.原词=="123万美元" for m in self.识别("款项123万美元",金额=True)))

    def test_金额保留币种门槛和日期仅年份选项(self):
        from 主程序.固定规则 import 固定规则识别
        from 主程序.识别结果 import 识别结果, 按位置替换
        from 主程序.ner引擎 import 全局映射表
        from 主程序.定位写回 import 准备替换
        b = 文本块("p","2026年9月18日；1234567美元；500元",{})
        映射 = 全局映射表()
        结果 = 识别结果(出现=固定规则识别(b,True,False,True))
        spans = 准备替换([b],结果,映射)["p"]
        输出 = 按位置替换(b.原文,spans)
        self.assertEqual(输出,"20X6年9月18日；100万余美元；500元")
        self.assertEqual(映射.批量还原文本(输出),b.原文)

    def 识别(self, text, 日期=False, 月日=False, 金额=False, 上下文=""):
        try:
            规则 = importlib.import_module("主程序.固定规则")
        except ImportError:
            self.fail("尚未实现统一的固定格式候选与校验")
        return 规则.固定规则识别(文本块("p",text,{},上下文),日期,月日,金额)

    def test_电话分隔全角区号分机和国际写法(self):
        for 原词 in ["138 0013 8000","138-0013-8000","１３８００１３８０００","（028）88889999","028-88889999转123","400-800-1234","+1 202-555-0123"]:
            with self.subTest(原词=原词):
                self.assertTrue(any(m.原词==原词 for m in self.识别("电话："+原词)))

    def test_证件分类和明确标签下校验异常(self):
        samples = [("身份证：11010519491231002X","11010519491231002X","id_card"),
            ("统一社会信用代码：91110105ma01234565","91110105ma01234565","credit_code"),
            ("统一社会信用代码：91110105MA01234560","91110105MA01234560","credit_code"),
            ("银行账号：1234567890123456789012","1234567890123456789012","bank_account"),
            ("卡号：4111 1111 1111 1111","4111 1111 1111 1111","bank_account")]
        for text,原词,类型 in samples:
            with self.subTest(text=text):
                items = self.识别(text)
                self.assertEqual([(m.原词,m.类型) for m in items],[(原词,类型)])
        self.assertFalse(self.识别("物料编号：ABCDEFGHIJKLMNOPQR"))
        self.assertFalse(self.识别("物料编号：123456789012345678"))

    def test_其余类别与开关(self):
        samples = [("o'connor@example.com","email"),("川A12345","plate_number"),("192.0.2.12","ip_address"),("00:11:22:33:44:55","mac_address")]
        for 原词,类型 in samples:
            self.assertTrue(any(m.原词==原词 and m.类型==类型 for m in self.识别(原词)))
        for text in ["2026/09/18","2026-09-18","二〇二六年九月十八日"]:
            self.assertFalse(self.识别(text))
            self.assertTrue(any(m.类型=="date" for m in self.识别(text,日期=True)))
        for text in ["1234567美元","壹佰贰拾万元整"]:
            self.assertFalse(self.识别(text))
            self.assertTrue(any(m.类型=="amount" for m in self.识别(text,金额=True)))
