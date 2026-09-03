"""NER 引擎跨块实体复用 单元测试

测试 ner引擎.py 的改造：
- _构造白名单：根据已识别实体 + 频次构造白名单，受字符上限约束
- 识别实体：跨块复用已识别实体，单次调用内重置状态
- _调用llm：接收 已知实体 参数并注入 prompt
- _严格解析 / _兜底解析：接收 黑名单 参数并过滤

设计文档：docs/superpowers/specs/2026-07-21-跨块实体复用-design.md
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))

from 主程序.ner引擎 import NER引擎


class Test构造白名单(unittest.TestCase):
    """_构造白名单：根据频次构造白名单，字符总数 ≤ 上限"""

    def test_空输入返回空(self):
        引擎 = NER引擎()
        结果 = 引擎._构造白名单({}, {}, 上限字符数=800)
        self.assertEqual(结果, {})

    def test_未超限全部进入(self):
        引擎 = NER引擎()
        已识别 = {"张三": "PERSON", "北京": "LOCATION", "涌江实业": "ORGANIZATION"}
        频次 = {"张三": 1, "北京": 1, "涌江实业": 1}
        结果 = 引擎._构造白名单(已识别, 频次, 上限字符数=800)
        self.assertEqual(set(结果.keys()), {"张三", "北京", "涌江实业"})

    def test_超限按频次裁(self):
        """大量实体时，频次高的优先保留"""
        引擎 = NER引擎()
        # 构造 50 个实体，每个名称 10 字符
        # 每条格式 "实体名|PERSON，" ≈ 18 字符
        # 上限 100 字符 → 大约能塞 5 条
        已识别 = {f"实体{i:02d}": "PERSON" for i in range(50)}
        # 高频次：实体00~04 频次=5
        # 中频次：实体05~09 频次=3
        # 低频次：实体10~49 频次=1
        频次 = {}
        for i in range(50):
            if i < 5:
                频次[f"实体{i:02d}"] = 5
            elif i < 10:
                频次[f"实体{i:02d}"] = 3
            else:
                频次[f"实体{i:02d}"] = 1

        结果 = 引擎._构造白名单(已识别, 频次, 上限字符数=100)

        # 高频次必须保留
        for i in range(5):
            self.assertIn(f"实体{i:02d}", 结果)
        # 低频次必须被裁掉
        self.assertNotIn("实体49", 结果)
        # 结果总字符数不超限
        self.assertLessEqual(引擎._白名单字符数(结果), 100)

    def test_频次相同长度优先(self):
        """频次相同则长实体优先（同频次时长的先入）"""
        引擎 = NER引擎()
        # 上限 20 字符
        # "这是一个非常长的实体名称"(12) + |PERSON, = 20 → 恰好能入
        # 剩余 0 字符，别的都进不来
        已识别 = {"短": "PERSON", "中等长度实体名": "PERSON", "这是一个非常长的实体名称": "PERSON"}
        频次 = {"短": 3, "中等长度实体名": 3, "这是一个非常长的实体名称": 3}
        结果 = 引擎._构造白名单(已识别, 频次, 上限字符数=20)
        # 最长的应该被选中（按长度优先排序，先入）
        self.assertIn("这是一个非常长的实体名称", 结果)
        self.assertNotIn("短", 结果)
        self.assertNotIn("中等长度实体名", 结果)
        self.assertLessEqual(引擎._白名单字符数(结果), 20)


class Test识别实体跨块状态(unittest.TestCase):
    """识别实体：单次调用内累积，多次调用间状态隔离"""

    def test_跨块复用第二块收到第一块实体(self):
        """第 2 块调用 LLM 时，prompt 中应包含第 1 块的已识别实体"""
        引擎 = NER引擎()
        # 模拟 3 块文本，每块 >6000 字符才能触发多块切分
        # 改为直接 mock _调用llm，更可控
        调用记录 = []

        def mock_调用llm(self, 文本, _重试=0, *, 已知实体=None):
            调用记录.append(已知实体 or {})
            if len(调用记录) == 1:
                return [("张三", "Nh"), ("北京", "Ns")]
            elif len(调用记录) == 2:
                return [("涌江实业", "Ni")]
            else:
                return []

        # 直接修改 _调用llm 不容易 patch（被同实例引用），改 patch 类方法
        with patch.object(NER引擎, '_调用llm', autospec=True) as mock_method:
            mock_method.side_effect = [
                [("张三", "Nh"), ("北京", "Ns")],
                [("涌江实业", "Ni")],
                [],
            ]
            文本 = "块1内容" + ("x" * 6500) + "块2内容" + ("y" * 6500) + "块3内容"
            引擎.识别实体(文本)

            self.assertEqual(mock_method.call_count, 3)
            # 第 1 次调用：白名单为空
            第一块参 = mock_method.call_args_list[0].kwargs.get("已知实体") or mock_method.call_args_list[0].kwargs.get("已知实体")
            # keyword-only 参数
            第一块已知 = mock_method.call_args_list[0].kwargs.get("已知实体")
            self.assertEqual(第一块已知, {})

            # 第 2 次调用：白名单含张三、北京
            第二块已知 = mock_method.call_args_list[1].kwargs.get("已知实体")
            self.assertIn("张三", 第二块已知)
            self.assertIn("北京", 第二块已知)

            # 第 3 次调用：白名单含张三、北京、涌江实业
            第三块已知 = mock_method.call_args_list[2].kwargs.get("已知实体")
            self.assertIn("张三", 第三块已知)
            self.assertIn("北京", 第三块已知)
            self.assertIn("涌江实业", 第三块已知)

    def test_两次调用状态隔离(self):
        """第二次调用识别实体时，白名单应为空（不跨文件累计）"""
        引擎 = NER引擎()

        with patch.object(NER引擎, '_调用llm', autospec=True) as mock_method:
            # 13000 字符 / 6000 = 3 块，需 3 个 side_effect
            mock_method.side_effect = [
                [("张三", "Nh")],
                [("李四", "Nh")],
                [("王五", "Nh")],
            ]
            文本1 = "a" * 6500 + "b" * 6500
            引擎.识别实体(文本1)

            # 第 2 块的白名单应包含张三
            第二块已知 = mock_method.call_args_list[1].kwargs.get("已知实体")
            self.assertIn("张三", 第二块已知)

            # 第二次调用识别实体
            mock_method.reset_mock()
            mock_method.side_effect = [
                [("赵六", "Nh")],
                [("孙七", "Nh")],
                [("周八", "Nh")],
            ]
            文本2 = "c" * 6500 + "d" * 6500
            引擎.识别实体(文本2)

            # 第二次调用的第 1 块：白名单应为空
            第一块已知 = mock_method.call_args_list[0].kwargs.get("已知实体")
            self.assertEqual(第一块已知, {})

    def test_防御去重_LLM不遵守prompt时丢弃(self):
        """LLM 在第 2 块返回含第 1 块已识别实体，识别实体应去重"""
        引擎 = NER引擎()

        with patch.object(NER引擎, '_调用llm', autospec=True) as mock_method:
            # 第 1 块：正常返回 张三
            # 第 2 块：mock LLM 不遵守 prompt，又返回了 张三 + 新增 李四
            # 但我们这里 _调用llm 已经被 mock，所以"不遵守 prompt"表现为：
            # mock 直接返回含 张三 的列表，但 prompt 注入由 mock 负责
            # 我们通过 mock_method 模拟：第 2 块返回 [(张三,Nh), (李四,Nh)]
            # 验证 _严格解析 / _兜底解析 内部会去重——这里直接验证识别实体最终结果
            mock_method.side_effect = [
                [("张三", "Nh")],
                [("张三", "Nh"), ("李四", "Nh")],
                [],
            ]
            文本 = "a" * 6500 + "b" * 6500
            结果 = 引擎.识别实体(文本)

            # 张三只能出现一次
            实体名列表 = [n for n, _ in 结果]
            self.assertEqual(实体名列表.count("张三"), 1)
            self.assertIn("李四", 实体名列表)


class Test调用llm已知实体注入(unittest.TestCase):
    """_调用llm：已知实体参数注入 prompt"""

    def _构造mock_响应(self, 返回内容):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": 返回内容}}]
        }
        return mock_resp

    @patch('主程序.ner引擎.NER引擎._读取llm配置')
    @patch('requests.post')
    def test_已知实体非空时注入prompt(self, mock_post, mock_配置):
        """传入已知实体时，prompt 应包含白名单段落"""
        mock_配置.return_value = {"mode": "online", "api_base": "http://test", "api_key": "k", "model": "m"}
        mock_post.return_value = self._构造mock_响应("[]")

        引擎 = NER引擎()
        引擎._调用llm("测试文本", 已知实体={"张三": "Nh", "北京": "Ns"})

        # 取出实际发送的 prompt
        实际请求 = mock_post.call_args
        实际prompt = 实际请求.kwargs["json"]["messages"][0]["content"]
        self.assertIn("张三", 实际prompt)
        self.assertIn("北京", 实际prompt)
        self.assertIn("Nh", 实际prompt)

    @patch('主程序.ner引擎.NER引擎._读取llm配置')
    @patch('requests.post')
    def test_无已知实体时不注入(self, mock_post, mock_配置):
        """不传 已知实体 时，prompt 应不含白名单段落"""
        mock_配置.return_value = {"mode": "online", "api_base": "http://test", "api_key": "k", "model": "m"}
        mock_post.return_value = self._构造mock_响应("[]")

        引擎 = NER引擎()
        引擎._调用llm("测试文本")

        实际prompt = mock_post.call_args.kwargs["json"]["messages"][0]["content"]
        self.assertNotIn("已识别", 实际prompt)
        self.assertNotIn("跳过", 实际prompt)


class Test解析黑名单过滤(unittest.TestCase):
    """_严格解析 / _兜底解析：黑名单过滤"""

    def test_严格解析_黑名单过滤(self):
        """白名单中的实体应被丢弃"""
        LLM_消息 = {
            "content": '[{"name": "张三", "type": "PERSON"}, {"name": "李四", "type": "PERSON"}]'
        }
        TYPE_MAP = {"PERSON": "Nh"}
        结果 = NER引擎._严格解析(
            LLM_消息, "张三和李四", TYPE_MAP, 黑名单={"张三"}
        )
        实体名列表 = [n for n, _ in 结果]
        self.assertNotIn("张三", 实体名列表)
        self.assertIn("李四", 实体名列表)

    def test_兜底解析_黑名单过滤(self):
        """白名单中的实体应被丢弃"""
        LLM_消息 = {
            "content": '[{"name": "北京", "type": "LOCATION"}, {"name": "上海", "type": "LOCATION"}]'
        }
        TYPE_MAP = {"LOCATION": "Ns"}
        结果 = NER引擎._兜底解析(
            LLM_消息, "北京和上海", TYPE_MAP, 黑名单={"北京"}
        )
        实体名列表 = [n for n, _ in 结果]
        self.assertNotIn("北京", 实体名列表)
        self.assertIn("上海", 实体名列表)

    def test_严格解析_无黑名单时不过滤(self):
        """不传黑名单时，所有合法实体都保留"""
        LLM_消息 = {
            "content": '[{"name": "张三", "type": "PERSON"}]'
        }
        TYPE_MAP = {"PERSON": "Nh"}
        结果 = NER引擎._严格解析(LLM_消息, "张三", TYPE_MAP)
        实体名列表 = [n for n, _ in 结果]
        self.assertIn("张三", 实体名列表)


if __name__ == '__main__':
    unittest.main()
