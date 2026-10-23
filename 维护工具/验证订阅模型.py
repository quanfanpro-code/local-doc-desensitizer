"""经本机 Codex CLI 订阅调用 gpt-6-luna；干净环境隔离全局指令，只发送给定消息。

接口与 NER引擎._请求文档模型 相同：入参消息列表，返回含 content 与完成原因的消息字典。
额外通过 引擎.请求记录 或本模块 最近回执 提供模型身份与真实用量证据。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

CODEX = Path.home() / '.codex' / '.sandbox-bin' / 'codex.exe'
模型 = 'gpt-6-luna'
强度 = 'medium'
最近回执: dict = {}


def 准备干净环境() -> Path:
    """独立 CODEX_HOME：只带登录凭据，不带全局指令、记忆或技能清单。"""
    环境目录 = Path(tempfile.gettempdir()) / 'codex脱敏验证环境'
    环境目录.mkdir(parents=True, exist_ok=True)
    来源 = Path.home() / '.codex' / 'auth.json'
    if not 来源.exists():
        raise RuntimeError('本机未找到 Codex 登录凭据（~/.codex/auth.json）')
    shutil.copyfile(来源, 环境目录 / 'auth.json')
    return 环境目录


def 组装提示(消息: list) -> str:
    """把消息列表拼成单一提示；system 在前、user 在后，逐字保留。"""
    部件 = []
    for m in 消息:
        角色 = m.get('role', 'user')
        内容 = m.get('content', '')
        if 角色 == 'system':
            部件.append('按以下系统要求处理资料，直接输出要求的结果：\n<系统要求>\n' + 内容 + '\n</系统要求>')
        else:
            部件.append('<资料>\n' + 内容 + '\n</资料>')
    return '\n\n'.join(部件)


def 解析事件(行列表: list[str]) -> dict:
    """从 codex exec 的 JSONL 事件提取最终回答、结束原因与用量；缺失记 None。"""
    回答, 结束原因, 用量 = '', None, None
    for 行 in 行列表:
        try:
            事件 = json.loads(行)
        except ValueError:
            continue
        类型 = 事件.get('type') or 事件.get('msg', {}).get('type')
        if 类型 == 'item.completed':
            条目 = 事件.get('item', {})
            if 条目.get('type') == 'agent_message' or 条目.get('item_type') == 'agent_message':
                回答 = ''.join(条目.get('text') or '') or 回答
        elif 类型 == 'turn.completed':
            用量 = 事件.get('usage')
            结束原因 = 'stop'
        elif 类型 == 'turn.failed' or 类型 == 'error':
            结束原因 = 'error:' + json.dumps(事件, ensure_ascii=False)[:200]
    return {'回答': 回答, '结束原因': 结束原因, '用量': 用量}


def 整理回执(模型: str, 强度: str, 用量) -> dict:
    """只整理已取得的元数据，不伪造服务端未返回的证明；缺失字段如实标注。"""
    回执 = {'模型': 模型, '强度': 强度, '思考token': None, '用量状态': '不可得'}
    if isinstance(用量, dict):
        各项 = {}
        for 键 in ('input_tokens', 'cached_input_tokens', 'output_tokens', 'total_tokens',
                   'reasoning_output_tokens', 'output_tokens_details'):
            if 用量.get(键) is not None:
                各项[键] = 用量[键]
        if 各项:
            回执.update(各项)
            回执['思考token'] = 用量.get('reasoning_output_tokens')
            回执['用量状态'] = '已取得'
    return 回执


def 调用(消息: list, 最大输出: int = 8192) -> dict:
    """一次真实订阅调用。返回值兼容 请求模型 的消息字典格式。"""
    if not CODEX.exists():
        raise RuntimeError(f'未找到 Codex CLI：{CODEX}')
    环境目录 = 准备干净环境()
    工作目录 = 环境目录 / '空工作区'
    工作目录.mkdir(exist_ok=True)
    回答文件 = 环境目录 / '最终回答.txt'
    回答文件.unlink(missing_ok=True)
    提示 = 组装提示(消息)
    (环境目录 / '请求正文.txt').write_text(提示, encoding='utf-8')
    import hashlib
    请求哈希 = hashlib.sha256(提示.encode('utf-8')).hexdigest()
    命令 = [str(CODEX), 'exec',
            '--ephemeral', '--skip-git-repo-check', '--ignore-user-config', '--ignore-rules',
            '--sandbox', 'read-only', '-C', str(工作目录),
            '-m', 模型, '-c', f'model_reasoning_effort="{强度}"',
            '--json', '-o', str(回答文件), '-']
    环境变量 = dict(os.environ, CODEX_HOME=str(环境目录), RUST_LOG='error')
    开始 = time.monotonic()
    进程 = subprocess.run(命令, input=提示, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', env=环境变量, timeout=900)
    耗时 = round(time.monotonic() - 开始, 3)
    行列表 = 进程.stdout.splitlines()
    (环境目录 / f'事件流_{time.strftime("%H%M%S")}.jsonl').write_text(进程.stdout, encoding='utf-8')
    摘要 = 解析事件(行列表)
    if 进程.returncode != 0 and not 摘要['回答']:
        raise RuntimeError('codex exec 失败（退出码 %d）：%s' % (进程.returncode, 进程.stderr[-800:]))
    回答 = 回答文件.read_text(encoding='utf-8').strip() if 回答文件.exists() else 摘要['回答']
    global 最近回执
    最近回执 = 整理回执(模型, 强度, 摘要['用量']) | {'耗时秒': 耗时, '请求哈希': 请求哈希}
    return {'content': 回答, '_finish_reason': 摘要['结束原因'], '_订阅回执': 最近回执}


if __name__ == '__main__':
    import sys
    结果 = 调用([{'role': 'user', 'content': sys.argv[1] if len(sys.argv) > 1 else '只回复：入口正常'}])
    print(json.dumps({'content': 结果['content'], '回执': 最近回执}, ensure_ascii=False, indent=2))
