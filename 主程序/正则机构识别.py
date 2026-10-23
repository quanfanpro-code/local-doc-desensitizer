"""纯正则机构识别：不调用模型，用后缀正则认出机构全称并登记出现位置。"""
from __future__ import annotations

import re

from 主程序.识别结果 import 出现记录, 识别结果
from 主程序.ner引擎 import NER引擎, _取词典, 判断机构子类型

# 只借后缀正则与词典，构造引擎不会触发任何模型请求。
_引擎 = NER引擎()

_括号模式: re.Pattern | None = None
_噪声模式: re.Pattern | None = None
_行业词模式: re.Pattern | None = None


def _初始化清洗模式() -> None:
    """按词典编译清洗用正则；词典缺失时退回最小标记集，不崩溃。"""
    global _括号模式, _噪声模式
    if _噪声模式 is not None:
        return
    _括号模式 = re.compile(_取词典("括号正则", r'[（(][^）)]*[）)]'))
    词: list[str] = []
    for 键 in ("行政区划标记", "区域标记", "法律形式", "分支标记", "控股标记"):
        词.extend(_取词典(键, ["省", "市", "县"]))
    词.sort(key=len, reverse=True)
    _噪声模式 = re.compile("|".join(re.escape(w) for w in 词))


def _清洗实体名(名称: str) -> str:
    """去掉括号内容、行政标记与法律形式，得到去壳后的名称。"""
    _初始化清洗模式()
    结果 = _噪声模式.sub("", _括号模式.sub("", 名称))
    return 结果 if 结果.strip() else 名称


def _洗行业词(名称: str) -> str:
    """循环剥掉末尾行业词与地名，至少保留两个字。"""
    global _行业词模式
    if _行业词模式 is None:
        词 = list(_取词典("行业词", ["科技", "实业"])) + list(_取词典("地名", ["北京", "上海"]))
        词.sort(key=len, reverse=True)
        _行业词模式 = re.compile("(" + "|".join(re.escape(w) for w in 词) + ")$")
    while True:
        m = _行业词模式.search(名称)
        if m and len(名称) - len(m.group(1)) >= 2:
            名称 = 名称[: -len(m.group(1))]
        else:
            return 名称


def _脱壳简称(全称: str) -> list[str]:
    """从全称剥壳生成简称；公司、合伙企业再多剥一层行业词。"""
    简称列表: list[str] = []
    去壳 = _清洗实体名(全称)
    if 去壳 != 全称 and len(去壳) >= 2:
        简称列表.append(去壳)
        if 判断机构子类型(全称) in {"公司", "合伙企业"}:
            核心 = _洗行业词(去壳)
            if 核心 != 去壳 and len(核心) >= 2:
                简称列表.append(核心)
    return 简称列表


# "（以下简称“××”）"声明：作者亲口写出的简称，是纯正则能拿到的最可靠简称来源。
_声明模式 = re.compile(
    r'[（(]\s*以下简称\s*[:：]?\s*'
    r'["“‘「『]?([\u4e00-\u9fffA-Za-z0-9·\-.]{2,20})["”’」』]?\s*[）)]'
)


def 并入声明简称(块列表, 结果: 识别结果) -> None:
    """把括号前的机构全称与声明简称关联到同一机构。"""
    for b in 块列表:
        for m in _声明模式.finditer(b.原文):
            简称 = m.group(1)
            前文 = b.原文[: m.start()].rstrip().rstrip('"\'”’」』').rstrip()
            命中 = None
            for 编号, 机构 in 结果.机构.items():
                for 名称 in sorted(机构["names"], key=len, reverse=True):
                    if len(名称) >= 4 and 前文.endswith(名称):
                        命中 = 编号
                        break
                if 命中:
                    break
            if 命中 is None:
                # 文档里“（以下简称“本协议”）”这类声明与机构无关，静默跳过，不当作未完成
                continue
            if any(简称 in v["names"] and k != 命中 for k, v in 结果.机构.items()):
                结果.未完成.append({"块编号": b.编号, "环节": "简称声明",
                                    "原因": f"简称“{简称}”已归属其他机构"})
                continue
            if 简称 not in 结果.机构[命中]["names"]:
                结果.机构[命中]["names"].append(简称)


def 定位出现(块列表, 结果: 识别结果) -> None:
    """按机构表里的每个称呼，在各块中登记每一处出现。"""
    for b in 块列表:
        for 编号, 机构 in 结果.机构.items():
            for 名称 in 机构["names"]:
                for m in re.finditer(re.escape(名称), b.原文):
                    结果.出现.append(出现记录(
                        块编号=b.编号, 开始=m.start(), 结束=m.end(),
                        原词=名称, 类型="Ni", 机构编号=编号, 来源="正则"))


def 识别正则机构(块列表, 进度回调=None) -> 识别结果:
    """纯正则识别机构全称，登记机构表后定位全部出现。"""
    结果 = 识别结果()
    全称列表: list[str] = []
    for b in 块列表:
        for 名称, _类型 in _引擎._规则识别明显机构(b.原文):
            if 名称 not in 全称列表:
                全称列表.append(名称)
    for 序号, 全称 in enumerate(全称列表, 1):
        称呼 = [全称] + _脱壳简称(全称)
        结果.机构[f"正则机构{序号}"] = {
            "canonical": 全称, "names": list(dict.fromkeys(称呼)), "evidence": []}
        if 进度回调:
            进度回调(-1, -1, f"正则识别机构 {序号}/{len(全称列表)}")
    并入声明简称(块列表, 结果)
    定位出现(块列表, 结果)
    return 结果
