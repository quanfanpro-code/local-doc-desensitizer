"""用合成数据验证正式 Excel 读取函数；保留样例和逐轮计时。"""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

项目 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(项目))
from 主程序.文档解析器 import Excel公式读取会话, 读取Excel公式值

预期循环 = ["星河", "远景贸易有限公司", "星河科技有限公司", "星河科技有限公司（供应商）", "13800138000"]


def 生成样例(路径, 数量):
    from openpyxl import Workbook
    wb = Workbook(); sheet = wb.active; sheet.title = "公式"
    数据 = wb.create_sheet("数据源")
    数据.append(["供应商", "星河科技有限公司"])
    数据.append(["客户", "远景贸易有限公司"])
    for 行 in range(1, 数量+1):
        公式 = ['="星"&"河"', '=VLOOKUP("客户",\'数据源\'!A1:B2,2,FALSE)',
              "='数据源'!B1", f'=B{行-1}&"（供应商）"', '=TEXT(13800138000,"0")'][(行-1) % 5]
        sheet.append([f"虚构案例{行}", 公式])
    wb.save(路径); wb.close()


def 运行(单文件目录=None, 批量目录=None):
    输出 = 项目.parent / ("Excel正式读取验证_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    输出.mkdir()
    if 单文件目录 is None:
        单文件目录 = 输出
        for 数量 in (8, 1000, 5000):
            生成样例(输出 / f"{数量}个公式.xlsx", 数量)
    if 批量目录 is None:
        批量目录 = 输出 / "十份文件"
        批量目录.mkdir()
        for i in range(1, 11):
            生成样例(批量目录 / f"虚构文件{i}.xlsx", 8)
    单文件 = [Path(单文件目录) / f"{n}个公式.xlsx" for n in (8, 1000, 5000)]
    批量 = [Path(批量目录) / f"虚构文件{i}.xlsx" for i in range(1, 11)]
    哈希 = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in 单文件+批量}
    记录 = []
    for 数量, 文件 in [(n, [p]) for n,p in zip((8,1000,5000), 单文件)] + [(8, 批量)]:
        耗时 = []
        for 轮 in range(3):
            位置 = [("公式",f"B{r}") for r in range(1, 数量+1)]
            开始 = time.perf_counter()
            with Excel公式读取会话() as 会话:
                值组 = [读取Excel公式值(p, 位置, 会话=会话) for p in 文件]
            耗时.append(round(time.perf_counter()-开始, 4))
            assert not 会话.问题, 会话.问题
            for 值 in 值组:
                assert len(值) == 数量
                assert [值[k] for k in 位置] == [预期循环[r % 5] for r in range(数量)]
            print(json.dumps({"公式数":数量,"文件数":len(文件),"轮次":轮+1,"秒":耗时[-1]},ensure_ascii=False),flush=True)
        记录.append({"每文件公式数":数量,"文件数":len(文件),"逐轮秒":耗时,"中位数秒":statistics.median(耗时)})
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p,h in 哈希.items())
    报告 = {"口径":"每轮包含独立实例启动、只读打开、重算、正式分块读取及退出；十文件每轮共用实例。不含模型识别。",
          "记录":记录,"全部值正确":True,"所有原件哈希不变":True,"原件哈希":哈希}
    (输出 / "效率记录.json").write_text(json.dumps(报告,ensure_ascii=False,indent=2),encoding="utf-8-sig")
    print(str(输出),flush=True)
    return 报告


if __name__ == "__main__":
    运行()
