"""按块生效协议：名称只替换其声明块内的出现；例外失败必须撤销默认命中。"""
import unittest
from unittest.mock import patch
from 主程序.ner引擎 import NER引擎
from 主程序.识别结果 import 文本块


class 按块识别测试(unittest.TestCase):
    def 识别(self, 块, 回答, **extra):
        engine = NER引擎()
        with patch.object(engine, '_请求文档模型', return_value={'content': 回答, **extra}) as 请求:
            result = engine.识别文档(块)
        return result, 请求

    def test_名称不扩展到未声明块(self):
        块 = [文本块('a', '成都远景机械有限公司简称远景。向远景付款。', {}),
              文本块('b', '行业发展远景较好。', {})]
        回答 = '机构\ta\t成都远景机械有限公司\t成都远景机械有限公司\t远景'
        result, 请求 = self.识别(块, 回答)
        self.assertFalse(result.未完成)
        self.assertEqual([(x.块编号, x.原词) for x in result.出现],
                         [('a', '成都远景机械有限公司'), ('a', '远景'), ('a', '远景')])
        self.assertEqual(请求.call_count, 1)

    def test_普通词块不声明即安全无需排除(self):
        块 = [文本块('a', '青岛禾舟运输有限公司简称小麦，向小麦付款。', {}),
              文本块('b', '采购小麦（粮食）。', {})]
        result, _ = self.识别(块, '机构\ta\t青岛禾舟运输有限公司\t青岛禾舟运输有限公司\t小麦')
        self.assertFalse(result.未完成)
        self.assertTrue(all(x.块编号 == 'a' for x in result.出现))
        self.assertEqual(len(result.出现), 3)

    def test_同块普通用法仍靠排除(self):
        块 = [文本块('p', '青岛禾舟运输有限公司简称小麦。向小麦付款，采购小麦（粮食）。', {})]
        result, _ = self.识别(块, '机构\tp\t青岛禾舟运输有限公司\t青岛禾舟运输有限公司\t小麦\n排除\tp\t采购【小麦】（粮食）')
        self.assertFalse(result.未完成)
        self.assertEqual([x.原词 for x in result.出现], ['青岛禾舟运输有限公司', '小麦', '小麦'])

    def test_同块多主体归属与普通词排除(self):
        块 = [文本块('a', '甲公司和乙公司都简称晨星。晨星交图，晨星收款，天上的晨星。', {})]
        回答 = ('机构\ta\t甲公司\t甲公司\t晨星\n机构\ta\t乙公司\t乙公司\t晨星\n'
                '归属\ta\t【晨星】交图\t甲公司\n归属\ta\t【晨星】收款\t乙公司\n排除\ta\t天上的【晨星】')
        result, _ = self.识别(块, 回答)
        self.assertTrue(result.未完成)
        self.assertEqual(len(result.出现), 4)
        self.assertEqual(len(result.普通位置), 1)

    def test_无效排除摘录撤销该块该词默认命中(self):
        块 = [文本块('a', '海城远景有限公司简称远景。行业发展远景较好。', {})]
        回答 = '机构\ta\t海城远景有限公司\t海城远景有限公司\t远景\n排除\ta\t行业发【展远景】较好'
        result, _ = self.识别(块, 回答)
        self.assertTrue(result.未完成)
        self.assertEqual([(x.块编号, x.原词) for x in result.出现],
                         [('a', '海城远景有限公司')])

    def test_无效归属也撤销该块该词(self):
        块 = [文本块('a', '甲公司简称晨星，晨星交图。', {})]
        回答 = '机构\ta\t甲公司\t甲公司\t晨星\n归属\ta\t【晨星】交图\t不存在的主体'
        result, _ = self.识别(块, 回答)
        self.assertTrue(result.未完成)
        self.assertEqual([x.原词 for x in result.出现], ['甲公司'])

    def test_块编号无法确定时整批该词撤销(self):
        块 = [文本块('a', '甲公司简称晨星。', {}), 文本块('b', '乙公司简称晨星。', {})]
        回答 = '机构\ta\t甲公司\t甲公司\t晨星\n机构\tb\t乙公司\t乙公司\t晨星\n排除\t不存在的块\t【晨星】'
        result, _ = self.识别(块, 回答)
        self.assertTrue(result.未完成)
        self.assertEqual([x.原词 for x in result.出现], ['甲公司', '乙公司'])
        self.assertFalse(any(x.原词 == '晨星' for x in result.出现))

    def test_未完成行标记位置不替换(self):
        块 = [文本块('a', '某机构简称晨星，晨星交图。', {}),
              文本块('b', '晨星收款。', {})]
        回答 = '机构\ta\t某机构\t某机构\t晨星\n未完成\tb\t【晨星】'
        result, _ = self.识别(块, 回答)
        self.assertTrue(any('未完成' in str(u.get('原因', '')) + str(u.get('环节', '')) for u in result.未完成))
        self.assertTrue(all(x.块编号 == 'a' for x in result.出现))

    def test_跨批无全称代称在后文补足关系(self):
        填充 = ''.join(f'普通业务记录{i}。' for i in range(3000))
        块 = [文本块('a', '向BlueX付款。', {}), 文本块('middle', 填充, {}),
              文本块('b', '海城蓝星有限公司英文代称BlueX。', {})]
        engine = NER引擎()
        def 回答(messages, 最大输出=8192):
            text = messages[-1]['content'].split('文档资料：\n', 1)[1]
            return {'content': '机构\tb\t海城蓝星有限公司\t海城蓝星有限公司\tBlueX' if '[b]' in text
                    else '机构\ta\t-\tBlueX' if '[a]' in text else '无'}
        with patch.object(engine, '_请求文档模型', side_effect=回答):
            result = engine.识别文档(块)
        self.assertFalse(result.未完成)
        self.assertEqual(len(result.出现), 3)
        self.assertTrue(all(result.机构[x.机构编号]['canonical'] == '海城蓝星有限公司' for x in result.出现))

    def test_连续重复块声明一次全部展开(self):
        块 = [文本块('a', '青岛禾舟运输有限公司简称小麦。', {})]
        块 += [文本块(f'p{i}', '向小麦付款。', {}) for i in range(100)]
        result, 请求 = self.识别(块, '机构\ta\t青岛禾舟运输有限公司\t青岛禾舟运输有限公司\t小麦\n机构\tp0\t青岛禾舟运输有限公司\t小麦')
        self.assertFalse(result.未完成)
        self.assertEqual(len(result.出现), 102)
        self.assertEqual(请求.call_count, 1)

    def test_人名地址按块登记(self):
        块 = [文本块('a', '经办人张岚。', {}), 文本块('b', '提到张岚负责。地址锦云路88号。', {})]
        result, _ = self.识别(块, '人名\ta\t张岚\n人名\tb\t张岚\n地址\tb\t锦云路88号')
        self.assertFalse(result.未完成)
        self.assertEqual([(x.块编号, x.类型) for x in result.出现], [('a', 'Nh'), ('b', 'Nh'), ('b', 'Ns')])

    def test_全称在本块出现也写入称呼列(self):
        块 = [文本块('a', '成都星河科技有限公司（以下简称星河）承接项目。', {}),
              文本块('b', '星河交付。', {})]
        result, _ = self.识别(块, '机构\ta\t成都星河科技有限公司\t成都星河科技有限公司\t星河\n机构\tb\t成都星河科技有限公司\t星河')
        self.assertFalse(result.未完成)
        self.assertEqual(len(result.出现), 3)
        主体 = {result.机构[x.机构编号]['canonical'] for x in result.出现}
        self.assertEqual(主体, {'成都星河科技有限公司'})

    def test_模型漏写全称时本地补登记(self):
        块 = [文本块('a', '成都星河科技有限公司（以下简称星河）承接项目，星河交付。', {})]
        result, _ = self.识别(块, '机构\ta\t成都星河科技有限公司\t星河')
        self.assertFalse(result.未完成)
        self.assertEqual([(x.开始, x.原词) for x in result.出现],
                         [(0, '成都星河科技有限公司'), (15, '星河'), (23, '星河')])

    def test_其他块全称在本块出现时补登记(self):
        块 = [文本块('a', '成都星河科技有限公司（以下简称星河）供货。', {}),
              文本块('b', '成都星河科技有限公司的子公司负责检修。', {}),
              文本块('c', '子公司成都星河运维有限公司负责检修。', {})]
        result, _ = self.识别(块, '机构\ta\t成都星河科技有限公司\t成都星河科技有限公司\t星河\n机构\tc\t成都星河运维有限公司\t成都星河运维有限公司')
        self.assertFalse(result.未完成)
        按块 = {}
        for x in result.出现:
            按块.setdefault(x.块编号, []).append(x.原词)
        self.assertEqual(按块['a'], ['成都星河科技有限公司', '星河'])
        self.assertEqual(按块['b'], ['成都星河科技有限公司'])
        self.assertEqual(按块['c'], ['成都星河运维有限公司'])

    def test_占位无字样不产生未完成(self):
        result, _ = self.识别([文本块('a', '本期经营正常。', {})], '人名\t无。\n地址\t无')
        self.assertFalse(result.未完成)
        self.assertFalse(result.出现)

    def test_称呼不在声明块中即报未完成(self):
        块 = [文本块('a', '甲公司简称晨星。', {}), 文本块('b', '乙公司事项。', {})]
        result, _ = self.识别(块, '机构\ta\t甲公司\t甲公司\t乙公司')
        self.assertTrue(result.未完成)
        self.assertFalse(any(x.原词 == '乙公司' for x in result.出现))

    def test_表头与占位行跳过(self):
        result, 请求 = self.识别([文本块('a', '本期经营正常。', {})],
            '机构\t块编号\t全称\t本块称呼1\t本块称呼2\n人名\t-\n地址\t-\t\n无')
        self.assertFalse(result.未完成)
        self.assertFalse(result.出现)
        self.assertEqual(请求.call_count, 1)


if __name__ == '__main__':
    unittest.main()
