from __future__ import annotations

import json
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

DATE_FULL_PATTERN = re.compile(
    r"((?:19|20)\d{2})年(\d{1,2})月(\d{1,2})日"
)

DATE_YM_PATTERN = re.compile(
    r"((?:19|20)\d{2})年(\d{1,2})月"
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

    def 查找或创建(self, 原文: str, 实体类型: str) -> str:
        if 原文 in self._正向:
            return self._正向[原文]

        标签 = ENTITY_TYPE_LABELS.get(实体类型, 实体类型)
        序号 = self._计数器.get(标签, 0) + 1
        self._计数器[标签] = 序号
        代号 = f"[{标签}{序号}]"
        self._正向[原文] = 代号
        self._反向[代号] = 原文
        self._版本 += 1
        return 代号

    _圈数字 = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]

    def 注册自定义映射(self, 原文: str, 替换值: str) -> None:
        if 原文 in self._正向:
            return
        if 替换值 not in self._反向:
            self._正向[原文] = 替换值
            self._反向[替换值] = 原文
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

    def 反向查找(self, 代号: str) -> str | None:
        return self._反向.get(代号)

    @property
    def 正向映射(self) -> dict[str, str]:
        return dict(self._正向)

    @property
    def 反向映射(self) -> dict[str, str]:
        return dict(self._反向)

    def 导出(self) -> dict[str, str]:
        return self.正向映射

    映射表代号模式 = re.compile(r"^\[([^]]+?)(\d+)\]$")

    def 从文件加载(self, 路径: str | Path) -> None:
        data = json.loads(Path(路径).read_text(encoding="utf-8"))
        self._正向 = dict(data)
        self._反向 = {v: k for k, v in data.items()}
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
            json.dumps(self._正向, ensure_ascii=False, indent=2),
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
        cls._调试日志文件 = open(路径, 'w', encoding='utf-8')
        cls._调试日志文件.write(f"=== NER调试日志 ===\n模型: {cls._MODEL}\n\n")
        cls._调试日志文件.flush()
        print(f"[NER调试] 日志文件: {路径}", file=sys.stderr)

    @classmethod
    def 关闭调试日志(cls) -> None:
        if cls._调试日志文件:
            cls._调试日志文件.close()
            cls._调试日志文件 = None

    @classmethod
    def _写调试(cls, 内容: str) -> None:
        if cls._调试日志文件:
            cls._调试日志文件.write(内容)
            cls._调试日志文件.flush()

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

    def _获取api地址(self) -> str:
        配置 = self._读取llm配置()
        return f"{配置['api_base']}/chat/completions"

    NER_PROMPT = """你是中文命名实体识别程序，不是聊天助手。

你必须把最终结果输出在正式回答中。
即使你有思考过程，也必须在正式回答中输出最终JSON。
禁止只在思考过程、reasoning_content、analysis、草稿中给出结果。

输出必须且只能是JSON数组。
禁止Markdown。
禁止代码块。
禁止解释。
禁止注释。
禁止任何JSON以外的文字。

数组元素只能包含两个字段：
"name" 和 "type"。

"type" 只能是以下三个字符串之一：
"PERSON"
"LOCATION"
"ORGANIZATION"

禁止使用其他字段名。
禁止使用中文字段名。
禁止使用 PER / LOC / ORG / 公司 / 机构 / 地点 / 人名 等别名。

如果没有实体，输出：
[]

正确格式示例：
[{"name": "张三", "type": "PERSON"}, {"name": "北京", "type": "LOCATION"}, {"name": "四川晟天新能源发展有限公司", "type": "ORGANIZATION"}]

待识别文本：
"""

    def __init__(self) -> None:
        self._可用: bool | None = None

    def _检测lm可用性(self) -> bool:
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

    def 识别实体(self, 文本: str, 进度回调=None) -> list[tuple[str, str]]:
        if not 文本.strip():
            return []
        if not self._检测lm可用性():
            import sys
            后端名 = "在线 API" if self._读取llm配置()["mode"] == "online" else "LM Studio"
            print(f"[NER警告] {后端名} 未就绪，NER识别已跳过", file=sys.stderr)
            if 进度回调:
                进度回调(-1, -1, f"NER跳过（{后端名}不可用，纯正则模式，无人名/地名识别）")
            return []
        结果: list[tuple[str, str]] = []
        段落列表 = [s for s in self._分段(文本, 最大长度=6000) if s.strip()]
        总数 = len(段落列表)
        for i, 段落 in enumerate(段落列表):
            if 进度回调:
                进度回调(i, 总数)
            段落结果 = self._调用llm(段落)
            结果.extend(段落结果)
        if 进度回调:
            进度回调(总数, 总数)
        return 结果

    def _调用llm(self, 文本: str, _重试: int = 0) -> list[tuple[str, str]]:
        import requests
        TYPE_MAP_STRICT = {
            "PERSON": "Nh",
            "LOCATION": "Ns",
            "ORGANIZATION": "Ni",
        }
        TYPE_MAP_LENIENT = {
            "PERSON": "Nh", "PER": "Nh", "人物": "Nh", "人名": "Nh",
            "LOCATION": "Ns", "LOC": "Ns", "地名": "Ns", "地址": "Ns", "地点": "Ns", "GPE": "Ns",
            "ORGANIZATION": "Ni", "ORG": "Ni", "机构": "Ni", "组织": "Ni", "公司": "Ni", "单位": "Ni", "COMPANY": "Ni", "FAC": "Ni",
        }
        _最大重试 = 2
        try:
            调用序号 = getattr(self, '_调试调用计数', 0) + 1
            self._调试调用计数 = 调用序号
            _分隔 = f"\n{'='*80}\n"
            self._写调试(f"{_分隔}调用 #{调用序号}{_分隔}")

            _完整prompt = self.NER_PROMPT + 文本
            self._写调试(f"【发送给LLM的完整内容】({len(_完整prompt)}字符)\n{_完整prompt}\n{_分隔}")

            _配置 = self._读取llm配置()
            _请求头 = {}
            if _配置["mode"] == "online" and _配置["api_key"]:
                _请求头["Authorization"] = f"Bearer {_配置['api_key']}"
            resp = requests.post(
                self._获取api地址(),
                headers=_请求头,
                json={
                    "model": self._MODEL,
                    "messages": [
                        {"role": "user", "content": _完整prompt}
                    ],
                    "temperature": 0.0,
                    "stream": False,
                },
                timeout=(180, 360),
            )
            resp.raise_for_status()
            _完整返回 = resp.json()
            消息 = _完整返回["choices"][0]["message"]

            _原始内容 = 消息.get("content", "")
            _原始推理 = 消息.get("reasoning_content", "")
            _finish = _完整返回["choices"][0].get("finish_reason", "?")
            self._写调试(f"HTTP: {resp.status_code}  finish_reason: {_finish}\n")
            self._写调试(f"【LLM返回的正式回答content】({len(_原始内容) if _原始内容 else 0}字符)\n{_原始内容}\n{_分隔}")
            if _原始推理:
                self._写调试(f"【LLM返回的思考过程reasoning_content】({len(_原始推理)}字符)\n{_原始推理}\n{_分隔}")

            严格结果 = self._严格解析(消息, 文本, TYPE_MAP_STRICT)
            if 严格结果 is not None and len(严格结果) > 0:
                self._写调试(f"严格解析成功: {len(严格结果)} 个实体\n")
                for n, t in 严格结果:
                    self._写调试(f"  [{t}] {n}\n")
                return 严格结果

            if _原始推理 and not _原始内容:
                self._写调试("思考模型content为空，从reasoning兜底解析\n")
            if 严格结果 is not None and len(严格结果) == 0:
                self._写调试("严格解析返回空列表，进入兜底\n")
            else:
                self._写调试("严格解析失败，进入兜底\n")
            兜底结果 = self._兜底解析(消息, 文本, TYPE_MAP_LENIENT)
            if 兜底结果 is not None and len(兜底结果) > 0:
                print(f"[NER兜底] 成功提取 {len(兜底结果)} 个实体", file=sys.stderr)
                self._写调试(f"兜底解析成功: {len(兜底结果)} 个实体\n")
                for n, t in 兜底结果:
                    self._写调试(f"  [{t}] {n}\n")
                return 兜底结果

            self._写调试("严格和兜底解析均失败，NER返回空\n")
            return []
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError) as exc:
            错误类型 = type(exc).__name__
            self._写调试(f"!!! LLM传输错误 [{错误类型}]: {exc}\n")
            if _重试 < _最大重试:
                间隔秒 = (_重试 + 1) * 3
                import time as _time
                self._写调试(f"将在 {间隔秒} 秒后重试 ({_重试 + 1}/{_最大重试})...\n")
                _time.sleep(间隔秒)
                return self._调用llm(文本, _重试=_重试 + 1)
            return []
        except requests.exceptions.HTTPError as exc:
            _状态码 = exc.response.status_code if exc.response is not None else "?"
            self._写调试(f"!!! LLM HTTP错误 [{_状态码}]: {exc}\n")
            # 5xx服务端错误可以重试
            if _重试 < _最大重试 and isinstance(_状态码, int) and _状态码 >= 500:
                间隔秒 = (_重试 + 1) * 3
                import time as _time
                self._写调试(f"将在 {间隔秒} 秒后重试 ({_重试 + 1}/{_最大重试})...\n")
                _time.sleep(间隔秒)
                return self._调用llm(文本, _重试=_重试 + 1)
            return []
        except json.JSONDecodeError as exc:
            self._写调试(f"!!! LLM返回JSON解析失败: {exc}\n")
            return []
        except Exception as exc:
            self._写调试(f"!!! LLM调用异常: {exc}\n")
            return []

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

    @staticmethod
    def _严格解析(消息: dict, 原文: str, TYPE_MAP: dict) -> list[tuple[str, str]] | None:
        content = NER引擎._获取消息正式回答(消息)
        if not content:
            return None
        json_str = NER引擎._提取json(content)
        if not json_str:
            return None
        try:
            entities = json.loads(json_str)
        except json.JSONDecodeError:
            return None
        if not isinstance(entities, list):
            return None
        结果: list[tuple[str, str]] = []
        for ent in entities:
            if not isinstance(ent, dict):
                continue
            if set(ent.keys()) - {"name", "type"}:
                continue
            name = ent.get("name", "")
            etype = ent.get("type", "")
            if not name or not isinstance(name, str) or len(name) < 2:
                continue
            if name.isdigit():
                continue
            if name not in 原文:
                continue
            内部类型 = TYPE_MAP.get(etype)
            if not 内部类型:
                continue
            结果.append((name, 内部类型))
        return 结果

    @staticmethod
    def _兜底解析(消息: dict, 原文: str, TYPE_MAP: dict) -> list[tuple[str, str]] | None:
        原始文本 = NER引擎._提取消息文本(消息)
        if not 原始文本:
            return None
        json_str = NER引擎._提取json(原始文本)
        if not json_str:
            return None
        try:
            entities = json.loads(json_str)
        except json.JSONDecodeError:
            return None
        if not isinstance(entities, list):
            return None
        结果: list[tuple[str, str]] = []
        for ent in entities:
            if isinstance(ent, str):
                name = ent
                etype = "ORGANIZATION"
            elif isinstance(ent, dict):
                name = (ent.get("name") or ent.get("text") or ent.get("entity")
                        or ent.get("entity_text") or ent.get("word")
                        or ent.get("名称") or ent.get("名字") or ent.get("公司名")
                        or ent.get("机构名") or ent.get("单位名称") or "")
                etype = (ent.get("type") or ent.get("label") or ent.get("entity_type")
                         or ent.get("category") or ent.get("类别") or ent.get("类型") or "")
                if not name:
                    candidates = []
                    for v in ent.values():
                        if isinstance(v, str) and len(v) >= 2 and not v.isdigit():
                            if any('\u4e00' <= c <= '\u9fff' for c in v):
                                candidates.append(v)
                    if candidates:
                        name = max(candidates, key=len)
                if not etype:
                    for v in ent.values():
                        if isinstance(v, str):
                            vu = v.upper()
                            if vu in ("PERSON", "PER", "LOCATION", "LOC", "ORGANIZATION", "ORG", "GPE", "FAC"):
                                etype = v
                                break
                        if isinstance(v, str) and v in ("机构", "组织", "公司", "单位", "人名", "人物", "地名", "地址", "地点"):
                            etype = v
                            break
            else:
                continue
            if not name or not isinstance(name, str) or len(name) < 2:
                continue
            if name.isdigit():
                continue
            if name not in 原文:
                continue
            内部类型 = TYPE_MAP.get(etype.upper() if etype else "ORGANIZATION")
            if not 内部类型:
                内部类型 = "Ni"
            结果.append((name, 内部类型))
        return 结果

    @staticmethod
    def _提取消息文本(消息: dict) -> str:
        内容 = 消息.get("content")
        if isinstance(内容, str) and 内容.strip():
            return 内容.strip()
        elif isinstance(内容, list):
            片段列表: list[str] = []
            for 项 in 内容:
                if not isinstance(项, dict):
                    continue
                文本 = str(项.get("text") or "").strip()
                if 文本:
                    片段列表.append(文本)
            if 片段列表:
                return "\n".join(片段列表).strip()
        推理内容 = 消息.get("reasoning_content")
        if isinstance(推理内容, str) and 推理内容.strip():
            return 推理内容.strip()
        return ""

    @staticmethod
    def _提取json(文本: str) -> str:
        end = 文本.rfind("]")
        while end >= 0:
            start = 文本.rfind("[", 0, end)
            if start < 0:
                break
            候选 = 文本[start:end + 1]
            try:
                json.loads(候选)
                return 候选
            except json.JSONDecodeError:
                end = 文本.rfind("]", 0, end)
        return ""

    # ---- 实体名清洗：用于跨地名标记的简称匹配 ----
    _括号内容模式: re.Pattern | None = None
    _噪声标记模式: re.Pattern | None = None

    @classmethod
    def _初始化噪声模式(cls) -> None:
        if cls._噪声标记模式 is not None:
            return
        _b = _取词典("括号正则", r'[（(][^）)]*[）)]|[【\[]][^】\]]*[】\]]|[《〈][^》〉]*[》〉]|[「『][^」』]*[」』]')
        cls._括号内容模式 = re.compile(_b)
        _词 = []
        for _k in ["行政区划标记", "区域标记", "法律形式", "分支标记", "控股标记"]:
            _vals = _取词典(_k, ["省", "市", "县"])  # 兜底最小集，防止空正则
            _词.extend(_vals)
        _词.sort(key=len, reverse=True)
        cls._噪声标记模式 = re.compile('|'.join(re.escape(w) for w in _词))

    @classmethod
    def _清洗实体名(cls, 名称: str) -> str:
        """去除地名标记、公司后缀、括号内容，用于父实体模糊匹配"""
        cls._初始化噪声模式()
        _r = cls._括号内容模式.sub('', 名称)
        _r = cls._噪声标记模式.sub('', _r)
        return _r if _r.strip() else 名称

    _行业词模式: re.Pattern | None = None

    @classmethod
    def _洗行业词(cls, 名称: str) -> str:
        """仅对公司实体：循环洗掉末尾行业词/地名露出核心品牌名"""
        if cls._行业词模式 is None:
            _w = list(_取词典("行业词", ["科技", "实业"])) + list(_取词典("地名", ["北京", "上海"]))
            _w.sort(key=len, reverse=True)
            cls._行业词模式 = re.compile('(' + '|'.join(re.escape(w) for w in _w) + ')$')
        while True:
            m = cls._行业词模式.search(名称)
            if m and len(名称) - len(m.group(1)) >= 2:
                名称 = 名称[:-len(m.group(1))]
            else:
                break
        return 名称

    @staticmethod
    def _查找父实体(原文: str, 已有映射: dict[str, str]) -> str | None:
        # 第一轮：严格子串匹配
        for 已有 in sorted(已有映射, key=len, reverse=True):
            if 原文 != 已有 and 原文 in 已有:
                return 已有
        # 第二轮：清洗地名标记/公司后缀/括号后做子串匹配
        清洗原文 = NER引擎._清洗实体名(原文)
        if len(清洗原文) >= 2:
            for 已有 in sorted(已有映射, key=len, reverse=True):
                if 原文 == 已有:
                    continue
                清洗已有 = NER引擎._清洗实体名(已有)
                # 只要任一方清洗后有变化，且清洗后原文是清洗后已有的子串
                if (清洗原文 != 原文 or 清洗已有 != 已有) and 清洗原文 in 清洗已有:
                    return 已有
        return None

    @staticmethod
    def _生成地址片段(原文: str) -> list[str]:
        片段列表 = []
        行政区划分割 = re.compile(r'([省市区县镇乡村组])')
        parts = [p for p in 行政区划分割.split(原文) if p]
        当前 = ""
        i = 0
        while i < len(parts):
            当前 += parts[i]
            i += 1
            if i < len(parts) and len(parts[i]) == 1 and parts[i] in '省市区县镇乡村组':
                当前 += parts[i]
                i += 1
            if len(当前) >= 3 and 当前 != 原文:
                片段列表.append(当前)
        return 片段列表

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
    _机构简称模式 = re.compile(
        r'(?:[\u4e00-\u9fff]{2,8}?(?:'
        r'有限公司|有限责任公司|股份有限公司|股份公司|'
        r'实业|集团|公司|'
        r'矿业|磷矿|盐矿|煤矿|煤业|盐业|盐化|盐品|'
        r'矿产|冶炼|钢铁|冶金|重工|'
        r'光能|光伏|新能|新能源|新材料|能源|电力|水利|'
        r'科技|农科|生物|基因|医药|制药|医疗|卫生|器械|'
        r'农业|农牧|林业|渔业|畜牧|乳业|饲料|养殖|种植|园艺|'
        r'加油站|加气站|天然气|石油|石化|'
        r'投资|资本|资产|基金|信托|租赁|融资|典当|'
        r'银行|保险|证券|'
        r'房地产|置业|物业|'
        r'水务|化工|机械|消防|锅炉|模具|轴承|阀门|电缆|电器|仪器|仪表|'
        r'工程|技术|开发|建设|制造|安装|装饰|检测|监理|'
        r'销售|贸易|进出口|零售|百货|超市|'
        r'仓储|配送|快递|物流|运输|'
        r'咨询|评估|拍卖|担保|会计|审计|税务|法律|'
        r'设计|广告|印刷|包装|出版|图书|'
        r'教育|培训|翻译|会展|'
        r'文化|传媒|娱乐|体育|艺术|'
        r'食品|酿酒|饮料|烟草|餐饮|酒店|旅游|'
        r'纺织|服装|鞋业|皮革|'
        r'电子|通信|软件|网络|数据|信息|数码|智能|芯片|半导|半导体|集成电路|'
        r'建筑|建材|钢结构|幕墙|门窗|园林|绿化|'
        r'环保|节能|环卫|'
        r'电站|汽车|机车|船舶|航空|航天|'
        r'家电|家具|办公|'
        r'造纸|橡胶|塑料|轮胎|涂料|油漆|玻璃|陶瓷|'
        r'化肥|农药|日化|化妆品|'
        r'珠宝|首饰|眼镜|钟表|乐器|'
        r'安保|养老|殡葬|'
        r'美容|美发|洗浴|'
        r'公证|仲裁|拍卖|'
        r'发电|供电|供水|供暖|'
        r'影城|影院|游乐|健身|'
        r'医院|诊所|学校'
        r'))'
        r'|'
        r'(?:[A-Z]{2,5})'
    )

    _审核PROMPT = """你是中文机构名称审核程序，不是聊天助手。

你必须把最终结果输出在正式回答中。
即使你有思考过程，也必须在正式回答中输出最终JSON。
禁止只在思考过程里给出结果。

输出必须且只能是JSON数组。
禁止Markdown、解释、注释、代码块、任何JSON以外的文字。

数组元素只能包含两个字段：
"name" 和 "is_org"。

"name" 必须是输入候选词中的原词。
"is_org" 只能是 true 或 false，不能是字符串 "true" 或 "false"。

判断标准：
1. 机构名通常包含：公司、实业、集团、矿业、科技、投资等后缀
2. 中文简称如"涌江实业"、"和邦农科"也是真实机构名
3. "实业兴邦"、"科技强国"这类口号/成语不是机构名
4. 英文大写缩写如"AEV"在上下文中可能是机构名
5. 包含"企业投资"、"项目备案"、"上网电价"等通用公文词汇的不是机构名
6. 以"家"、"省"、"市"、"对"、"应"等碎片开头的不完整短语不是机构名

如果没有真实机构名，输出：
[]

正确格式示例：
[{"name": "通江实业", "is_org": true}, {"name": "实业兴邦", "is_org": false}]

待审核词语：
"""

    # 以下黑名单从词典.json加载，文件缺失时使用内置默认值
    _通用前缀黑名单 = frozenset(_取词典("前缀黑名单", ["目标", "贵", "本", "该", "此", "某", "各"]))
    _简称全词黑名单 = frozenset(_取词典("全词黑名单", ["目标公司", "贵公司", "本公司"]))
    _句内禁用字 = frozenset(_取词典("虚词词典", ["的", "了", "和", "与", "或"]))
    _简称_短后缀长度下限 = _取词典("短后缀下限", {"公司": 6, "集团": 6})

    def _发现简称候选(self, 文本: str, 已有映射: dict[str, str]) -> list[str]:
        候选集合: set[str] = set()
        for m in self._机构简称模式.finditer(文本):
            word = m.group()
            if word in 已有映射:
                continue
            if len(word) < 3:
                continue
            # 简称不可能是长句子（含后缀最多15字）
            if len(word) > 15:
                continue
            # 黑名单过滤
            if word in self._简称全词黑名单:
                continue
            # 通用前缀过滤
            if any(word.startswith(p) for p in self._通用前缀黑名单):
                continue
            # 短后缀要求更长候选：常见后缀如"公司"太短容易误伤
            过短 = False
            for 后缀, 下限 in self._简称_短后缀长度下限.items():
                if word.endswith(后缀) and len(word) < 下限:
                    过短 = True
                    break
            if 过短:
                continue
            # 纯数字或纯标点过滤
            if not any('\u4e00' <= c <= '\u9fff' for c in word):
                continue
            # 句子连接词过滤：实体名不含"的、了、和、与"等虚词
            if any(c in self._句内禁用字 for c in word):
                continue
            候选集合.add(word)
        return list(候选集合)

    def _审核简称候选(self, 候选列表: list[str]) -> list[str]:
        if not 候选列表:
            return []
        if not self._检测lm可用性():
            return []
        import requests
        prompt_text = self._审核PROMPT + "\n".join(候选列表)
        try:
            _配置 = self._读取llm配置()
            _请求头 = {}
            if _配置["mode"] == "online" and _配置["api_key"]:
                _请求头["Authorization"] = f"Bearer {_配置['api_key']}"
            resp = requests.post(
                self._获取api地址(),
                headers=_请求头,
                json={
                    "model": self._MODEL,
                    "messages": [
                        {"role": "user", "content": prompt_text}
                    ],
                    "temperature": 0.0,
                    "stream": False,
                },
                timeout=(180, 360),
            )
            resp.raise_for_status()
            消息 = resp.json()["choices"][0]["message"]
            content = self._获取消息正式回答(消息)
            if not content:
                content = self._提取消息文本(消息)
            content = self._提取json(content)
            if not content:
                return []
            items = json.loads(content)
            if not isinstance(items, list):
                return []
            结果列表: list[str] = []
            候选集合 = set(候选列表)
            for item in items:
                if not isinstance(item, dict):
                    continue
                name = item.get("name") or item.get("text") or item.get("entity") or item.get("word") or item.get("机构名") or item.get("名称") or ""
                if not name or not isinstance(name, str):
                    continue
                if name not in 候选集合:
                    continue
                is_org = item.get("is_org")
                if is_org is True or is_org == "true" or is_org == "是" or is_org == "yes" or is_org == 1:
                    结果列表.append(name)
            return 结果列表
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError) as exc:
            import sys
            print(f"[NER审核] 传输错误: {exc}", file=sys.stderr)
            return []
        except requests.exceptions.HTTPError as exc:
            import sys
            _状态码 = exc.response.status_code if exc.response is not None else "?"
            print(f"[NER审核] HTTP错误 [{_状态码}]: {exc}", file=sys.stderr)
            return []
        except json.JSONDecodeError as exc:
            import sys
            print(f"[NER审核] JSON解析失败: {exc}", file=sys.stderr)
            return []
        except Exception:
            return []

    def _分段(self, 文本: str, 最大长度: int = 500, 重叠量: int = 50) -> list[str]:
        if len(文本) <= 最大长度:
            return [文本]
        段落列表 = 文本.split("\n")
        结果: list[str] = []
        当前 = ""
        for 段 in 段落列表:
            if len(当前) + len(段) + 1 > 最大长度:
                if 当前:
                    结果.append(当前)
                if len(段) > 最大长度:
                    步长 = max(最大长度 - 重叠量, 1)
                    for i in range(0, len(段), 步长):
                        结果.append(段[i:i + 最大长度])
                    当前 = ""
                else:
                    当前 = 段
            else:
                当前 = 当前 + "\n" + 段 if 当前 else 段
        if 当前:
            结果.append(当前)
        return 结果

    def 文本脱敏(self, 文本: str, 映射: 全局映射表, 进度回调=None,
                 启用日期: bool = True, 启用月日: bool = False, 启用金额: bool = False) -> str:
        if 进度回调:
            进度回调(-1, -1, "NER 开始")
        实体列表 = self.识别实体(文本, 进度回调=进度回调)
        llm已工作 = self._可用 is True
        # LLM已产出实体时，正则无权插手实体识别，仅做结构化脱敏
        llm已产出实体 = llm已工作 and len(实体列表) > 0
        _ner人名 = sum(1 for _, t in 实体列表 if t == "Nh")
        _ner地址 = sum(1 for _, t in 实体列表 if t == "Ns")
        _ner机构 = sum(1 for _, t in 实体列表 if t == "Ni")
        if 进度回调:
            _msg = f"NER发现: 人名{_ner人名} 地址{_ner地址} 机构{_ner机构}，注册映射实体"
            进度回调(-1, -1, _msg)
        实体列表.sort(key=lambda x: len(x[0]), reverse=True)
        新地址实体: list[str] = []
        for 原文, 实体类型 in 实体列表:
            if 原文 in 映射.正向映射:
                continue
            父实体 = self._查找父实体(原文, 映射.正向映射)
            if 父实体:
                映射.注册自定义映射(原文, 映射._正向[父实体])
            else:
                if 实体类型 == "Ni":
                    子类型 = 判断机构子类型(原文)
                    映射.查找或创建(原文, 子类型)
                else:
                    映射.查找或创建(原文, 实体类型)
            if 实体类型 == "Ns":
                新地址实体.append(原文)

        # 从已确认实体生成脱壳简称（与正则发现互补，不依赖后缀匹配）
        # 分两轮：第一轮洗法律后缀/地名标记，第二轮仅对公司类洗行业词
        # 用注册自定义映射为每个简称分配独有代号（带圈数字序号），保留还原能力
        _脱壳计数 = 0
        for 原文 in list(映射.正向映射.keys()):
            代号 = 映射._正向[原文]
            # 第一轮：洗掉法律后缀 + 地名标记
            简称 = self._清洗实体名(原文)
            if 简称 != 原文 and len(简称) >= 2 and 简称 not in 映射.正向映射:
                映射.注册自定义映射(简称, 代号)
                _脱壳计数 += 1
            # 第二轮（仅公司类）：再洗一次行业词，露出核心品牌名
            if 代号.startswith('[公司') or 代号.startswith('[合伙'):
                核心 = self._洗行业词(简称)
                if 核心 != 简称 and len(核心) >= 2 and 核心 not in 映射.正向映射:
                    映射.注册自定义映射(核心, 代号)
                    _脱壳计数 += 1
        if _脱壳计数 and 进度回调:
            进度回调(-1, -1, f"实体脱壳生成{_脱壳计数}个简称")

        # 正则兜底：仅在LLM未产出实体时启用
        if not llm已产出实体:
            规则机构 = self._规则识别明显机构(文本)
            _规则新增 = 0
            if 规则机构:
                for 机构名, 实体类型 in 规则机构:
                    if 机构名 in 映射.正向映射:
                        continue
                    # 脏上下文过滤：正则匹配到了包含已有实体的更长文本（如整句），跳过
                    if any(已有 in 机构名 for 已有 in 映射.正向映射 if len(已有) >= 4):
                        continue
                    父实体 = self._查找父实体(机构名, 映射.正向映射)
                    if 父实体:
                        映射.注册自定义映射(机构名, 映射._正向[父实体])
                        _规则新增 += 1
                    elif not llm已工作:
                        # LLM没工作，正则独立兜底，可以信任
                        子类型 = 判断机构子类型(机构名)
                        映射.查找或创建(机构名, 子类型)
                        _规则新增 += 1
                    # LLM已工作且既非脏匹配也非子实体：跳过，不信任纯正则发现
            if 进度回调 and 规则机构:
                进度回调(-1, -1, f"规则兜底: {len(规则机构)}候选, 实际新增{_规则新增}个")
        elif 进度回调:
            进度回调(-1, -1, "NER已产出实体，跳过正则兜底")
        if 进度回调 and 新地址实体:
            进度回调(-1, -1, "注册地址片段")
        for 地址原文 in 新地址实体:
            if 地址原文 not in 映射.正向映射:
                continue
            代号 = 映射.正向映射[地址原文]
            for 片段 in self._生成地址片段(地址原文):
                if 片段 not in 映射.正向映射:
                    映射.注册自定义映射(片段, 代号)
        if 进度回调:
            进度回调(-1, -1, "匹配正则模式")
        匹配列表 = [
            (BANK_ACCOUNT_PATTERN, "bank_account"),
            (CREDIT_CODE_PATTERN, "credit_code"),
            (MOBILE_PHONE_PATTERN, "mobile_phone"),
            (LANDLINE_PATTERN, "landline"),
            (ID_CARD_PATTERN, "id_card"),
            (EMAIL_PATTERN, "email"),
            (PLATE_NUMBER_PATTERN, "plate_number"),
            (IPV4_PATTERN, "ip_address"),
            (MAC_ADDRESS_PATTERN, "mac_address"),
        ]
        for 模式, 类型标签 in 匹配列表:
            for 匹配 in 模式.finditer(文本):
                候选 = 匹配.group()
                if 类型标签 == "credit_code" and 候选.isdigit():
                    continue
                映射.查找或创建(候选, 类型标签)
        if 启用金额:
            if 进度回调:
                进度回调(-1, -1, "处理金额")
            for 匹配 in AMOUNT_PATTERN.finditer(文本):
                数字部分 = 匹配.group(1)
                单位 = 匹配.group(2)
                原始匹配串 = 匹配.group(0)
                模糊值 = _模糊化金额(原始匹配串, 数字部分, 单位)
                if 模糊值:
                    映射.注册自定义映射(原始匹配串, 模糊值)
            for 匹配 in AMOUNT_NO_UNIT_PATTERN.finditer(文本):
                数字部分 = 匹配.group(1)
                模糊值 = _模糊化金额(数字部分, 数字部分, "元")
                if 模糊值:
                    映射.注册自定义映射(数字部分, 模糊值)
        # 简称候选发现：父实体自动注册始终执行（子串匹配安全），
        # LLM审核仅在正则兜底模式（LLM未产出实体）时启用
        if 进度回调:
            进度回调(-1, -1, "发现简称候选")
        简称候选 = self._发现简称候选(文本, 映射.正向映射)
        待审核列表: list[str] = []
        自动注册计数 = 0
        for 候选名 in 简称候选:
            父实体 = self._查找父实体(候选名, 映射.正向映射)
            if 父实体:
                映射.注册自定义映射(候选名, 映射._正向[父实体])
                自动注册计数 += 1
            else:
                待审核列表.append(候选名)
        if 自动注册计数 and 进度回调:
            进度回调(-1, -1, f"简称 自动注册{自动注册计数}个，待LLM审核{len(待审核列表)}个")
        if not llm已产出实体 and 待审核列表:
            # 正则兜底模式：送LLM审核未知简称
            通过审核: list[str] = []
            批次大小 = 50
            总批次 = (len(待审核列表) + 批次大小 - 1) // 批次大小
            for 批次序号, 批次起点 in enumerate(range(0, len(待审核列表), 批次大小), 1):
                批次 = 待审核列表[批次起点:批次起点 + 批次大小]
                if 进度回调:
                    进度回调(-1, -1, f"LLM审核简称 {批次序号}/{总批次}")
                通过审核.extend(self._审核简称候选(批次))
            for 候选名 in 通过审核:
                if 候选名 in 映射.正向映射:
                    continue
                子类型 = 判断机构子类型(候选名)
                映射.查找或创建(候选名, 子类型)
        elif llm已产出实体 and 待审核列表 and 进度回调:
            进度回调(-1, -1, f"跳过{len(待审核列表)}个未知简称的LLM审核（NER已产出实体）")

        机构标签集合 = {"公司", "机关", "事业单位", "协会", "机构", "合伙企业"}
        映射中机构数 = sum(
            1 for 代号 in 映射.正向映射.values()
            if any(tag in 代号 for tag in 机构标签集合)
        )
        if 映射中机构数 == 0:
            再次检查 = self._规则识别明显机构(文本)
            if 再次检查:
                import sys
                msg = "质量闸门：单位识别完全失败。映射表0个机构项，但原文中存在明显单位名称。请检查LM Studio或更换模型。"
                print(f"[质量闸门] {msg}", file=sys.stderr)
                if 进度回调:
                    进度回调(-1, -1, f"[质量闸门] 单位识别完全失败！")
                raise RuntimeError(msg)

        if 启用日期:
            if 进度回调:
                进度回调(-1, -1, "脱敏日期")
            self._脱敏日期(文本, 映射, 启用月日=启用月日)
        if 进度回调:
            进度回调(-1, -1, "AC自动机替换")
        return 映射.批量替换文本(文本)

    def _脱敏日期(self, 文本: str, 映射: 全局映射表, 启用月日: bool = False) -> None:
        已处理 = set()
        for 匹配 in DATE_FULL_PATTERN.finditer(文本):
            完整 = 匹配.group(0)
            年份 = 匹配.group(1)
            月 = 匹配.group(2)
            日 = 匹配.group(3)
            if 完整 in 已处理:
                continue
            已处理.add(完整)
            模糊年 = 年份[:2] + "X" + 年份[3]
            if 启用月日:
                代号 = 映射.查找或创建(f"{月}月{日}日", "date")
                替换值 = f"{模糊年}年{代号}"
            else:
                替换值 = f"{模糊年}年{月}月{日}日"
            映射.注册自定义映射(完整, 替换值)
        for 匹配 in DATE_YM_PATTERN.finditer(文本):
            完整 = 匹配.group(0)
            if 完整 in 已处理:
                continue
            紧后面 = 文本[匹配.end():匹配.end() + 3]
            if 紧后面 and 紧后面[0].isdigit():
                后续 = 紧后面.split("日")[0] if "日" in 紧后面 else ""
                if 后续 and 后续.isdigit() and 1 <= int(后续) <= 31:
                    continue
            已处理.add(完整)
            年份 = 匹配.group(1)
            月 = 匹配.group(2)
            模糊年 = 年份[:2] + "X" + 年份[3]
            if 启用月日:
                代号 = 映射.查找或创建(f"{月}月", "date")
                替换值 = f"{模糊年}年{代号}"
            else:
                替换值 = f"{模糊年}年{月}月"
            映射.注册自定义映射(完整, 替换值)
