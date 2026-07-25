from __future__ import annotations

from docx.oxml.ns import qn


def 收集文档全部部件(doc):
    部件列表 = [doc.element]
    for rel in doc.part.rels.values():
        try:
            target = rel.target_part
            if not hasattr(target, 'element'):
                continue
            reltype = rel.reltype
            if "header" in reltype or "footer" in reltype or "footnotes" in reltype or "endnotes" in reltype:
                部件列表.append(target.element)
        except Exception:
            continue
    # 多节文档可能有独立的页眉页脚不在 rels 中暴露
    try:
        for section in doc.sections:
            for 部件名 in ('header', 'footer'):
                部件 = getattr(section, 部件名, None)
                if 部件 is not None:
                    elem = getattr(部件, '_element', None)
                    if elem is not None and elem not in 部件列表:
                        部件列表.append(elem)
    except Exception:
        pass
    return 部件列表


def 替换部件文本(部件根元素, 替换函数):
    for 段落 in 部件根元素.iter(qn('w:p')):
        _替换段落文本(段落, 替换函数)


def _替换段落文本(段落元素, 替换函数):
    """对单个段落执行段落级文本替换，解决跨 w:r 分片的匹配问题"""
    运行列表 = []
    for run in 段落元素.iter(qn('w:r')):
        t_elem = run.find(qn('w:t'))
        if t_elem is not None and t_elem.text:
            运行列表.append((run, t_elem, t_elem.text))
    if not 运行列表:
        return
    原文 = ''.join(t for _, _, t in 运行列表)
    if not 原文.strip():
        return
    替换后 = 替换函数(原文)
    if 替换后 == 原文:
        return
    _分配文本到运行(运行列表, 替换后)


def _分配文本到运行(运行列表, 替换后文本):
    """将替换后的整段文本按原运行长度比例分配回各 w:r 的 w:t 中"""
    原文总长 = sum(len(t) for _, _, t in 运行列表)
    if 原文总长 == 0:
        return
    pos = 0
    替换总长 = len(替换后文本)
    n = len(运行列表)
    for i, (run, t_elem, orig_text) in enumerate(运行列表):
        if i == n - 1:
            t_elem.text = 替换后文本[pos:]
        else:
            proportion = len(orig_text) / 原文总长
            chunk_len = max(1, int(替换总长 * proportion))
            remaining_runs = n - i - 1
            chunk_len = min(chunk_len, 替换总长 - pos - remaining_runs)
            t_elem.text = 替换后文本[pos:pos + chunk_len]
            pos += chunk_len


def 提取部件文本(部件根元素) -> list[str]:
    文本列表: list[str] = []
    for 段落元素 in 部件根元素.iter(qn('w:p')):
        片段 = []
        for 文本节点 in 段落元素.iter(qn('w:t')):
            if 文本节点.text:
                片段.append(文本节点.text)
        段落文本 = "".join(片段).strip()
        if 段落文本:
            文本列表.append(段落文本)
    return 文本列表
