"""同一批虚构材料的真实端到端比较；输出不包含接口密钥。"""
import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--source', required=True)
p.add_argument('--output', required=True)
p.add_argument('--stress', type=int, default=0, help='默认只测三份小样例；大压力样例须明确指定重复次数')
p.add_argument('--reasoning', choices=['configured','disabled','low','high'], default='configured', help='仅评测时覆盖 DeepSeek 思考参数，不修改设置文件')
p.add_argument('--codex', action='store_true', help='用本机 Codex 订阅 gpt-6-luna/medium 替换模型请求边界，不改识别与解析')
args = p.parse_args()
sys.dont_write_bytecode = True
sys.path.insert(0, args.source)
from 主程序.脱敏处理器 import 脱敏处理器
from 主程序.ner引擎 import 全局映射表
from 主程序.识别结果 import 合并出现
import requests

out = Path(args.output)
out.mkdir(parents=True, exist_ok=False)
data_path = Path(args.source) / '开发测试/样例/机构识别标注.json'
data = json.loads(data_path.read_text(encoding='utf-8-sig'))['文档']
full, alias = '青岛禾舟运输有限公司', '蓝帆'
stress_blocks = [{'id': 'R0', 'text': f'{full}（以下简称{alias}）。'}]
stress_blocks += [{'id': f'R{i+1}', 'text': f'向{alias}支付运费。'} for i in range(args.stress)]
if args.stress > 0:
    data.append({'名称': f'重复简称{args.stress}次', '块': stress_blocks,
                 '标准': [['R0', full, 1, full], ['R0', alias, 1, full]] +
                         [[f'R{i+1}', alias, 1, full] for i in range(args.stress)]})
records = []
original_post = requests.post
def measured_post(*a, **kw):
    start = time.perf_counter()
    from urllib.parse import urlsplit
    payload = kw.get('json', {})
    if args.reasoning != 'configured':
        if not a or urlsplit(a[0]).hostname != 'api.deepseek.com':
            raise ValueError('思考参数覆盖仅用于 DeepSeek 官方接口')
        payload.pop('chat_template_kwargs', None)
        payload['thinking'] = {'type': 'disabled' if args.reasoning == 'disabled' else 'enabled'}
        if args.reasoning != 'disabled':
            payload['reasoning_effort'] = args.reasoning
    item = {'模型': payload.get('model'), '思考参数': payload.get('thinking'),
            '思考强度': payload.get('reasoning_effort'), '最大输出': payload.get('max_tokens'), '输入字符': sum(len(m['content']) for m in kw.get('json', {}).get('messages', []))}
    try:
        response = original_post(*a, **kw)
        item['状态码'] = response.status_code
        try:
            body = response.json()
            item['usage'] = body.get('usage', {})
            choice = body.get('choices', [{}])[0]
            item['回答'] = choice.get('message', {}).get('content', '')
            item['结束原因'] = choice.get('finish_reason')
        except (ValueError, IndexError):
            pass
        return response
    finally:
        item['耗时秒'] = round(time.perf_counter() - start, 4)
        records.append(item)
        print(f'请求 {len(records)} 完成：{item["耗时秒"]} 秒', flush=True)
requests.post = measured_post
if args.codex:
    from 维护工具.验证订阅模型 import 调用
    import 主程序.文档识别 as 文档识别
    def 订阅请求(引擎, 消息, 最大输出=8192):
        开始 = time.perf_counter()
        返回 = 调用(消息, 最大输出)
        item = {'模型': 'gpt-6-luna', '思考强度': 'medium', '最大输出': 最大输出,
                '回答': 返回.get('content', ''), '结束原因': 返回.get('_finish_reason'),
                'usage': 返回.get('_订阅回执'), '耗时秒': round(time.perf_counter() - 开始, 4)}
        records.append(item)
        print(f'请求 {len(records)} 完成：{item["耗时秒"]} 秒', flush=True)
        return 返回
    文档识别.请求模型 = 订阅请求
report = {'源目录': args.source, '评测思考覆盖': args.reasoning, '调用方式': 'codex订阅' if args.codex else 'requests', '标注哈希': hashlib.sha256(data_path.read_bytes()).hexdigest(), '文档': []}
for doc in data:
    records.clear()
    name = doc['名称']
    source = out / (name + '.txt')
    original_blocks = {b['id']: b['text'] * b.get('repeat', 1) for b in doc['块']}
    text = '\n'.join(original_blocks.values())
    source.write_text(text, encoding='utf-8-sig')
    before_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    block_ids = {key: f'text:{i}' for i, key in enumerate(original_blocks)}
    expected = {}
    for key, word, occurrence, entity in doc['标准']:
        match = list(re.finditer(re.escape(word), original_blocks[key]))[occurrence - 1]
        expected[(block_ids[key], match.start(), match.end())] = entity
    processor = 脱敏处理器(启用日期=False, 启用金额=False)
    captured = []
    identify = processor._ner.识别文档
    def capture(blocks, callback=None):
        result = identify(blocks, callback)
        captured.append((blocks, result))
        return result
    processor._ner.识别文档 = capture
    print('开始：' + name, flush=True)
    start = time.perf_counter()
    result = processor.处理文件列表([str(source)], str(out / name), print)
    elapsed = time.perf_counter() - start
    actual = {}
    if captured:
        blocks, detection = captured[0]
        hits, errors = 合并出现(blocks, detection.出现)
        for hit in hits:
            if hit.类型 not in {'Ni', 'Nh', 'Ns'}:
                continue
            entity = detection.机构.get(hit.机构编号, {})
            subject = (entity.get('canonical') or entity.get('names', [hit.原词])[0]) if hit.类型 == 'Ni' else hit.类型
            actual[(hit.块编号, hit.开始, hit.结束)] = subject
    restored = False
    if result.已生成文件 and result.映射表路径列表:
        mapping = 全局映射表()
        mapping.从文件加载(result.映射表路径列表[0])
        masked = Path(result.已生成文件[0]).read_text(encoding='utf-8-sig')
        restored = mapping.批量还原文本(masked) == text
    item = {'名称': name, '原文字数': len(text), '原件哈希': before_hash,
            '原件未变': hashlib.sha256(source.read_bytes()).hexdigest() == before_hash,
            '标准出现数': len(expected), '漏检': len(expected.keys() - actual.keys()),
            '误检': len(actual.keys() - expected.keys()),
            '错误关联': sum(actual[k] != expected[k] for k in actual.keys() & expected.keys()),
            '准确还原': restored, '完整成功': result.成功数 == 1, '耗时秒': round(elapsed, 4),
            '请求数': len(records), '请求': list(records), '未完成': result.未完成环节,
            '失败': result.失败文件,
            '漏检明细': [[list(k), expected[k]] for k in sorted(expected.keys() - actual.keys())],
            '误检明细': [[list(k), actual[k]] for k in sorted(actual.keys() - expected.keys())],
            '错误关联明细': [[list(k), expected[k], actual[k]] for k in actual.keys() & expected.keys() if actual[k] != expected[k]]}
    report['文档'].append(item)
    (out / f'{len(report["文档"])}_评测.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8-sig')
    print(json.dumps({k: v for k, v in item.items() if k not in {'请求', '漏检明细', '误检明细'}}, ensure_ascii=False), flush=True)
