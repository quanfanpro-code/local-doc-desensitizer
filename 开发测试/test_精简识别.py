"""精简回答必须保持每处命中、歧义边界及错误可见。"""
import unittest
from unittest.mock import patch
from 主程序.ner引擎 import NER引擎, 全局映射表
from 主程序.识别结果 import 文本块, 按位置替换
from 主程序.定位写回 import 准备替换


class 精简识别测试(unittest.TestCase):
    def 识别(self, 块, 回答, **extra):
        engine = NER引擎()
        with patch.object(engine, '_请求文档模型', return_value={'content': 回答, **extra}) as 请求:
            result = engine.识别文档(块)
        return result, 请求

    def test_千次简称只问一次且全部替换还原(self):
        原文 = '青岛禾舟运输有限公司（以下简称蓝帆）。' + '向蓝帆支付运费。' * 1000
        块 = [文本块('p', 原文, {})]
        结果, 请求 = self.识别(块, '机构\tp\t青岛禾舟运输有限公司\t青岛禾舟运输有限公司\t蓝帆')
        self.assertEqual(len(结果.出现), 1002)
        self.assertFalse(结果.未完成)
        self.assertEqual(请求.call_count, 1)
        映射 = 全局映射表()
        替换 = 准备替换(块, 结果, 映射)
        脱敏 = 按位置替换(原文, 替换['p'])
        self.assertNotIn('蓝帆', 脱敏)
        self.assertEqual(映射.批量还原文本(脱敏), 原文)

    def test_同块普通词仅排除指定摘录(self):
        块 = [文本块('p', '青岛禾舟运输有限公司简称小麦。向小麦付款，采购小麦（粮食）。', {})]
        result, _ = self.识别(块, '机构\tp\t青岛禾舟运输有限公司\t青岛禾舟运输有限公司\t小麦\n排除\tp\t采购【小麦】（粮食）')
        self.assertFalse(result.未完成)
        self.assertEqual([m.原词 for m in result.出现], ['青岛禾舟运输有限公司', '小麦', '小麦'])

    def test_同名两主体分别归属不合并(self):
        块 = [文本块('a', '北京澄川设计有限公司简称晨星，晨星交图。', {}),
              文本块('b', '苏州清衡施工有限公司简称晨星，晨星收款。', {}),
              文本块('c', '天空中的晨星。', {})]
        answer = '机构\ta\t北京澄川设计有限公司\t北京澄川设计有限公司\t晨星\n机构\tb\t苏州清衡施工有限公司\t苏州清衡施工有限公司\t晨星\n归属\ta\t【晨星】\t北京澄川设计有限公司\n归属\tb\t【晨星】\t苏州清衡施工有限公司'
        result, _ = self.识别(块, answer)
        self.assertFalse(result.未完成)
        self.assertEqual(len(result.出现), 6)
        for m in result.出现:
            self.assertEqual(result.机构[m.机构编号]['canonical'], '北京澄川设计有限公司' if m.块编号 == 'a' else '苏州清衡施工有限公司')

    def test_一字简称不误改词内普通字(self):
        result, _ = self.识别([文本块('p', '青岛禾舟物流有限公司代称舟。舟负责承运；江边一叶扁舟。', {})],
            '机构\tp\t青岛禾舟物流有限公司\t青岛禾舟物流有限公司\t舟\n排除\tp\t扁【舟】')
        self.assertFalse(result.未完成)
        self.assertEqual(len(result.出现), 3)

    def test_人名地址和合法空结果(self):
        块 = [文本块('p', '经办人张岚，地址锦云路88号。', {})]
        result, _ = self.识别(块, '人名\tp\t张岚\n地址\tp\t锦云路88号')
        self.assertEqual([m.类型 for m in result.出现], ['Nh', 'Ns'])
        self.assertFalse(result.未完成)
        empty, _ = self.识别([文本块('p', '本期业务正常。', {})], '无')
        self.assertFalse(empty.出现)
        self.assertFalse(empty.未完成)

    def test_错误行保留有效行并且不整批重试(self):
        result, request = self.识别([文本块('p', '经办人张岚。', {})], '人名\tp\t张岚\n人名\tp\t不存在的姓名')
        self.assertEqual([m.原词 for m in result.出现], ['张岚'])
        self.assertTrue(result.未完成)
        self.assertEqual(request.call_count, 1)

    def test_截断和空白不能当成功(self):
        for answer, extra in [('', {}), ('人名\tp\t张岚\n', {'_finish_reason': 'length'})]:
            result, request = self.识别([文本块('p', '经办人张岚。', {})], answer, **extra)
            self.assertTrue(result.未完成)
            self.assertEqual(request.call_count, 1)

    def test_连续重复块例外映回每个位置(self):
        块 = [文本块('a', '青岛禾舟运输有限公司简称小麦。', {})]
        块 += [文本块(f'p{i}', '向小麦付款，采购小麦（粮食）。', {}) for i in range(100)]
        result, request = self.识别(块, '机构\ta\t青岛禾舟运输有限公司\t青岛禾舟运输有限公司\t小麦\n机构\tp0\t青岛禾舟运输有限公司\t小麦\n排除\tp0\t采购【小麦】（粮食）')
        self.assertFalse(result.未完成)
        self.assertEqual(len(result.出现), 102)
        self.assertEqual(request.call_count, 1)

    def test_普通数值格无需模型(self):
        for 类型 in ('n', 'f'):
            with self.subTest(类型=类型):
                result, request = self.识别([文本块('n', '12345.60', {}, 数据类型=类型)], '无')
                self.assertFalse(result.未完成)
                self.assertEqual(request.call_count, 0)

    def test_共享上下文只发送和计入批次一次(self):
        from 主程序.文档识别 import _准备输入
        context = '本表列示普通业务记录。' * 80
        blocks = [文本块(f'p{i}', f'第{i}项业务正常。', {}, 上下文=context) for i in range(100)]
        batches = _准备输入(blocks)
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0][0].count(context[:1000]), 1)
        self.assertEqual(len(batches[0][1]), 100)

    def test_不接受不存在的例外摘录(self):
        result, _ = self.识别([文本块('p', '向小麦付款。', {})], '机构\tp\t-\t小麦\n排除\tp\t采购【小麦】（粮食）')
        self.assertTrue(result.未完成)
        # 摘录无效说明模型判断自相矛盾，撤销默认命中，宁可不替换也不误伤。
        self.assertEqual(len(result.出现), 0)

    def test_后批简称不能误改前批普通用法(self):
        填充 = ''.join(f'普通业务记录{i}。' for i in range(3000))
        块 = [文本块('a', '采购小麦（粮食）。' + 填充, {}),
              文本块('b', '青岛禾舟运输有限公司简称小麦，小麦承运。', {})]
        engine = NER引擎()
        def 回答(messages, 最大输出=8192):
            return {'content': '机构\tb\t青岛禾舟运输有限公司\t青岛禾舟运输有限公司\t小麦' if '[b]' in messages[-1]['content'] else '无'}
        with patch.object(engine, '_请求文档模型', side_effect=回答):
            result = engine.识别文档(块)
        self.assertFalse(result.未完成)
        self.assertEqual(len(result.出现), 3)
        self.assertTrue(all(m.块编号 == 'b' for m in result.出现))

    def test_跨批无全称代称在后文补足关系(self):
        填充 = ''.join(f'普通业务记录{i}。' for i in range(3000))
        块 = [文本块('a', '向BlueX付款。', {}), 文本块('middle', 填充, {}),
              文本块('b', '海城蓝星有限公司英文代称BlueX。', {})]
        engine = NER引擎()
        def 回答(messages, 最大输出=8192):
            text = messages[-1]['content'].split('文档资料：\n', 1)[1]
            return {'content': '机构\tb\t海城蓝星有限公司\t海城蓝星有限公司\tBlueX' if '[b]' in text else '机构\ta\t-\tBlueX' if '[a]' in text else '无'}
        with patch.object(engine, '_请求文档模型', side_effect=回答):
            result = engine.识别文档(块)
        self.assertFalse(result.未完成)
        self.assertEqual(len(result.出现), 3)
        self.assertTrue(all(result.机构[m.机构编号]['canonical'] == '海城蓝星有限公司' for m in result.出现))

    def test_未知归属不能当成功(self):
        result, _ = self.识别([文本块('a', '向小麦付款。', {})], '归属\ta\t【小麦】\t不存在公司')
        self.assertTrue(result.未完成)

    def test_字面转义制表符仍可读取(self):
        result, _ = self.识别([文本块('a', '张岚经办。', {})], r'人名\ta\t张岚')
        self.assertFalse(result.未完成)
        self.assertEqual([m.原词 for m in result.出现], ['张岚'])

    def test_空简称占位及唯一编号省略前缀(self):
        块 = [文本块('text:0', '青岛禾舟运输有限公司简称小麦，向小麦付款，采购小麦（粮食）。', {}),
              文本块('text:1', '无关内容。', {})]
        result, _ = self.识别(块, '机构\ttext:0\t青岛禾舟运输有限公司\t青岛禾舟运输有限公司\t小麦\t-\n排除\t0\t采购【小麦】（粮食）')
        self.assertFalse(result.未完成)
        self.assertEqual(len(result.出现), 3)

    def test_DeepSeek官方接口使用低强度单轮思考(self):
        import requests
        engine = NER引擎()
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"choices":[{"message":{"content":"none"},"finish_reason":"stop"}]}'
        with patch.object(engine, '_读取llm配置', return_value={'api_base':'https://api.deepseek.com/v1','model':'deepseek-flash'}), patch('requests.post', return_value=response) as post:
            engine._请求文档模型([])
        self.assertEqual(post.call_args.kwargs['json'].get('thinking'), {'type':'enabled'})
        self.assertEqual(post.call_args.kwargs['json'].get('reasoning_effort'), 'low')
        self.assertNotIn('chat_template_kwargs', post.call_args.kwargs['json'])

    def test_块内唯一归属沿用而无归属不能猜(self):
        块 = [文本块('a', '北方甲公司在设计合同中简称晨星，晨星交图。', {}),
              文本块('b', '南方乙公司在施工合同中也简称晨星。晨星收款。', {})]
        answer = '机构\ta\t北方甲公司\t北方甲公司\t晨星\n机构\tb\t南方乙公司\t南方乙公司\t晨星\n归属\ta\t【晨星】交图\t北方甲公司\n归属\tb\t【晨星】收款\t南方乙公司'
        result, _ = self.识别(块, answer)
        self.assertFalse(result.未完成)
        self.assertEqual(len(result.出现), 6)
        # 分块声明后各块简称不再冲突，缺归属行也能按块内唯一主体定位。
        分块声明, _ = self.识别(块, '\n'.join(answer.splitlines()[:2]))
        self.assertFalse(分块声明.未完成)
        self.assertEqual(len(分块声明.出现), 6)
        # 同块内两家机构争同一简称且无归属行时不能猜。
        同块 = [文本块('a', '甲公司和乙公司都简称晨星，晨星交图。', {})]
        uncertain, _ = self.识别(同块, '机构\ta\t甲公司\t甲公司\t晨星\n机构\ta\t乙公司\t乙公司\t晨星')
        self.assertTrue(uncertain.未完成)
        self.assertEqual(len(uncertain.出现), 2)

    def test_同块多归属不扩大例外且普通词优先(self):
        块 = [文本块('a', '甲公司和乙公司都简称晨星。晨星交图，晨星收款，天上的晨星。', {})]
        answer = '机构\ta\t甲公司\t甲公司\t晨星\n机构\ta\t乙公司\t乙公司\t晨星\n归属\ta\t【晨星】交图\t甲公司\n归属\ta\t【晨星】收款\t乙公司\n排除\ta\t天上的【晨星】'
        result, _ = self.识别(块, answer)
        self.assertTrue(result.未完成)
        self.assertEqual(len(result.出现), 4)
        self.assertEqual(len(result.普通位置), 1)

    def test_多余清单表头直接略过(self):
        result, request = self.识别([文本块('a', '甲公司简称小麦。', {})], '机构\t块编号\t全称\t本块称呼1\t本块称呼2\n机构\ta\t甲公司\t甲公司\t小麦')
        self.assertFalse(result.未完成)
        self.assertEqual(len(result.出现), 2)
        self.assertEqual(request.call_count, 1)

    def test_空类别占位不触发重问(self):
        result, request = self.识别([文本块('a', '本期经营正常。', {})], '人名\t-\n地址\t-\t')
        self.assertFalse(result.未完成)
        self.assertFalse(result.出现)
        self.assertEqual(request.call_count, 1)

    def test_同一摘录多个标记逐处定位(self):
        块 = [文本块('a', '北方甲公司简称晨星，晨星交图。', {}),
              文本块('b', '南方乙公司简称晨星，晨星收款。', {})]
        answer = '机构\ta\t北方甲公司\t北方甲公司\t晨星\n机构\tb\t南方乙公司\t南方乙公司\t晨星\n归属\ta\t简称【晨星】，【晨星】交图\t北方甲公司\n归属\tb\t简称【晨星】，【晨星】收款\t南方乙公司'
        result, request = self.识别(块, answer)
        self.assertFalse(result.未完成)
        self.assertEqual(len(result.出现), 6)
        self.assertEqual(request.call_count, 1)

    def test_取消不再发起请求(self):
        engine = NER引擎()
        engine._取消检查 = lambda: True
        with patch.object(engine, '_请求文档模型', side_effect=AssertionError('取消后不应请求')):
            result = engine.识别文档([文本块('a', '张岚经办。', {})])
        self.assertTrue(result.未完成)
        self.assertFalse(result.已核对块)

    def test_例外框错词不能假装完成(self):
        块 = [文本块('a', '海城远景有限公司简称远景。行业发展远景较好。', {})]
        result, request = self.识别(块, '机构\ta\t海城远景有限公司\t海城远景有限公司\t远景\n排除\ta\t行业发【展远景】较好')
        self.assertTrue(result.未完成)
        self.assertEqual(request.call_count, 1)

    def test_同形简称跨批各自归属(self):
        填充 = ''.join(f'普通业务记录{i}。' for i in range(3000))
        块 = [文本块('a', '北方甲公司简称晨星，晨星交图。', {}), 文本块('middle', 填充, {}),
              文本块('b', '南方乙公司简称晨星，晨星收款。', {})]
        engine = NER引擎()
        def 回答(messages, 最大输出=8192):
            text = messages[-1]['content'].split('文档资料：\n', 1)[1]
            return {'content': '机构\tb\t南方乙公司\t南方乙公司\t晨星' if '[b]' in text else '机构\ta\t北方甲公司\t北方甲公司\t晨星' if '[a]' in text else '无'}
        with patch.object(engine, '_请求文档模型', side_effect=回答):
            result = engine.识别文档(块)
        self.assertFalse(result.未完成)
        self.assertEqual(len(result.出现), 6)
        for m in result.出现:
            self.assertEqual(result.机构[m.机构编号]['canonical'], '北方甲公司' if m.块编号 == 'a' else '南方乙公司')


if __name__ == '__main__':
    unittest.main()
