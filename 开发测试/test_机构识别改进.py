import json
from pathlib import Path
import unittest
from unittest.mock import patch
from 维护工具.运行脱敏验证 import 验证用临时目录
from 主程序.ner引擎 import 全局映射表, NER引擎
from 主程序.识别结果 import 文本块




class 定位替换测试(unittest.TestCase):
    def test_重复冲突不能因第三个重复结果重新被选中(self):
        from 主程序.识别结果 import 出现记录,合并出现
        b = 文本块("p","小麦",{})
        hits,errors = 合并出现([b],[出现记录("p",0,2,"小麦","Ni",k) for k in ("A","B","A")])
        self.assertFalse(hits)
        self.assertTrue(errors)


    def test_评测漏误和错连分别计算(self):
        from 维护工具.验证机构识别 import 评分
        self.assertEqual(评分({("p",0,1):"A",("p",1,2):"B"},{("p",0,1):"C",("p",2,3):"D"}),{"漏检":1,"误检":1,"错误关联":1})

    def test_只改机构位置且拒绝越界重叠(self):
        from 主程序 import 识别结果 as 模块
        self.assertTrue(hasattr(模块,"按位置替换"))
        self.assertEqual(模块.按位置替换("向小麦付款，采购小麦（粮食）。",[(1,3,"[机构1]")]),"向[机构1]付款，采购小麦（粮食）。")
        for spans in [[(0,4,"甲"),(2,5,"乙")],[(0,99,"甲")],[(-1,2,"甲")]]:
            with self.assertRaises(ValueError):
                模块.按位置替换("测试原文",spans)


class 模型结构测试(unittest.TestCase):
    def test_本地模式使用实际加载模型而非类默认占位名(self):
        import requests
        引擎 = NER引擎()
        response = requests.Response(); response.status_code = 200
        response._content = b'{"choices":[{"message":{"content":"{}"}}]}'
        def 已加载():
            引擎._MODEL = "actual-local-model"
            return True
        with patch.object(引擎,"_读取llm配置",return_value={"api_base":"http://test/v1","model":"","mode":"local"}),patch.object(引擎,"_检测lm可用性",side_effect=已加载),patch("requests.post",return_value=response) as post:
            引擎._请求文档模型([])
        self.assertEqual(post.call_args.kwargs["json"]["model"],"actual-local-model")

    def setUp(self):
        self.引擎 = NER引擎()
        self.块 = [文本块("运输", "向小麦支付运费，另采购小麦（粮食）。", {})]





    def test_请求超时可恢复而鉴权失败不重复请求(self):
        import requests
        self.assertTrue(hasattr(self.引擎, "_请求文档模型"))
        ok = requests.Response(); ok.status_code = 200
        ok._content = json.dumps({"choices":[{"message":{"content":"{}"},"finish_reason":"stop"}]}).encode()
        denied = requests.Response(); denied.status_code = 401
        with patch.object(self.引擎,"_读取llm配置",return_value={"mode":"online","api_base":"http://test/v1","api_key":"test","model":"test"}):
            with patch("requests.post", side_effect=[requests.Timeout(),ok]) as post:
                self.assertEqual(self.引擎._请求文档模型([])["content"], "{}")
                self.assertEqual(post.call_count, 2)
            with patch("requests.post", return_value=denied) as post:
                with self.assertRaises(requests.HTTPError):
                    self.引擎._请求文档模型([])
                self.assertEqual(post.call_count, 1)


class 机构映射测试(unittest.TestCase):
    def test_全称简称保存重载后准确还原(self):
        映射 = 全局映射表()
        self.assertTrue(hasattr(映射, "注册机构称呼"), "缺少机构与原文写法分离的登记方法")
        self.assertEqual(映射.注册机构称呼("E1", "成都星河科技有限公司", "公司", True), "[公司1]")
        self.assertEqual(映射.注册机构称呼("E1", "星河", "公司"), "[公司1]①")
        with 验证用临时目录() as 目录:
            路径 = Path(目录) / "映射.json"
            映射.保存到文件(路径)
            重载 = 全局映射表()
            重载.从文件加载(路径)
        self.assertEqual(重载.批量还原文本("[公司1]（[公司1]①）"), "成都星河科技有限公司（星河）")
        self.assertEqual(重载.注册机构称呼("E1", "星科", "公司"), "[公司1]②")

    def test_同名不同主体与原文代号不碰撞(self):
        映射 = 全局映射表()
        self.assertTrue(hasattr(映射, "保留原文代号"))
        映射.保留原文代号("原文已有[公司1]和[公司2]①")
        a = 映射.注册机构称呼("E1", "小麦", "公司", True)
        b = 映射.注册机构称呼("E2", "小麦", "公司", True)
        self.assertNotEqual(a, b)
        self.assertNotIn(a, ("[公司1]", "[公司2]"))
        self.assertEqual(映射.批量还原文本(a + "和" + b), "小麦和小麦")

    def test_旧映射可读取且多种称呼不丢失(self):
        映射 = 全局映射表()
        with 验证用临时目录() as 目录:
            路径 = Path(目录) / "旧映射.json"
            路径.write_text(json.dumps({"甲公司": "[公司5]"}), encoding="utf-8")
            映射.从文件加载(路径)
        self.assertEqual(映射.批量还原文本("[公司5]"), "甲公司")
        self.assertTrue(hasattr(映射, "注册机构称呼"))
        for i in range(13):
            映射.注册机构称呼("E", f"称呼{i}", "公司", i == 0)
        self.assertEqual(len(set(映射.反向映射)), 14)
