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
        self,
        文件路径列表: list[str],
        输出目录: str | None = None,
        进度回调: Callable[[str], None] | None = None,
    ) -> 脱敏处理结果:
        self._取消标记 = False
        结果 = 脱敏处理结果()
        目标目录 = 输出目录 or ""

        if not 文件路径列表:
            raise ValueError("没有找到支持的文件")
        if not 目标目录:
            目标目录 = str(Path(文件路径列表[0]).parent)
        结果.输出目录 = 目标目录

        总数 = len(文件路径列表)

        for 序号, 文件路径 in enumerate(文件路径列表, 1):
            if self._取消标记:
                break
            try:
                映射 = 全局映射表()
                文本 = self._提取文本自动处理(文件路径, 进度回调)
                if 文本:
                    # 调试日志默认关闭（会把原文写入输出目录，有泄露风险）；
                    # 需要排查时在 settings.json 里加 "debug_ner_log": true 开启
                    if 读取用户设置().get("debug_ner_log"):
                        _调试日志路径 = str(Path(目标目录) / f"{Path(文件路径).stem}_NER调试.log")
                        NER引擎.启用调试日志(_调试日志路径)
                    try:
                        def _ner进度(当前块, 总块数, 额外消息=None, _序号=序号, _文件=文件路径):
                            if 额外消息 is not None:
                                if 进度回调:
                                    进度回调(
                                        f"[{_序号}/{总数}] "
                                        f"{Path(_文件).name} — {额外消息}"
                                    )
                                return
                            if 进度回调:
                                if 当前块 < 总块数:
                                    进度回调(
                                        f"[{_序号}/{总数}] "
                                        f"{Path(_文件).name} — NER {当前块+1}/{总块数}"
                                    )
                                else:
                                    进度回调(
                                        f"[{_序号}/{总数}] "
                                        f"{Path(_文件).name} — NER 完成"
                                    )
                        self._ner.文本脱敏(文本, 映射, 进度回调=_ner进度,
                                            启用日期=self.启用日期, 启用月日=self.启用月日, 启用金额=self.启用金额)
                    finally:
                        NER引擎.关闭调试日志()

                if 进度回调:
                    进度回调(f"[{序号}/{总数}] {Path(文件路径).name} — 映射完成({len(映射.正向映射)}项)，开始脱敏...")

                后缀 = Path(文件路径).suffix.lower()
                if 后缀 == ".pdf":
                    try:
                        是否扫描 = 判断是否扫描版pdf(文件路径)
                    except Exception:
                        是否扫描 = False
                    if 是否扫描:
                        if 进度回调:
                            进度回调(f"[{序号}/{总数}] {Path(文件路径).name} — 扫描版PDF，生成纯文本脱敏输出")
                        # 扫描版PDF没有文字层，必须用OCR出的文本生成md，不能重新从文件提取
                        md路径 = 生成脱敏md(文件路径, 映射, 目标目录, 原始文本=文本)
                        结果.成功文件.append(md路径)
                        映射表路径 = self._构建单文件映射表路径(文件路径, 目标目录)
                        映射.保存到文件(映射表路径)
                        结果.映射表路径列表.append(映射表路径)
                        continue

                脱敏路径 = 脱敏并保存原格式(文件路径, 映射, 目标目录)
                if 后缀 not in (".txt", ".md"):
                    生成脱敏md(文件路径, 映射, 目标目录)
                结果.成功文件.append(脱敏路径)

                映射表路径 = self._构建单文件映射表路径(文件路径, 目标目录)
                映射.保存到文件(映射表路径)
                结果.映射表路径列表.append(映射表路径)

                if 进度回调:
                    进度回调(f"[{序号}/{总数}] {Path(文件路径).name} — 脱敏完成 ✓")
            except Exception as exc:
                结果.失败文件.append((文件路径, str(exc)))

        return 结果

    def 还原文件列表(
        self,
        文件路径列表: list[str],
        映射表路径: str | None = None,
        输出目录: str | None = None,
        进度回调: Callable[[str], None] | None = None,
    ) -> 脱敏处理结果:
        from 主程序.格式保持器 import 还原并保存原格式

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
                结果.成功文件.append(还原路径)
                if 进度回调:
                    进度回调(f"还原完成 [{序号}/{总数}] {Path(文件路径).name}")
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
