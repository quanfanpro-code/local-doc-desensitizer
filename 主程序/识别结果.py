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
    from bisect import bisect_left
    块表 = {b.编号: b for b in 块列表}
    结果, 错误, 冲突位置 = {}, [], set()
    # 处理顺序固定为：同块内先"规则类"后"机构类"，且各类内部按开始位置升序。
    # 因此两类已接受区间都只需在末尾追加即可保持有序，判重叠时用二分定位邻域，
    # 既不做全量两两比较，也不在有序表中间插队搬运。
    索引: dict = {}  # 块编号 -> {是否机构: [开始表, 结束表, 项表]}

    def 取组(块编号, 是机构):
        return 索引.setdefault(块编号, {}).setdefault(是机构, [[], [], []])

    def 查重叠(块编号, 开始, 结束):
        命中 = []
        for 是机构 in (False, True):
            开始表, 结束表, 项表 = 取组(块编号, 是机构)
            i = bisect_left(开始表, 开始)
            if i and 结束表[i-1] > 开始:
                i -= 1
            while i < len(开始表) and 开始表[i] < 结束:
                命中.append((是机构, i, 项表[i]))
                i += 1
        return 命中

    for item in sorted(出现列表, key=lambda x: (x.块编号, x.类型 in {"Ni","Nh","Ns"}, x.开始, -(x.结束-x.开始), x.来源 != "模型")):
        块 = 块表.get(item.块编号)
        if 块 is None or not 0 <= item.开始 < item.结束 <= len(块.原文) or 块.原文[item.开始:item.结束] != item.原词:
            错误.append({"块编号": item.块编号, "环节": "位置验证", "原因": "原词与位置不一致"})
            continue
        key = (item.块编号,item.开始,item.结束)
        if key in 冲突位置:
            continue
        是机构 = item.类型 in {"Ni","Nh","Ns"}
        命中 = 查重叠(item.块编号, item.开始, item.结束)
        重叠 = [p for _是机构, _i, p in 命中]
        if not 重叠:
            开始表, 结束表, 项表 = 取组(item.块编号, 是机构)
            开始表.append(item.开始)
            结束表.append(item.结束)
            项表.append(item)
            结果[key] = item
        elif 是机构 and any(p.类型 not in {"Ni","Nh","Ns"} for p in 重叠):
            # 完全位于规则中的模型子串已被保护；部分交叉不能静默当作完成。
            if not any(p.开始 <= item.开始 and p.结束 >= item.结束 for p in 重叠):
                错误.append({"块编号":item.块编号,"环节":"跨度冲突","原因":"模型范围与完整固定格式范围交叉，已保留固定格式替换，模型范围待核对"})
        elif any(p.开始 == item.开始 and p.结束 == item.结束 and p.机构编号 != item.机构编号 and p.机构编号 and item.机构编号 for p in 重叠):
            错误.append({"块编号": item.块编号, "环节": "主体核对", "原因": "相同位置指向不同主体"})
            冲突位置.add(key)
            待移除: dict = {}
            for 是否机构, i, _p in 命中:
                待移除.setdefault(是否机构, []).append(i)
            for 是否机构, 下标列表 in 待移除.items():
                开始表, 结束表, 项表 = 取组(item.块编号, 是否机构)
                for i in sorted(下标列表, reverse=True):
                    开始表.pop(i)
                    结束表.pop(i)
                    p = 项表.pop(i)
                    结果.pop((p.块编号, p.开始, p.结束), None)
    return list(结果.values()), 错误
