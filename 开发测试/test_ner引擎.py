import tempfile
import unittest
from unittest.mock import patch

from 主程序.ner引擎 import 全局映射表, 判断机构子类型, NER引擎
from 主程序.mineru桥接 import 选择首选文本模型


class Test判断机构子类型(unittest.TestCase):
    def test_公司(self):
        self.assertEqual(判断机构子类型("XX集团有限公司"), "公司")

    def test_协会(self):
        self.assertEqual(判断机构子类型("XX行业协会"), "协会")

    def test_机关(self):
        self.assertEqual(判断机构子类型("XX市财政局"), "机关")

    def test_事业单位(self):
        self.assertEqual(判断机构子类型("XX研究院"), "事业单位")

    def test_合伙企业(self):
        self.assertEqual(判断机构子类型("XX投资合伙企业"), "合伙企业")

    def test_未知类型(self):
        self.assertEqual(判断机构子类型("XX组织"), "机构")


class Test全局映射表(unittest.TestCase):
    def test_新建映射_自动编号(self):
        映射 = 全局映射表()
        self.assertEqual(映射.查找或创建("XX集团", "公司"), "[公司1]")
        self.assertEqual(映射.查找或创建("YY有限公司", "公司"), "[公司2]")
        self.assertEqual(映射.查找或创建("张三", "Nh"), "[人物1]")

    def test_重复原文_返回同一代号(self):
        映射 = 全局映射表()
        代号1 = 映射.查找或创建("XX集团", "公司")
        代号2 = 映射.查找或创建("XX集团", "公司")
        self.assertEqual(代号1, 代号2)

    def test_不同机构子类型分别编号(self):
        映射 = 全局映射表()
        self.assertEqual(映射.查找或创建("XX集团", "公司"), "[公司1]")
        self.assertEqual(映射.查找或创建("XX行业协会", "协会"), "[协会1]")
        self.assertEqual(映射.查找或创建("XX市财政局", "机关"), "[机关1]")
        self.assertEqual(映射.查找或创建("XX研究院", "事业单位"), "[事业单位1]")
        self.assertEqual(映射.查找或创建("YY公司", "公司"), "[公司2]")

    def test_批量替换(self):
        映射 = 全局映射表()
        映射.查找或创建("XX集团", "公司")
        映射.查找或创建("张三", "Nh")
        文本 = "XX集团与张三签署协议"
        self.assertEqual(映射.批量替换文本(文本), "[公司1]与[人物1]签署协议")

    def test_批量还原(self):
        映射 = 全局映射表()
        映射.查找或创建("XX集团", "公司")
        映射.查找或创建("张三", "Nh")
        文本 = "[公司1]与[人物1]签署协议"
        self.assertEqual(映射.批量还原文本(文本), "XX集团与张三签署协议")

    def test_保存和加载(self):
        映射 = 全局映射表()
        映射.查找或创建("XX集团", "公司")
        映射.查找或创建("张三", "Nh")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as f:
            映射.保存到文件(f.name)
            加载映射 = 全局映射表()
            加载映射.从文件加载(f.name)
            self.assertEqual(加载映射.正向映射, {"XX集团": "[公司1]", "张三": "[人物1]"})

    def test_长名称优先替换(self):
        映射 = 全局映射表()
        映射.查找或创建("XX集团有限责任公司", "公司")
        映射.查找或创建("XX集团", "公司")
        文本 = "XX集团有限责任公司是XX集团的子公司"
        结果 = 映射.批量替换文本(文本)
        self.assertIn("[公司1]", 结果)
        self.assertIn("[公司2]", 结果)
        self.assertNotIn("XX集团", 结果)

    def test_银行账号标签(self):
        映射 = 全局映射表()
        self.assertEqual(映射.查找或创建("6222021234567890123", "bank_account"), "[银行账号1]")

    def test_信用代码标签(self):
        映射 = 全局映射表()
        self.assertEqual(映射.查找或创建("91110000MA0123456X", "credit_code"), "[信用代码1]")

    def test_空映射不修改文本(self):
        映射 = 全局映射表()
        self.assertEqual(映射.批量替换文本("hello"), "hello")
        self.assertEqual(映射.批量还原文本("hello"), "hello")


class TestNER引擎辅助方法(unittest.TestCase):
    def test_选择首选文本模型_只认已加载模型(self):
        模型列表 = [
            {"id": "模型A", "type": "llm", "state": "not-loaded"},
            {"id": "模型B", "type": "vlm", "state": "loaded"},
            {"id": "模型C", "type": "llm", "state": "loaded"},
        ]
        self.assertEqual(选择首选文本模型(模型列表), "模型B")

    def test_选择首选文本模型_未加载时返回空(self):
        模型列表 = [
            {"id": "模型A", "type": "llm", "state": "not-loaded"},
            {"id": "模型B", "type": "embeddings", "state": "loaded"},
        ]
        self.assertEqual(选择首选文本模型(模型列表), "")

    def test_提取消息文本_兼容推理字段(self):
        消息 = {
            "content": "",
            "reasoning_content": "思考后输出：[{\"name\": \"张三\", \"type\": \"PERSON\"}]",
        }
        文本 = NER引擎._提取消息文本(消息)
        self.assertIn("张三", 文本)
        self.assertEqual(
            NER引擎._提取json(文本),
            "[{\"name\": \"张三\", \"type\": \"PERSON\"}]",
        )

    def test_提取消息文本_兼容内容列表(self):
        消息 = {
            "content": [
                {"type": "text", "text": "[{\"name\": \"北京\", \"type\": \"LOCATION\"}]"}
            ]
        }
        文本 = NER引擎._提取消息文本(消息)
        self.assertEqual(
            NER引擎._提取json(文本),
            "[{\"name\": \"北京\", \"type\": \"LOCATION\"}]",
        )

    def test_提取消息文本_正式内容优先于推理内容(self):
        消息 = {
            "content": "[{\"name\": \"和邦生物\", \"type\": \"ORGANIZATION\"}]",
            "reasoning_content": "推理过程里还有别的数组：[1, 2, 3]",
        }
        文本 = NER引擎._提取消息文本(消息)
        self.assertEqual(
            NER引擎._提取json(文本),
            "[{\"name\": \"和邦生物\", \"type\": \"ORGANIZATION\"}]",
        )

    def test_检测lm可用性_没有已加载文本模型时返回假(self):
        引擎 = NER引擎()
        with patch("主程序.mineru桥接.读取用户设置", return_value={"llm_mode": "local", "lm_port": 1234}):
            with patch("主程序.mineru桥接.获取lm_studio模型列表", return_value=[
                {"id": "嵌入模型", "type": "embeddings", "state": "loaded"},
                {"id": "文本模型", "type": "llm", "state": "not-loaded"},
            ]):
                self.assertFalse(引擎._检测lm可用性())


if __name__ == "__main__":
    unittest.main()
