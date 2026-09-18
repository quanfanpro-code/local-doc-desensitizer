"""识别与文件写回共同使用的原文位置。"""
from dataclasses import dataclass, field


@dataclass
class 文本块:
    编号: str
    原文: str
    位置: dict
    上下文: str = ""
    原值: object = None
    数据类型: str = "text"


@dataclass
class 出现记录:
    块编号: str
    开始: int
    结束: int
    原词: str
    类型: str
    机构编号: str | None = None
    来源: str = "模型"
    替换值: str | None = None


@dataclass
class 识别结果:
    机构: dict = field(default_factory=dict)
    出现: list[出现记录] = field(default_factory=list)
    已核对块: set[str] = field(default_factory=set)
    未完成: list[dict] = field(default_factory=list)
    普通位置: set[tuple[str, int, int]] = field(default_factory=set)


def 按位置替换(原文: str, 替换: list[tuple[int, int, str]]) -> str:
    有序 = sorted(替换)
    上次结束 = 0
    for 开始, 结束, 代号 in 有序:
        if not 0 <= 开始 < 结束 <= len(原文) or 开始 < 上次结束:
            raise ValueError("替换位置越界或重叠")
        上次结束 = 结束
    for 开始, 结束, 代号 in reversed(有序):
        原文 = 原文[:开始] + 代号 + 原文[结束:]
    return 原文


def 合并出现(块列表, 出现列表):
    """验证原词，去重，完整名称优先；相同位置不同主体不擅自选择。"""
    块表 = {b.编号: b for b in 块列表}
    结果, 错误, 冲突位置 = [], [], set()
    for item in sorted(出现列表, key=lambda x: (x.块编号, x.开始, -(x.结束-x.开始), x.来源 != "模型")):
        块 = 块表.get(item.块编号)
        if 块 is None or not 0 <= item.开始 < item.结束 <= len(块.原文) or 块.原文[item.开始:item.结束] != item.原词:
            错误.append({"块编号": item.块编号, "环节": "位置验证", "原因": "原词与位置不一致"})
            continue
        key = (item.块编号,item.开始,item.结束)
        if key in 冲突位置:
            continue
        重叠 = [p for p in 结果 if p.块编号 == item.块编号 and p.开始 < item.结束 and item.开始 < p.结束]
        if not 重叠:
            结果.append(item)
        elif any(p.开始 == item.开始 and p.结束 == item.结束 and p.机构编号 != item.机构编号 and p.机构编号 and item.机构编号 for p in 重叠):
            错误.append({"块编号": item.块编号, "环节": "主体核对", "原因": "相同位置指向不同主体"})
            冲突位置.add(key)
            for p in 重叠:
                结果.remove(p)
    return 结果, 错误
