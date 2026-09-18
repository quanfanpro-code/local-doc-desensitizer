"""使用虚构标注比较真实模型；接口配置只从标准输入读取，不保存密钥。"""
import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import re
import sys
import time

项目 = Path(__file__).resolve().parents[1]


def 评分(标准, 实际):
    return {"漏检":len(标准.keys()-实际.keys()),"误检":len(实际.keys()-标准.keys()),
        "错误关联":sum(标准[k]!=实际[k] for k in 标准.keys() & 实际.keys())}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline",action="store_true")
    p.add_argument("--current",action="store_true")
    args = p.parse_args()
    if args.baseline == args.current:
        p.error("选择 --baseline 或 --current")
    源目录 = 项目.parent / "实施前基线_576e2668" if args.baseline else 项目
    sys.path.insert(0,str(源目录))
    from 主程序.ner引擎 import NER引擎, 全局映射表
    import requests
    接入 = json.loads(sys.stdin.read())
    数据 = json.loads((项目/"开发测试/样例/机构识别标注.json").read_text(encoding="utf-8-sig"))
    输出目录 = 项目.parent / ("模型评测_"+("改前_" if args.baseline else "改后_")+datetime.now().strftime("%Y%m%d_%H%M%S"))
    输出目录.mkdir()
    报告 = {"模型":接入["model"],"模式":"改前" if args.baseline else "改后","文档":[]}
    原请求 = requests.post
    请求记录 = []
    def 计量请求(*a,**kw):
        # 相同模型和采样参数；两代流程自己的提示、调用次数均保持真实。
        if "json" in kw and "messages" in kw["json"]:
            kw["json"]["temperature"] = 0
            kw["json"]["max_tokens"] = 8192
            kw["json"]["chat_template_kwargs"] = {"enable_thinking":False}
        start = time.monotonic()
        r = 原请求(*a,**kw)
        try:
            j = r.json()
            请求记录.append({"秒":round(time.monotonic()-start,3),"状态码":r.status_code,"用量":j.get("usage",{})})
        except ValueError:
            请求记录.append({"状态码":r.status_code})
        return r
    requests.post = 计量请求
    for 文档 in 数据["文档"]:
        print("开始："+文档["名称"],flush=True)
        原文块 = {b["id"]:b["text"]*b.get("repeat",1) for b in 文档["块"]}
        标准 = {}
        for 编号,text,n,主体 in 文档["标准"]:
            m = list(re.finditer(re.escape(text),原文块[编号]))[n-1]
            标准[(编号,m.start(),m.end())] = 主体
        eng = NER引擎()
        eng._读取llm配置 = lambda:接入
        eng._MODEL = 接入["model"]
        start = time.monotonic(); 请求记录.clear()
        m = 全局映射表(); 实际 = {}; 出错 = []
        try:
            if args.baseline:
                eng._可用 = True
                eng._检测lm可用性 = lambda:True
                text = "\n".join(原文块.values())
                masked = eng.文本脱敏(text,m,启用日期=False,启用金额=False)
                pattern = re.compile("|".join(re.escape(x) for x in sorted(m.正向映射,key=len,reverse=True))) if m.正向映射 else None
                for 编号,原字 in 原文块.items():
                    for hit in pattern.finditer(原字) if pattern else []:
                        token = m.正向映射[hit.group()]
                        root = token.split("]")[0]+"]"
                        主体 = "Nh" if token.startswith("[人物") else "Ns" if token.startswith("[地址") else m.反向映射.get(root,hit.group())
                        实际[(编号,hit.start(),hit.end())] = 主体
                roundtrip = m.批量还原文本(masked) == text
                明细 = {"映射":m.正向映射}
            else:
                from 主程序.识别结果 import 文本块,按位置替换
                from 主程序.定位写回 import 准备替换
                blocks = [文本块(k,v,{}) for k,v in 原文块.items()]
                result = eng.识别文档(blocks)
                出错 = result.未完成
                for hit in result.出现:
                    en = result.机构.get(hit.机构编号,{})
                    主体 = en.get("canonical") or (en.get("names") or [hit.原词])[0] if hit.类型=="Ni" else hit.类型
                    实际[(hit.块编号,hit.开始,hit.结束)] = 主体
                spans = 准备替换(blocks,result,m)
                text = "\n".join(原文块.values())
                masked = "\n".join(按位置替换(b.原文,spans.get(b.编号,[])) for b in blocks)
                roundtrip = m.批量还原文本(masked) == text
                明细 = asdict(result)
            (输出目录/(文档["名称"]+"_脱敏.txt")).write_text(masked,encoding="utf-8-sig")
            映射路径 = 输出目录/(文档["名称"]+"_映射.json")
            m.保存到文件(映射路径)
            重载 = 全局映射表()
            重载.从文件加载(映射路径)
            roundtrip = 重载.批量还原文本(masked) == text
        except Exception as exc:
            出错.append({"原因":str(exc),"类型":type(exc).__name__})
            roundtrip = False
            明细 = {}
        统计 = 评分(标准,实际)
        项 = {"名称":文档["名称"],"原文字数":sum(map(len,原文块.values())),"标准出现数":len(标准),
            **统计,"准确还原":roundtrip,"耗时秒":round(time.monotonic()-start,3),
            "请求":list(请求记录),"未完成":出错,
            "漏检明细":[[list(k),标准[k]] for k in 标准.keys()-实际.keys()],
            "误检明细":[[list(k),实际[k]] for k in 实际.keys()-标准.keys()],
            "错连明细":[[list(k),标准[k],实际[k]] for k in 标准.keys() & 实际.keys() if 标准[k]!=实际[k]]}
        报告["文档"].append(项)
        (输出目录/(文档["名称"]+"_识别.json")).write_text(json.dumps(明细,ensure_ascii=False,indent=2,default=list),encoding="utf-8-sig")
        # 各次落入独立文件，不覆盖已有阶段证据。
        (输出目录/(str(len(报告["文档"]))+"_评测.json")).write_text(json.dumps(报告,ensure_ascii=False,indent=2),encoding="utf-8-sig")
        print(json.dumps(项,ensure_ascii=False),flush=True)
    print(str(输出目录),flush=True)


if __name__ == "__main__":
    main()
