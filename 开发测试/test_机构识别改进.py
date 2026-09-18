import json
from pathlib import Path
import unittest
from unittest.mock import patch
from 维护工具.运行脱敏验证 import 验证用临时目录
from 主程序.ner引擎 import 全局映射表, NER引擎
from 主程序.识别结果 import 文本块


class 两轮识别测试(unittest.TestCase):
    def test_补充核对按候选编号解决漏项和普通词冲突(self):
        引擎 = NER引擎()
        块 = [文本块('p','青岛禾舟运输有限公司简称小麦，采购小麦（粮食）。',{})]
        主体 = {'id':'E','canonical':'青岛禾舟运输有限公司','names':['小麦']}
        def 回答(消息, 最大输出=8192):
            请求 = json.loads(消息[-1]['content'])
            if 请求['阶段'] == '候选逐项判断':
                return {'content':json.dumps({'decisions':[{'id':c['id'],'type':'ordinary' if c['开始'] == 块[0].原文.rindex('小麦') else 'Ni','entity_id':'E'} for c in 请求['候选出现']]})}
            return {'content':json.dumps({'entities':[主体],'mentions':[
                {'block':'p','text':主体['canonical'],'entity_id':'E'},
                {'block':'p','text':'小麦','occurrence':2,'type':'Ns'}],
                'non_entities':[{'block':'p','text':'小麦','occurrence':2}]})}
        with patch.object(引擎,'_请求文档模型',side_effect=回答):
            结果 = 引擎.识别文档(块)
        self.assertEqual([m.原词 for m in 结果.出现],['青岛禾舟运输有限公司','小麦'])
        self.assertFalse(结果.未完成)
        self.assertEqual(结果.出现[-1].开始,块[0].原文.index('小麦'))

    def test_后文全称帮助前文简称且普通词保留(self):
        引擎 = NER引擎()
        self.assertTrue(hasattr(引擎, "识别文档"))
        块 = [文本块("前文", "向小麦支付运费。", {}), 文本块("定义", "青岛禾舟运输有限公司简称小麦。", {}), 文本块("普通", "采购小麦（粮食）。", {})]
        主体 = {"id":"E1", "canonical":"青岛禾舟运输有限公司", "names":["小麦"]}
        def 回答(消息, 最大输出=8192):
            请求 = json.loads(消息[-1]["content"])
            if 请求["阶段"] == "候选逐项判断":
                return {"content":json.dumps({"decisions":[{"id":c["id"],"type":"ordinary" if c["block"]=="普通" else "Ni","entity_id":"E1"} for c in 请求["候选出现"]]})}
            if 请求["阶段"] == "发现":
                return {"content":json.dumps({"entities":[主体],"mentions":[]})}
            self.assertIn("E1", 请求["机构资料"])
            self.assertEqual({b["id"] for b in 请求["原文块"]}, {"前文","定义","普通"})
            return {"content":json.dumps({"entities":[],"mentions":[
                {"block":"前文","text":"小麦","entity_id":"E1","type":"Ni"},
                {"block":"定义","text":"青岛禾舟运输有限公司","entity_id":"E1","type":"Ni"},
                {"block":"定义","text":"小麦","entity_id":"E1","type":"Ni"}],
                "non_entities":[{"block":"普通","text":"小麦"}]})}
        with patch.object(引擎,"_请求文档模型",side_effect=回答):
            结果 = 引擎.识别文档(块)
        self.assertEqual(len(结果.出现),3)
        self.assertEqual(结果.已核对块,{"前文","定义","普通"})
        self.assertFalse(结果.未完成)
        self.assertFalse(any(x.块编号=="普通" for x in 结果.出现))

    def test_第二轮仍可发现首轮漏项(self):
        引擎 = NER引擎()
        self.assertTrue(hasattr(引擎, "识别文档"))
        首轮 = {"content":json.dumps({"entities":[],"mentions":[]})}
        次轮 = {"content":json.dumps({"entities":[{"id":"E1","canonical":None,"names":["BlueX"]}],"mentions":[{"block":"p","text":"BlueX","entity_id":"E1","type":"Ni"}]})}
        def 回答(消息, 最大输出=8192):
            req = json.loads(消息[-1]["content"])
            if req["阶段"] == "候选逐项判断":
                return {"content":json.dumps({"decisions":[{"id":c["id"],"type":"Ni","entity_id":"E1"} for c in req["候选出现"]]})}
            return 首轮 if req["阶段"]=="发现" else 次轮
        with patch.object(引擎,"_请求文档模型",side_effect=回答):
            结果 = 引擎.识别文档([文本块("p","向供应商BlueX结算货款",{})])
        self.assertEqual([m.原词 for m in 结果.出现],["BlueX"])
        self.assertFalse(结果.未完成)

    def test_已经被模型肯定的简称也核对普通用法(self):
        engine = NER引擎()
        def 回答(messages,最大输出=8192):
            req = json.loads(messages[-1]["content"])
            if req["阶段"] == "候选逐项判断":
                return {"content":json.dumps({"decisions":[{"id":c["id"],"type":"ordinary"} for c in req["候选出现"]]})}
            return {"content":json.dumps({"entities":[{"id":"E","canonical":None,"names":["小麦"]}],
                "mentions":[{"block":"p","text":"小麦","entity_id":"E"}],"non_entities":[]})}
        with patch.object(engine,"_请求文档模型",side_effect=回答):
            result = engine.识别文档([文本块("p","采购小麦（粮食）。",{})])
        self.assertFalse(result.出现)
        self.assertFalse(result.未完成)

    def test_取消不再发起下一轮(self):
        引擎 = NER引擎()
        self.assertTrue(hasattr(引擎, "识别文档"))
        引擎._取消检查 = lambda: True
        with patch.object(引擎,"_请求文档模型", side_effect=AssertionError("取消后不得继续请求")):
            结果 = 引擎.识别文档([文本块("p","供应商小麦",{})])
        self.assertTrue(结果.未完成)


class 定位替换测试(unittest.TestCase):
    def test_重复冲突不能因第三个重复结果重新被选中(self):
        from 主程序.识别结果 import 出现记录,合并出现
        b = 文本块("p","小麦",{})
        hits,errors = 合并出现([b],[出现记录("p",0,2,"小麦","Ni",k) for k in ("A","B","A")])
        self.assertFalse(hits)
        self.assertTrue(errors)

    def test_长机构资料保留全部名称且不截断后组(self):
        from 主程序.文档识别 import _机构分组,合入机构
        from 主程序.识别结果 import 识别结果,出现记录
        names = [f"机构称呼{i}" for i in range(2000)]
        groups = list(_机构分组({"E":{"canonical":None,"names":names}}))
        self.assertGreater(len(groups),1)
        self.assertEqual([n for g in groups for e in g.values() for n in e["names"]],names)
        a = 识别结果(机构={"A":{"canonical":"甲公司","names":["甲公司"]}})
        b = 识别结果(机构={"B":{"canonical":"甲公司","names":["小麦"]}},出现=[出现记录("p",0,2,"小麦","Ni","B")])
        合入机构(a,b)
        self.assertEqual(b.出现[0].机构编号,"A")
        self.assertIn("小麦",a.机构["A"]["names"])

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

    def 解析(self, 内容):
        self.assertTrue(hasattr(self.引擎, "_解析文档返回"), "缺少含原文位置的模型返回解析")
        return self.引擎._解析文档返回({"content": 内容}, self.块)

    def test_合法空结果与损坏JSON分开(self):
        空 = self.解析('</think>\n```json\n{"entities":[],"mentions":[]}\n```')
        self.assertFalse(空.未完成)
        self.assertEqual(空.已核对块, {"运输"})
        错误 = self.解析('{"entities":[')
        self.assertTrue(错误.未完成)
        self.assertFalse(错误.已核对块)

    def test_未知主体及不唯一位置不能猜(self):
        结果 = self.解析(json.dumps({"entities": [], "mentions": [{"block":"运输", "text":"小麦", "entity_id":"E9", "type":"Ni"}]}))
        self.assertFalse(结果.出现)
        self.assertTrue(结果.未完成)
        结果 = self.解析(json.dumps({"entities": [{"id":"E1", "canonical":None, "names":["小麦"]}], "mentions": [{"block":"运输", "text":"小麦", "entity_id":"E1", "type":"Ni"}]}))
        self.assertFalse(结果.出现)
        self.assertTrue(结果.未完成)

    def test_具体出现编号区分同形普通词(self):
        结果 = self.解析(json.dumps({"entities": [{"id":"E1", "canonical":None, "names":["小麦"]}], "mentions": [{"block":"运输", "text":"小麦", "occurrence":1, "entity_id":"E1", "type":"Ni"}], "non_entities":[{"block":"运输", "text":"小麦", "occurrence":2}]}))
        self.assertEqual([(m.开始,m.结束) for m in 结果.出现], [(1,3)])
        self.assertIn(("运输",11,13), 结果.普通位置)

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
