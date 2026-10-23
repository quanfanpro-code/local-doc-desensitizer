"""订阅验证入口的离线边界：输入隔离、用量如实、事件解析。不发真实请求。"""
import unittest


class 订阅验证边界测试(unittest.TestCase):
    def test_用量缺失不得写成零(self):
        from 维护工具.验证订阅模型 import 整理回执
        回执 = 整理回执(模型='gpt-6-luna', 强度='medium', 用量=None)
        self.assertIsNone(回执['思考token'])
        self.assertEqual(回执['用量状态'], '不可得')

    def test_用量完整时如实登记(self):
        from 维护工具.验证订阅模型 import 整理回执
        回执 = 整理回执(模型='gpt-6-luna', 强度='medium',
                    用量={'input_tokens': 1200, 'cached_input_tokens': 300,
                          'output_tokens': 800, 'reasoning_output_tokens': 640})
        self.assertEqual(回执['思考token'], 640)
        self.assertEqual(回执['input_tokens'], 1200)
        self.assertEqual(回执['用量状态'], '已取得')

    def test_组装提示只含给定消息不带全局内容(self):
        from 维护工具.验证订阅模型 import 组装提示
        消息 = [{'role': 'system', 'content': '识别资料中的机构。'},
                {'role': 'user', 'content': '经办人张岚。'}]
        提示 = 组装提示(消息)
        self.assertIn('识别资料中的机构', 提示)
        self.assertIn('经办人张岚', 提示)
        for 哨兵 in ('喵', 'AGENTS', '技能', 'ponytail'):
            self.assertNotIn(哨兵, 提示, f'提示混入了全局内容：{哨兵}')

    def test_解析事件提取回答用量与失败(self):
        from 维护工具.验证订阅模型 import 解析事件
        行 = ['{"type":"item.completed","item":{"type":"agent_message","text":"机构\\t甲公司"}}',
              '{"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":40}}']
        摘要 = 解析事件(行)
        self.assertEqual(摘要['回答'], '机构\t甲公司')
        self.assertEqual(摘要['用量']['output_tokens'], 40)
        self.assertNotEqual(摘要['结束原因'], 'length', '正常完成不得误报截断')
        失败 = 解析事件(['{"type":"turn.failed","error":"stream error"}'])
        self.assertTrue(str(失败['结束原因']).startswith('error'))

    def test_组装提示逐字保留资料(self):
        from 维护工具.验证订阅模型 import 组装提示
        资料 = '成都远景机械有限公司简称远景。' * 200
        提示 = 组装提示([{'role': 'system', 'content': 'S'}, {'role': 'user', 'content': 资料}])
        self.assertIn(资料, 提示)


if __name__ == '__main__':
    unittest.main()
