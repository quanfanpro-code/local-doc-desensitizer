"""固定格式候选、校验及原文位置；来源见 docs/规则来源.md。"""
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re
import unicodedata
import phonenumbers
from 主程序.识别结果 import 出现记录


def 金额模糊值(文字):
    """保留既有百万门槛、银行家舍入及原币种，不做币种换算。"""
    匹配 = re.fullmatch(r"([\d,.]+)\s*((?:万|亿)?(?:港元|美元|欧元|日元|英镑|元)|万|亿)?",文字)
    币种 = "元"
    if 匹配:
        try:
            金额 = Decimal(匹配[1].replace(",",""))
        except InvalidOperation:
            return None
        单位 = 匹配[2] or "元"
        金额 *= 10000 if 单位.startswith("万") else 100000000 if 单位.startswith("亿") else 1
        币种 = 单位.lstrip("万亿") or "元"
    else:
        核心 = re.split("[元圆]",文字)[0]
        数字 = dict(zip("零壹贰叁肆伍陆柒捌玖",range(10)))
        小单位 = {"拾":10,"佰":100,"仟":1000}
        总数 = 段值 = 当前 = 0
        for c in 核心:
            if c in 数字:
                当前 = 数字[c]
            elif c in 小单位:
                段值 += (当前 or 1)*小单位[c]; 当前 = 0
            elif c in "万亿":
                段值 += 当前; 当前 = 0
                if c == "万":
                    总数 += 段值*10000
                else:
                    总数 = (总数+段值)*100000000
                段值 = 0
            else:
                return None
        金额 = Decimal(总数+段值+当前)
    if 金额 < 1000000:
        return None
    百万数 = (金额/Decimal(1000000)).quantize(Decimal(1))
    return f"{百万数*100}万余{币种}"


def 身份证校验(值):
    if not re.fullmatch(r"[1-9]\d{16}[\dX]", 值):
        return False
    try:
        datetime.strptime(值[6:14], "%Y%m%d")
    except ValueError:
        return False
    权 = (7,9,10,5,8,4,2,1,6,3,7,9,10,5,8,4,2)
    return "10X98765432"[sum(int(x)*w for x,w in zip(值[:17],权)) % 11] == 值[-1]


def 信用代码校验(值):
    字符 = "0123456789ABCDEFGHJKLMNPQRTUWXY"
    if not re.fullmatch(r"[159Y][1239]\d{6}[0-9A-Z]{10}", 值):
        return False
    if any(c not in 字符 for c in 值):
        return False
    权 = (1,3,9,27,19,26,16,17,20,29,25,13,8,24,10,30,28)
    return 字符[(31-sum(字符.index(c)*w for c,w in zip(值[:17],权)) % 31) % 31] == 值[-1]


def 银行卡校验(值):
    if not 值.isdigit() or not 13 <= len(值) <= 19:
        return False
    总数 = 0
    for i,c in enumerate(reversed(值)):
        n = int(c) * (2 if i % 2 else 1)
        总数 += n if n < 10 else n - 9
    return 总数 % 10 == 0


def _有效日期(文字):
    """使用真实日历校验；没有年份的月日允许闰日，不猜测年份。"""
    def 数字(值):
        值 = 值.translate(str.maketrans("〇零一二三四五六七八九", "00123456789"))
        if "十" in 值:
            a,b = 值.split("十")
            return int(a or "1")*10 + int(b or "0")
        return int(值)
    try:
        部分 = [数字(x) for x in re.split(r"[年月日/-]",文字) if x]
        if "年" not in 文字 and not re.match(r"\d{4}[-/]",文字):
            部分.insert(0,2000)
        datetime(*(部分 + [1]*(3-len(部分))))
        return True
    except (ValueError,TypeError):
        return False


def 固定规则识别(块, 启用日期=False, 启用月日=False, 启用金额=False):
    from 主程序.ner引擎 import PLATE_NUMBER_PATTERN, IPV4_PATTERN, MAC_ADDRESS_PATTERN, AMOUNT_NO_UNIT_PATTERN
    规范, 偏移 = [], []
    for i,c in enumerate(块.原文):
        值 = unicodedata.normalize("NFKC",c)
        规范.extend(值); 偏移.extend([i]*len(值))
    文本 = "".join(规范)
    命中 = []
    def 记录(s,e,类型,优先=5,异常=False,金额单位=""):
        if s >= e:
            return
        a,b = 偏移[s], 偏移[e-1]+1
        命中.append((优先,出现记录(块.编号,a,b,块.原文[a:b],类型,
            来源="规则（校验异常，字段明确）" if 异常 else "规则")))
        if 金额单位:
            命中[-1][1].替换值 = 金额模糊值(文本[s:e]+金额单位)
            if 命中[-1][1].替换值 is None:
                命中.pop()
    def 前字段(s):
        return re.split(r"[；;。，,\n]",文本[max(0,s-45):s])[-1]
    def 标签(s, 模式):
        前文 = 前字段(s)
        # Excel 单元格按列归属：只搜当前列的字段提示，
        # 不让整行/整表头里其他列的字段名干扰当前格；非 Excel 块维持原行为
        if "列字段" in 块.位置:
            return bool(re.search(模式, 前文 + " " + 块.位置["列字段"], re.I))
        return bool(re.search(模式, 前文 + " " + 块.上下文, re.I))
    for m in re.finditer(r"(?<![0-9A-Za-z])[0-9A-Za-z](?:[ -]?[0-9A-Za-z]){17}(?![0-9A-Za-z])",文本):
        v = re.sub(r"[ -]","",m.group()).upper()
        身份有效 = 身份证校验(v)
        if 身份有效 or (re.fullmatch(r"\d{17}[\dX]",v) and 标签(m.start(),r"身份证|公民身份")):
            记录(m.start(),m.end(),"id_card",0,not 身份有效)
        elif (信用代码校验(v) and not 标签(m.start(),r"物料编号|产品编号|商品编码")) or 标签(m.start(),r"社会信用|信用代码|纳税人识别号"):
            记录(m.start(),m.end(),"credit_code",1,not 信用代码校验(v))
    账号字段 = r"银行账[号户]|收款账[号户]|付款账[号户]|开户账号|卡号"
    for m in re.finditer(r"(?<![0-9A-Za-z])\d(?:[ -]?\d){0,29}(?![0-9A-Za-z])",文本):
        v = re.sub(r"\D","",m.group())
        # 短账号紧随标签，或独占明确账号列，不借用前面别的字段。
        明确账号 = ((m.group() == 文本.strip() and re.search(账号字段,块.位置.get("列字段","")))
                    or re.search(r"(?<!\[)(?:"+账号字段+r")\s*(?:[:：]|为)?\s*$",前字段(m.start())))
        if (银行卡校验(v) and not 标签(m.start(),r"物料编号|产品编号|商品编码")) or 明确账号:
            记录(m.start(),m.end(),"bank_account",3)
    for m in phonenumbers.PhoneNumberMatcher(文本,"CN"):
        end = m.end
        分机 = re.match(r"\s*(?:转|分机|ext\.?|x)\s*\d{1,6}",文本[end:],re.I)
        if 分机:
            end += 分机.end()
        类型 = "mobile_phone" if phonenumbers.number_type(m.number) in {phonenumbers.PhoneNumberType.MOBILE,phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE} else "landline"
        记录(m.start,end,类型,2)
    # 明确中国服务电话及座机的括号/分机写法，补充解析库不接受的排版。
    for m in re.finditer(r"(?<!\d)(?:[48]00[- ]?\d{3}[- ]?\d{4}|\(0\d{2,3}\)[ -]?\d{7,8}|0\d{2,3}[- ]?\d{7,8})(?:\s*(?:转|分机|ext\.?|x)\s*\d{1,6})?(?!\d)",文本,re.I):
        记录(m.start(),m.end(),"landline",2)
    邮箱 = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_\x60{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    for 模式, 类型 in [(邮箱,"email"),(PLATE_NUMBER_PATTERN,"plate_number"),(IPV4_PATTERN,"ip_address"),(MAC_ADDRESS_PATTERN,"mac_address")]:
        for m in 模式.finditer(文本):
            记录(m.start(),m.end(),类型,2)
    if 启用日期:
        模式 = r"(?<!\d)(?:19|20)\d{2}(?:年\d{1,2}月(?:\d{1,2}日)?|[-/]\d{1,2}(?:[-/]\d{1,2})?)(?!\d)|[〇零一二三四五六七八九]{4}年[一二三四五六七八九十]{1,3}月(?:[一二三四五六七八九十]{1,3}日)?"
        for m in re.finditer(模式,文本):
            if _有效日期(m.group()):
                记录(m.start(),m.end(),"date",4)
    if 启用月日 and 启用日期:
        for m in re.finditer(r"(?<![\d年])\d{1,2}月\d{1,2}日",文本):
            if _有效日期(m.group()):
                记录(m.start(),m.end(),"date",4)
    if 启用金额:
        for m in re.finditer(r"(?<![\dA-Za-z.,])\d+(?:\.\d+)?(?![\dA-Za-z.,])",文本):
            独占单元格 = m.group() == 文本.strip()
            字段 = 块.位置.get("列字段","") if 独占单元格 else 前字段(m.start())
            金额字段 = r"金额|价款|总价|余额|收入|支出|成本|费用|利润"
            字段匹配 = 金额字段 if 独占单元格 else r"(?:"+金额字段+r")\s*(?:\([^()]*\))?\s*[:：]?\s*$"
            if re.search(字段匹配,字段):
                单位 = re.findall(r"(?:万|亿)?(?:港元|美元|欧元|日元|英镑|元)",字段)
                记录(m.start(),m.end(),"amount",4,金额单位=单位[-1] if 单位 else "元")
        for m in AMOUNT_NO_UNIT_PATTERN.finditer(文本):
            记录(m.start(1),m.end(1),"amount",4)
        for m in re.finditer(r"(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*(?:(?:万|亿)?(?:港元|美元|欧元|日元|英镑|元)|万|亿)|[零壹贰叁肆伍陆柒捌玖拾佰仟万亿]+(?:元|圆)(?:整|[零壹贰叁肆伍陆柒捌玖拾]+角(?:[零壹贰叁肆伍陆柒捌玖拾]+分)?)?",文本):
            记录(m.start(),m.end(),"amount",4)
    # 校验充分的证件优先；同类保留更长跨度（含分机、完整日期）。
    选中 = []
    for 优先,m in sorted(命中,key=lambda x:(x[0],-(x[1].结束-x[1].开始))):
        if m.类型 == "amount":
            if 块.原文[m.结束:m.结束+1] == "余":
                continue
            m.替换值 = m.替换值 or 金额模糊值(unicodedata.normalize("NFKC",m.原词))
            if m.替换值 is None:
                continue
        elif m.类型 == "date" and not 启用月日:
            m.替换值 = m.原词[:2]+"X"+m.原词[3:]
        if not any(m.开始 < p.结束 and p.开始 < m.结束 for p in 选中):
            选中.append(m)
    return sorted(选中,key=lambda m:m.开始)
