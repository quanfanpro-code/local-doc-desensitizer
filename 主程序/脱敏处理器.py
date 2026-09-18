from __future__ import annotations

from pathlib import Path
from typing import Callable

from 主程序.文档解析器 import 提取文本, 判断是否扫描版pdf
from 主程序.ner引擎 import NER引擎, 全局映射表
from 主程序.格式保持器 import 脱敏并保存原格式, 生成脱敏md
from 主程序.mineru桥接 import 默认ocr引擎, 读取用户设置


class 脱敏处理结果:
    def __init__(self) -> None:
        self.成功文件: list[str] = []
        self.失败文件: list[tuple[str, str]] = []
        self.映射表路径列表: list[str] = []
        self.输出目录: str = ""
        self.已生成文件: list[str] = []
        self.未完成环节: list[dict] = []

    @property
    def 成功数(self) -> int:
        return len(self.成功文件)

    @property
    def 失败数(self) -> int:
        return len(self.失败文件)


class 脱敏处理器:
    def __init__(self, ocr引擎=None, 启用日期: bool = True, 启用月日: bool = False, 启用金额: bool = False) -> None:
        self._ner = NER引擎()
        self._ocr = ocr引擎 or 默认ocr引擎
        self._取消标记 = False
        self.启用日期 = 启用日期
        self.启用月日 = 启用月日
        self.启用金额 = 启用金额

    def 请求取消(self) -> None:
        self._取消标记 = True

    def _构建单文件映射表路径(self, 文件路径: str, 输出目录: str) -> str:
        stem = Path(文件路径).stem
        return str(Path(输出目录) / f"{stem}_脱敏映射表.json")

    def 处理文件列表(
        self, 文件路径列表: list[str], 输出目录: str | None = None,
        进度回调: Callable[[str], None] | None = None,
    ) -> 脱敏处理结果:
        from 主程序.文档解析器 import Excel公式读取会话
        with Excel公式读取会话(取消检查=lambda: self._取消标记) as 会话:
            结果 = self._处理文件列表(文件路径列表, 输出目录, 进度回调, 会话)
        for 问题 in 会话.问题:
            结果.未完成环节.append({"文件":"本批任务","环节":"Excel资源释放","原因":问题})
            if 进度回调:
                进度回调(问题)
        return 结果

    def _处理文件列表(self, 文件路径列表, 输出目录, 进度回调, Excel会话):
        from 主程序.文档解析器 import 读取文档块
        from 主程序.识别结果 import 文本块, 识别结果
        from 主程序.固定规则 import 固定规则识别
        from 主程序.定位写回 import 保存, 准备替换, 残留对应原文, 备份已有输出
        if not 文件路径列表:
            raise ValueError("没有找到支持的文件")
        self._取消标记 = False
        self._ner._取消检查 = lambda: self._取消标记
        结果 = 脱敏处理结果()
        目标目录 = Path(输出目录 or Path(文件路径列表[0]).parent)
        目标目录.mkdir(parents=True, exist_ok=True)
        结果.输出目录 = str(目标目录)
        使用名称 = set()
        原件路径集 = {str(Path(p).resolve()).casefold() for p in 文件路径列表}
        for 序号, 文件路径 in enumerate(文件路径列表, 1):
            if self._取消标记:
                break
            原件 = Path(文件路径)
            名称 = 原件.stem
            避让 = 0
            while 名称.casefold() in 使用名称 or any(
                    str((目标目录/f"{名称}_脱敏{s}").resolve()).casefold() in 原件路径集
                    for s in (原件.suffix,".md")):
                避让 += 1
                名称 = f"{原件.stem}_{原件.suffix.lstrip('.')}_{序号}_{避让}"
            使用名称.add(名称.casefold())
            映射 = 全局映射表()
            本文件问题 = []
            已交付 = False
            def 报告(文字):
                if 进度回调:
                    进度回调(f"[{序号}/{len(文件路径列表)}] {原件.name} — {文字}")
            def 模型进度(当前, 总数, 文字=None):
                报告(文字 or f"识别 {当前+1}/{总数}")
            try:
                块 = 读取文档块(文件路径, Excel会话=Excel会话)
                扫描输出 = 原件.suffix.lower() == ".pdf" and (not 块 or 判断是否扫描版pdf(文件路径))
                if 扫描输出:
                    文本 = self._提取文本自动处理(文件路径, 进度回调)
                    块 = [文本块(f"text:{i}",行,{"行":i}) for i,行 in enumerate(文本.splitlines(keepends=True))]
                if 读取用户设置().get("debug_ner_log"):
                    日志路径 = 目标目录 / f"{名称}_NER调试.log"
                    备份已有输出(日志路径)
                    NER引擎.启用调试日志(str(日志路径))
                try:
                    检出 = self._ner.识别文档(块, 模型进度)
                except Exception as exc:
                    检出 = 识别结果(未完成=[{"环节":"机构识别","原因":str(exc) or type(exc).__name__}])
                finally:
                    NER引擎.关闭调试日志()
                for b in 块:
                    检出.出现.extend(固定规则识别(b,self.启用日期,self.启用月日,self.启用金额))
                    if b.位置.get("公式复算未完成"):
                        检出.未完成.append({"块编号":b.编号,"环节":"公式显示值","原因":b.位置["公式复算未完成"]})
                后缀 = ".md" if 扫描输出 else 原件.suffix
                输出路径 = str(目标目录 / f"{名称}_脱敏{后缀}")
                映射路径 = str(目标目录 / f"{名称}_脱敏映射表.json")
                写回源 = str(原件.with_suffix(".md")) if 扫描输出 else 文件路径
                报告(f"检测结束，开始写回 {len(检出.出现)} 处")
                保存(写回源, 块, 检出, 映射, 输出路径)
                备份已有输出(映射路径)
                映射.保存到文件(映射路径)
                # 映射已经落盘；后续复查失败不扣住这一对可用结果。
                结果.已生成文件.append(输出路径)
                结果.映射表路径列表.append(映射路径)
                已交付 = True
                try:
                    输出块 = 读取文档块(输出路径, Excel会话=Excel会话)
                    原替换 = 准备替换(块,检出,映射)
                    复查 = self._ner.复查输出(输出块,块,检出.机构,模型进度)
                    for b in 输出块:
                        复查.出现.extend(固定规则识别(b,self.启用日期,self.启用月日,self.启用金额))
                    检出.机构.update(复查.机构)
                    新增 = []
                    for item in 复查.出现:
                        原位置 = 残留对应原文(块,输出块,原替换,item)
                        if 原位置 is not None:
                            新增.append(原位置)
                        else:
                            复查.未完成.append({"块编号":item.块编号,"环节":"残留定位","原因":"无法唯一对应原文位置"})
                    if 新增:
                        检出.出现.extend(新增)
                        映射.文件记录 = []
                        报告(f"复查发现遗漏，补充处理 {len(新增)} 处")
                        保存(写回源,块,检出,映射,输出路径)
                        备份已有输出(映射路径)
                        映射.保存到文件(映射路径)
                        输出块 = 读取文档块(输出路径, Excel会话=Excel会话)
                    for b in 输出块:
                        if b.位置.get("公式复算未完成"):
                            复查.未完成.append({"块编号":b.编号,"环节":"输出公式复算","原因":b.位置["公式复算未完成"]})
                    self._核对实际写回(块,输出块,检出,映射)
                    本文件问题.extend(复查.未完成)
                except Exception as exc:
                    本文件问题.append({"环节":"输出复查","原因":str(exc) or type(exc).__name__})
                if 后缀.lower() not in (".txt",".md"):
                    from 主程序.识别结果 import 按位置替换
                    spans = 准备替换(块,检出,映射)
                    md = 目标目录 / f"{名称}_脱敏.md"
                    备份已有输出(md)
                    md.write_text("\n".join(按位置替换(b.原文,spans.get(b.编号,[])) for b in 块),encoding="utf-8-sig")
                本文件问题.extend(检出.未完成)
                if 本文件问题:
                    结果.未完成环节.extend({"文件":文件路径,**问题} for 问题 in 本文件问题)
                    报告("文件和还原映射已生成；部分环节未完成，详见处理说明")
                else:
                    结果.成功文件.append(输出路径)
                    报告("脱敏及输出复查完成")
            except Exception as exc:
                if 已交付:
                    结果.未完成环节.append({"文件":文件路径,"环节":"附加输出","原因":str(exc)})
                else:
                    结果.失败文件.append((文件路径,str(exc)))
        return 结果

    def _核对实际写回(self, 原块, 输出块, 检出, 映射):
        from 主程序.定位写回 import 准备替换
        from 主程序.识别结果 import 按位置替换
        spans = 准备替换(原块,检出,映射)
        输出表 = {b.编号:b for b in 输出块}
        for b in 原块:
            if b.编号 not in spans:
                continue
            预期 = 按位置替换(b.原文,spans[b.编号])
            if "页" in b.位置:
                页文字 = "\n".join(x.原文 for x in 输出块 if x.位置.get("页") == b.位置["页"])
                for s,e,token in spans[b.编号]:
                    if token not in 页文字:
                        raise ValueError(f"PDF代号未写入：{b.编号}")
            elif b.编号 not in 输出表 or 输出表[b.编号].原文 != 预期:
                raise ValueError(f"输出与确认的替换结果不一致：{b.编号}")

    def 还原文件列表(
        self,
        文件路径列表: list[str],
        映射表路径: str | None = None,
        输出目录: str | None = None,
        进度回调: Callable[[str], None] | None = None,
    ) -> 脱敏处理结果:
        from 主程序.格式保持器 import 还原并保存原格式

        self._取消标记 = False
        目标目录 = 输出目录 or ""
        结果 = 脱敏处理结果()

        总数 = len(文件路径列表)

        for 序号, 文件路径 in enumerate(文件路径列表, 1):
            if self._取消标记:
                break
            try:
                文件映射表路径 = self._查找对应映射表(文件路径, 映射表路径)
                if not 文件映射表路径:
                    raise FileNotFoundError(
                        f"找不到对应的映射表文件，请确认「{Path(文件路径).name}」"
                        f"旁边的 *_脱敏映射表.json 文件存在"
                    )

                映射 = 全局映射表()
                映射.从文件加载(文件映射表路径)

                还原路径 = 还原并保存原格式(文件路径, 映射, 目标目录)
                结果.已生成文件.append(还原路径)
                if 映射.载入提示:
                    结果.未完成环节.extend({"文件":文件路径,"环节":"旧映射还原","原因":提示} for 提示 in 映射.载入提示)
                else:
                    结果.成功文件.append(还原路径)
                if 进度回调:
                    进度回调(f"还原文件已生成 [{序号}/{总数}] {Path(文件路径).name}")
                    for 提示 in 映射.载入提示:
                        进度回调("旧映射说明："+提示)
            except Exception as exc:
                结果.失败文件.append((文件路径, str(exc)))

        结果.输出目录 = 目标目录
        return 结果

    def _查找对应映射表(self, 文件路径: str, 显式路径: str | None = None) -> str | None:
        if 显式路径:
            p = Path(显式路径)
            if p.exists():
                return str(p)

        stem = Path(文件路径).stem

        清理后stem = stem
        for 后缀 in ("_脱敏", "_还原"):
            if 清理后stem.endswith(后缀):
                清理后stem = 清理后stem[:-len(后缀)]
                break

        搜索目录 = Path(文件路径).parent

        候选 = 搜索目录 / f"{清理后stem}_脱敏映射表.json"
        if 候选.exists():
            return str(候选)

        候选 = 搜索目录 / f"{stem}_脱敏映射表.json"
        if 候选.exists():
            return str(候选)

        for json文件 in 搜索目录.glob("*_脱敏映射表.json"):
            json_stem = json文件.stem.replace("_脱敏映射表", "")
            if json_stem == 清理后stem or json_stem == stem:
                return str(json文件)

        return None

    def 检查扫描版pdf(self, 文件路径列表: list[str]) -> list[str]:
        扫描版列表: list[str] = []
        for 文件路径 in 文件路径列表:
            if Path(文件路径).suffix.lower() == ".pdf":
                try:
                    if 判断是否扫描版pdf(文件路径):
                        扫描版列表.append(文件路径)
                except Exception:
                    pass
        return 扫描版列表

    def _提取文本自动处理(self, 文件路径: str, 回调: Callable[[str], None] | None = None) -> str:
        后缀 = Path(文件路径).suffix.lower()
        if 后缀 == ".pdf" and 判断是否扫描版pdf(文件路径):
            if not self._ocr.是否可用():
                raise RuntimeError("扫描版PDF需要OCR引擎，但当前OCR引擎不可用。")
            if 回调:
                回调(f"检测到扫描版PDF，使用OCR处理：{Path(文件路径).name}")
            return self._ocr.pdf转文本(文件路径)
        return 提取文本(文件路径)
