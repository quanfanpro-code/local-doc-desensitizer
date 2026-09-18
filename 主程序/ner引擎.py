from __future__ import annotations

import json
import sys
import re
from pathlib import Path

# ====== 加载统一词典 ======
_词典路径 = Path(__file__).resolve().parents[1] / "词典.json"
_词典: dict = {}
try:
    if _词典路径.exists():
        _词典 = json.loads(_词典路径.read_text(encoding="utf-8"))
except (json.JSONDecodeError, OSError) as e:
    import sys
    print(f"[词典警告] 加载词典.json失败: {e}，将使用内置默认值继续运行", file=sys.stderr)


def _取词典(key: str, default=None):
    """从统一词典中取值，文件不存在时返回默认值"""
    return _词典.get(key, default or [])

ENTITY_TYPE_LABELS: dict[str, str] = {
    "Nh": "人物",
    "Ns": "地址",
    "bank_account": "银行账号",
    "credit_code": "信用代码",
    "mobile_phone": "手机号",
    "landline": "座机号",
    "id_card": "身份证号",
    "email": "邮箱",
    "plate_number": "车牌号",
    "ip_address": "IP地址",
    "mac_address": "MAC地址",
    "amount": "金额",
    "date": "日期",
}

BANK_ACCOUNT_PATTERN = re.compile(r"(?<!\d)\d{16,19}(?!\d)")
CREDIT_CODE_PATTERN = re.compile(r"(?<![0-9A-Z])[0-9A-Z]{18}(?![0-9A-Z])")

MOBILE_PHONE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:"
    r"1[3-9]\d{9}"
    r"|"
    r"\+[1-9]\d{6,14}"
    r"|"
    r"00[1-9]\d{6,13}"
    r")"
    r"(?!\d)"
)

LANDLINE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:"
    r"0\d{2,3}[-\s]?\d{7,8}"
    r"|"
    r"\+[1-9]\d{0,3}[-\s]?\d{6,14}"
    r"|"
    r"00[1-9]\d{0,3}[-\s]?\d{6,13}"
    r")"
    r"(?:\s*(?:转|分机|ext\.?|x)\s*\d{2,6})?"
    r"(?!\d)"
)

ID_CARD_PATTERN = re.compile(
    r"(?<!\d)"
    r"[1-9]\d{5}"
    r"(?:19|20)\d{2}"
    r"(?:0[1-9]|1[0-2])"
    r"(?:0[1-9]|[12]\d|3[01])"
    r"\d{3}[\dXx]"
    r"(?!\d)"
)

EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

PLATE_NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z\u4e00-\u9fff])"
    r"(?:[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤川青藏琼宁]"
    r"[A-HJ-NP-Z]"
    r"[A-HJ-NP-Z0-9]{4,5}"
    r"[A-HJ-NP-Z0-9挂学警港澳])"
    r"(?![A-Za-z0-9])"
)

IPV4_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)"
    r"(?!\d)"
)

MAC_ADDRESS_PATTERN = re.compile(
    r"(?<![\da-fA-F])"
    r"(?:[0-9A-Fa-f]{2}[:-]){5}"
    r"[0-9A-Fa-f]{2}"
    r"(?![\da-fA-F])"
)

AMOUNT_PATTERN = re.compile(
    r"(?<!\d)"
    r"((?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d{1,2})?)"
    r"\s*(万元|亿元|万|亿|元|港元|美元|欧元|日元|英镑)"
)

AMOUNT_NO_UNIT_PATTERN = re.compile(
    r"(?<!\d)"
    r"((?:\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?)"
    r"(?!\d)"
)

_金额单位倍数 = {
    "元": 1, "港元": 1, "美元": 1, "欧元": 1, "日元": 1, "英镑": 1,
    "万": 10000, "万元": 10000,
    "亿": 100000000, "亿元": 100000000,
}


def _模糊化金额(原始匹配串: str, 数字部分: str, 单位: str) -> str | None:
    try:
        纯数字 = float(数字部分.replace(",", ""))
    except ValueError:
        return None
    换算为元 = 纯数字 * _金额单位倍数.get(单位, 1)
    if 换算为元 < 1000000:
        return None
    换算为万 = round(换算为元 / 10000)
    取整到百 = round(换算为万 / 100) * 100
    return f"{取整到百}万余元"


ORG_SUFFIX_RULES: list[tuple[str, str]] = [
    ("公司", "公司"),
    ("集团", "公司"),
    ("合伙企业", "合伙企业"),
    ("合伙", "合伙企业"),
    ("协会", "协会"),
    ("学会", "协会"),
    ("联合会", "协会"),
    ("商会", "协会"),
    ("促进会", "协会"),
    ("基金会", "协会"),
    ("研究所", "事业单位"),
    ("研究院", "事业单位"),
    ("中心", "事业单位"),
    ("馆", "事业单位"),
    ("站", "事业单位"),
    ("社", "事业单位"),
    ("院", "事业单位"),
    ("局", "机关"),
    ("厅", "机关"),
    ("部", "机关"),
    ("委", "机关"),
    ("办", "机关"),
    ("处", "机关"),
    ("署", "机关"),
]


def 判断机构子类型(机构名: str) -> str:
    for 关键词, 子类型 in ORG_SUFFIX_RULES:
        if 关键词 in 机构名:
            return 子类型
    return "机构"


class 全局映射表:
    def __init__(self) -> None:
        self._正向: dict[str, str] = {}
        self._反向: dict[str, str] = {}
        self._计数器: dict[str, int] = {}
        self._版本: int = 0
        self._自动机正向 = None
        self._自动机反向 = None
        self._自动机正向版本: int = -1
        self._自动机反向版本: int = -1
        self._机构: dict[str, dict] = {}
        self._保留代号: set[str] = set()
        self._歧义原词: set[str] = set()
        self.文件记录: list[dict] = []
        self.载入提示: list[str] = []

    def 保留原文代号(self, 原文: str) -> None:
        self._保留代号.update(re.findall(r"\[[^\]\r\n]+\d+\]", 原文))

    def _分配主代号(self, 类型: str) -> str:
        标签 = ENTITY_TYPE_LABELS.get(类型, 类型)
        序号 = self._计数器.get(标签, 0)
        while True:
            序号 += 1
            代号 = f"[{标签}{序号}]"
            if 代号 not in self._反向 and 代号 not in self._保留代号:
                self._计数器[标签] = 序号
                return 代号

    def 注册机构称呼(self, 机构编号: str, 原文: str, 子类型: str, 是否全称: bool = False) -> str:
        if not 机构编号 or not 原文:
            raise ValueError("机构编号和原文不能为空")
        if 机构编号 not in self._机构:
            self._机构[机构编号] = {"主代号": self._分配主代号(子类型), "称呼": {}, "下个序号": 1}
        机构 = self._机构[机构编号]
        if 原文 in 机构["称呼"]:
            return 机构["称呼"][原文]
        代号 = 机构["主代号"]
        if not 是否全称 or 代号 in self._反向:
            while True:
                序号 = 机构["下个序号"]
                机构["下个序号"] += 1
                后缀 = self._圈数字[序号 - 1] if 序号 <= len(self._圈数字) else f"({序号})"
                代号 = 机构["主代号"] + 后缀
                if 代号 not in self._反向 and 代号 not in self._保留代号:
                    break
        机构["称呼"][原文] = 代号
        if 原文 in self._正向 and self._正向[原文] != 代号:
            self._歧义原词.add(原文)
            self._正向.pop(原文)
        elif 原文 not in self._歧义原词:
            self._正向[原文] = 代号
        self._反向[代号] = 原文
        self._版本 += 1
        return 代号

    def 查找或创建(self, 原文: str, 实体类型: str) -> str:
        if 原文 in self._正向:
            return self._正向[原文]

        代号 = self._分配主代号(实体类型)
        self._正向[原文] = 代号
        self._反向[代号] = 原文
        self._版本 += 1
        return 代号

    _圈数字 = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]

    def 注册自定义映射(self, 原文: str, 替换值: str, *, 允许共用: bool = False) -> None:
        if 原文 in self._正向:
            return
        if 替换值 not in self._反向:
            self._正向[原文] = 替换值
            self._反向[替换值] = 原文
            self._版本 += 1
            return
        if 允许共用:
            # 简称声明合并：多个原文共用同一代号是期望行为，不再加后缀
            self._正向[原文] = 替换值
            self._版本 += 1
            return
        for i in range(2, len(self._圈数字) + 2):
            后缀 = self._圈数字[i - 2] if i - 2 < len(self._圈数字) else f"({i})"
            候选值 = f"{替换值}{后缀}"
            if 候选值 not in self._反向:
                self._正向[原文] = 候选值
                self._反向[候选值] = 原文
                self._版本 += 1
                return
        # 圈数字用完后回退到数字后缀继续注册，绝不能静默放弃（放弃=原文泄露）
        i = len(self._圈数字) + 2
        while True:
            候选值 = f"{替换值}({i})"
            if 候选值 not in self._反向:
                self._正向[原文] = 候选值
                self._反向[候选值] = 原文
                self._版本 += 1
                return
            i += 1

    def 合并代号(self, 旧代号: str, 新代号: str) -> int:
        """把旧代号下挂的所有原文整体改挂到新代号（简称并入主实体时用）

        返回实际改挂的原文条数。旧代号随之作废删除。
        """
        if 旧代号 == 新代号:
            return 0
        改挂列表 = [原文 for 原文, 代号 in self._正向.items() if 代号 == 旧代号]
        for 原文 in 改挂列表:
            self._正向[原文] = 新代号
        self._反向.pop(旧代号, None)
        self._版本 += 1
        return len(改挂列表)

    @property
    def 正向映射(self) -> dict[str, str]:
        return dict(self._正向)

    @property
    def 反向映射(self) -> dict[str, str]:
        return dict(self._反向)

    映射表代号模式 = re.compile(r"^\[([^]]+?)(\d+)\]$")

    def 从文件加载(self, 路径: str | Path) -> None:
        data = json.loads(Path(路径).read_text(encoding="utf-8-sig"))
        self.__init__()
        if isinstance(data, dict) and data.get("version") == 2:
            self._正向 = dict(data["正向"])
            self._反向 = dict(data["反向"])
            self._机构 = dict(data.get("机构", {}))
            self._保留代号 = set(data.get("保留代号", []))
            self._歧义原词 = set(data.get("歧义原词", []))
            self._计数器 = dict(data.get("计数器", {}))
            self.文件记录 = list(data.get("文件记录", []))
        elif isinstance(data, dict) and all(isinstance(v, str) for v in data.values()):
            self._正向 = dict(data)
            self._反向 = {v: k for k, v in data.items()}
            if len(self._反向) != len(self._正向):
                self.载入提示.append("旧映射存在共用代号，无法恢复每处最初写法；沿用旧版还原结果")
        else:
            raise ValueError("无法识别映射文件格式")
        合法标签集合 = set(ENTITY_TYPE_LABELS.values()) | {t for _, t in ORG_SUFFIX_RULES} | {"机构", "实体"}
        for 代号 in self._反向:
            匹配 = self.映射表代号模式.match(代号)
            if not 匹配:
                continue
            标签 = 匹配.group(1)
            if 标签 not in 合法标签集合:
                continue
            序号文本 = 匹配.group(2)
            try:
                序号 = int(序号文本)
                self._计数器[标签] = max(self._计数器.get(标签, 0), 序号)
            except ValueError:
                pass
        self._版本 += 1

    def 保存到文件(self, 路径: str | Path) -> None:
        Path(路径).write_text(
            json.dumps({"version": 2, "正向": self._正向, "反向": self._反向,
                        "机构": self._机构, "计数器": self._计数器,
                        "保留代号": sorted(self._保留代号), "歧义原词": sorted(self._歧义原词),
                        "文件记录": self.文件记录}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _构建正向自动机(self):
        import ahocorasick
        A = ahocorasick.Automaton()
        for 原文 in self._正向:
            A.add_word(原文, 原文)
        A.make_automaton()
        return A

    def _构建反向自动机(self):
        import ahocorasick
        A = ahocorasick.Automaton()
        for 代号 in self._反向:
            A.add_word(代号, 代号)
        A.make_automaton()
        return A

    def 批量替换文本(self, 文本: str) -> str:
        if not self._正向:
            return 文本
        if self._自动机正向 is None or self._自动机正向版本 != self._版本:
            self._自动机正向 = self._构建正向自动机()
            self._自动机正向版本 = self._版本
        匹配列表 = []
        for end_idx, 原文 in self._自动机正向.iter(文本):
            start_idx = end_idx - len(原文) + 1
            匹配列表.append((start_idx, end_idx + 1, 原文))
        匹配列表.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        已用 = set()
        有效匹配 = []
        for start, end, 原文 in 匹配列表:
            if any(start <= p < end for p in 已用):
                continue
            for i in range(start, end):
                已用.add(i)
            有效匹配.append((start, end, 原文))
        有效匹配.sort(key=lambda x: x[0], reverse=True)
        for start, end, 原文 in 有效匹配:
            文本 = 文本[:start] + self._正向[原文] + 文本[end:]
        return 文本

    def 批量还原文本(self, 文本: str) -> str:
        if not self._反向:
            return 文本
        if self._自动机反向 is None or self._自动机反向版本 != self._版本:
            self._自动机反向 = self._构建反向自动机()
            self._自动机反向版本 = self._版本
        匹配列表 = []
        for end_idx, 代号 in self._自动机反向.iter(文本):
            start_idx = end_idx - len(代号) + 1
            匹配列表.append((start_idx, end_idx + 1, 代号))
        匹配列表.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        已用 = set()
        有效匹配 = []
        for start, end, 代号 in 匹配列表:
            if any(start <= p < end for p in 已用):
                continue
            for i in range(start, end):
                已用.add(i)
            有效匹配.append((start, end, 代号))
        有效匹配.sort(key=lambda x: x[0], reverse=True)
        for start, end, 代号 in 有效匹配:
            文本 = 文本[:start] + self._反向[代号] + 文本[end:]
        return 文本


class NER引擎:
    _MODEL = "local-model"
    _调试日志文件: object | None = None

    @classmethod
    def 启用调试日志(cls, 路径: str) -> None:
        import sys
        if cls._调试日志文件:
            cls._调试日志文件.close()
        cls._调试日志文件 = open(路径, 'w', encoding='utf-8')
        cls._调试日志文件.write(f"=== NER调试日志 ===\n")
        cls._调试日志文件.flush()
        print(f"[NER调试] 日志文件: {路径}", file=sys.stderr)

    @classmethod
    def 关闭调试日志(cls) -> None:
        if cls._调试日志文件:
            cls._调试日志文件.close()
            cls._调试日志文件 = None

    def _读取llm配置(self) -> dict:
        """从 settings.json 读取当前 LLM 模式和配置。

        返回：
          {"mode": "local"|"online", "api_base": str, "api_key": str, "model": str}
          - 本地模式：api_base 为探测lm_studio地址() 结果，api_key 空，model 空（靠 _检测lm可用性 自动探测）
          - 在线模式：api_base 为规范化后的地址，api_key/model 为用户填的值
        """
        try:
            from .mineru桥接 import 读取用户设置, 探测lm_studio地址, 规范化在线api地址
        except ImportError:
            from mineru桥接 import 读取用户设置, 探测lm_studio地址, 规范化在线api地址
        设置 = 读取用户设置()
        模式 = 设置.get("llm_mode", "local")
        if 模式 == "online":
            return {
                "mode": "online",
                "api_base": 规范化在线api地址(设置.get("online_api_base", "")),
                "api_key": 设置.get("online_api_key", ""),
                "model": 设置.get("online_model", ""),
            }
        return {
            "mode": "local",
            "api_base": 探测lm_studio地址(),
            "api_key": "",
            "model": "",
        }

    def _请求文档模型(self, 消息, 最大输出=8192):
        from 主程序.文档识别 import 请求模型
        return 请求模型(self, 消息, 最大输出)

    def _解析文档返回(self, 消息, 块列表, 机构资料=None, 全文块=None):
        from 主程序.文档识别 import 解析返回
        return 解析返回(self, 消息, 块列表, 机构资料, 全文块)

    def 识别文档(self, 块列表, 进度回调=None):
        from 主程序.文档识别 import 识别文档
        return 识别文档(self, 块列表, 进度回调)

    def 复查输出(self, 输出块, 原块, 已有机构, 进度回调=None):
        from 主程序.文档识别 import 复查输出
        return 复查输出(self, 输出块, 原块, 已有机构, 进度回调)

    def __init__(self) -> None:
        self._可用: bool | None = None
        self._缓存模式 = None

    def _检测lm可用性(self) -> bool:
        当前模式 = self._读取llm配置().get("mode")
        if 当前模式 != self._缓存模式:
            self._可用 = None
            self._缓存模式 = 当前模式
        if self._可用 is True:
            return True
        try:
            配置 = self._读取llm配置()
            if 配置["mode"] == "online":
                # 在线模式：调 探测在线api状态 验证连通性
                if not 配置["api_base"] or not 配置["api_key"]:
                    return False
                try:
                    from .mineru桥接 import 探测在线api状态
                except ImportError:
                    from mineru桥接 import 探测在线api状态
                状态 = 探测在线api状态(配置["api_base"], 配置["api_key"], 配置["model"])
                if not 状态["已启动"]:
                    return False
                # 模型名优先用用户填的，没填就取 /models 第一个
                self._MODEL = 配置["model"] or 状态["模型名称"]
                if not self._MODEL:
                    return False
                self._可用 = True
                return True
            # 本地模式：沿用现有逻辑
            try:
                from .mineru桥接 import 获取lm_studio模型列表, 选择首选文本模型
            except ImportError:
                from mineru桥接 import 获取lm_studio模型列表, 选择首选文本模型
            模型列表 = 获取lm_studio模型列表()
            if 模型列表:
                首选模型 = 选择首选文本模型(模型列表)
                if 首选模型:
                    self._MODEL = 首选模型
                    self._可用 = True
                    return True
        except Exception:
            pass
        return False

    @staticmethod
    def _获取消息正式回答(消息: dict) -> str:
        内容 = 消息.get("content")
        if isinstance(内容, str) and 内容.strip():
            return 内容.strip()
        if isinstance(内容, list):
            片段列表: list[str] = []
            for 项 in 内容:
                if not isinstance(项, dict):
                    continue
                文本 = str(项.get("text") or "").strip()
                if 文本:
                    片段列表.append(文本)
            if 片段列表:
                return "\n".join(片段列表).strip()
        return ""

    _明显机构后缀模式组: list[re.Pattern] = []

    _前缀清洗模式: re.Pattern | None = None

    @classmethod
    def _取前缀清洗模式(cls) -> re.Pattern:
        if cls._前缀清洗模式 is None:
            _词 = _取词典("前缀清洗词", ["关于", "拟", "对", "的", "和", "与"])
            _词.sort(key=len, reverse=True)
            _pat = r'^(?:' + '|'.join(re.escape(w) for w in _词) + r'|[\d\s，,。.、年月日/\-]{1,30}){1,5}'
            _pat += r'(?=[\u4e00-\u9fff（）()a-zA-Z0-9]{4,})'
            cls._前缀清洗模式 = re.compile(_pat)
        return cls._前缀清洗模式

    _兜底黑名单 = frozenset({
        "有限公司", "有限责任公司", "股份有限公司", "股份公司", "集团", "集团公司",
        "协会", "学会", "联合会", "商会", "促进会", "基金会",
        "研究院", "研究所", "中心", "社", "馆", "站", "院",
        "局", "厅", "部", "委", "办", "处", "署",
    })

    def _规则识别明显机构(self, 文本: str) -> list[tuple[str, str]]:
        if not self._明显机构后缀模式组:
            self._构建明显机构模式组()
        结果: list[tuple[str, str]] = []
        已见: set[str] = set()
        for pat in self._明显机构后缀模式组:
            for m in pat.finditer(文本):
                raw = m.group()
                name = self._取前缀清洗模式().sub('', raw)
                if len(name) < 4 or name in self._兜底黑名单:
                    continue
                if name not in 已见:
                    已见.add(name)
                    结果.append((name, "Ni"))
        return 结果

    @classmethod
    def _构建明显机构模式组(cls) -> None:
        _名 = r'[\u4e00-\u9fff（）()a-zA-Z0-9]{2,30}?'
        cls._明显机构后缀模式组 = [
            re.compile(_名 + r'会计师事务所(?:（[^）]*）)?'),
            re.compile(_名 + r'集团有限公司'),
            re.compile(_名 + r'集团(?:有限(?:责任)?公司|股份(?:有限)?公司)'),
            re.compile(_名 + r'有限(?:责任)?公司'),
            re.compile(_名 + r'股份(?:有限)?公司'),
            re.compile(_名 + r'银行(?:股份(?:有限)?公司)?'),
            re.compile(_名 + r'供电公司'),
            re.compile(_名 + r'财务公司'),
            re.compile(_名 + r'工程(?:有限(?:责任)?公司)?'),
            re.compile(_名 + r'新能源(?:股份(?:有限)?公司|有限(?:责任)?公司|发展(?:有限(?:责任)?公司)?)'),
            re.compile(_名 + r'投资合伙企业(?:（[^）]*）)?'),
            re.compile(_名 + r'研究院(?:有限(?:责任)?公司)?'),
            re.compile(_名 + r'研究所(?:有限(?:责任)?公司)?'),
            re.compile(_名 + r'协会'),
            re.compile(_名 + r'学会'),
            re.compile(_名 + r'联合会'),
            re.compile(_名 + r'商会'),
            re.compile(_名 + r'促进会'),
            re.compile(_名 + r'基金会'),
        ]

    def 文本脱敏(self, 文本: str, 映射: 全局映射表, 进度回调=None,
                 启用日期: bool = True, 启用月日: bool = False, 启用金额: bool = False) -> str:
        from 主程序.识别结果 import 文本块, 按位置替换
        from 主程序.固定规则 import 固定规则识别
        from 主程序.定位写回 import 准备替换
        块 = 文本块("text:0",文本,{})
        检出 = self.识别文档([块],进度回调)
        检出.出现.extend(固定规则识别(块,启用日期,启用月日,启用金额))
        self.最近识别结果 = 检出
        return 按位置替换(文本,准备替换([块],检出,映射).get(块.编号,[]))
