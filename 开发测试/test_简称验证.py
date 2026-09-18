"""机构关系相同仍逐字还原，独立的母公司不随子串自动合并。"""
import unittest
from unittest.mock import patch
from 主程序.ner引擎 import 全局映射表, NER引擎
from 主程序.识别结果 import 识别结果, 出现记录


class 简称兼容测试(unittest.TestCase):
    def test_显式简称登记保留原写法(self):
        m = 全局映射表()
        m.查找或创建("成都禾舟科技有限公司","公司")
        NER引擎()._合并简称声明('成都禾舟科技有限公司（以下简称“禾舟”）',m)
        self.assertNotEqual(m.正向映射["成都禾舟科技有限公司"],m.正向映射["禾舟"])
        self.assertEqual(m.批量还原文本(m.正向映射["禾舟"]),"禾舟")

    def test_文本接口使用位置且母子主体分离(self):
        text = "禾舟集团与禾舟科技签约，禾舟为诗中用语。"
        result = 识别结果(机构={"母":{"canonical":None,"names":["禾舟集团"]},
            "子":{"canonical":None,"names":["禾舟科技"]}},出现=[
            出现记录("text:0",0,4,"禾舟集团","Ni","母"),
            出现记录("text:0",5,9,"禾舟科技","Ni","子")])
        m = 全局映射表(); engine = NER引擎()
        with patch.object(engine,"识别文档",return_value=result):
            masked = engine.文本脱敏(text,m)
        self.assertIn("禾舟为诗中用语",masked)
        self.assertNotEqual(m._机构["母"]["主代号"],m._机构["子"]["主代号"])
        self.assertEqual(m.批量还原文本(masked),text)
