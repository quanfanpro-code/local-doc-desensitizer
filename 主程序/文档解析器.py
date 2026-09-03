from __future__ import annotations

from pathlib import Path


SUPPORTED_EXTENSIONS: set[str] = {
    ".txt", ".md", ".docx",
    ".xlsx", ".pptx", ".pdf",
}

_OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_ZIP_MAGIC = b"PK\x03\x04"


def 检测文件真实格式(文件路径: str) -> str | None:
    try:
        with open(文件路径, "rb") as f:
            头部 = f.read(8)
    except OSError:
        return None
    if 头部.startswith(_OLE2_MAGIC):
        return "ole2"
    if 头部.startswith(_ZIP_MAGIC):
        return "zip"
    return None


def 验证office文件格式(文件路径: str) -> None:
    后缀 = Path(文件路径).suffix.lower()
    if 后缀 not in {".docx", ".xlsx", ".pptx"}:
        return
    真实格式 = 检测文件真实格式(文件路径)
    格式映射 = {".docx": "Word", ".xlsx": "Excel", ".pptx": "PowerPoint"}
    旧版映射 = {".docx": ".doc", ".xlsx": ".xls", ".pptx": ".ppt"}
    if 真实格式 == "ole2":
        raise ValueError(
            f"该文件实际上是旧版{格式映射[后缀]}（{旧版映射[后缀]}）格式，"
            f"仅被改了扩展名为{后缀}。请先用Office另存为真正的{后缀}格式后再处理。"
        )


def _读取文本文件(路径: str) -> str:
    try:
        return Path(路径).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return Path(路径).read_text(encoding="gbk", errors="replace")


def 提取文本(文件路径: str) -> str:
    后缀 = Path(文件路径).suffix.lower()
    if 后缀 in {".txt", ".md"}:
        return _读取文本文件(文件路径)
    if 后缀 == ".docx":
        return _提取docx文本(文件路径)
    if 后缀 == ".doc":
        raise NotImplementedError("旧版 .doc 格式暂不支持，请先转换为 .docx")
    if 后缀 == ".xlsx":
        return _提取excel文本(文件路径)
    if 后缀 == ".xls":
        raise NotImplementedError("旧版 .xls 格式暂不支持，请先转换为 .xlsx")
    if 后缀 == ".pptx":
        return _提取ppt文本(文件路径)
    if 后缀 == ".ppt":
        raise NotImplementedError("旧版 .ppt 格式暂不支持，请先转换为 .pptx")
    if 后缀 == ".pdf":
        return _提取pdf文本(文件路径)
    raise ValueError(f"不支持的文件格式：{后缀}")


def _提取docx文本(路径: str) -> str:
    from docx import Document
    from 主程序._docx_xml工具 import 收集文档全部部件, 提取部件文本
    验证office文件格式(路径)
    doc = Document(路径)
    所有文本: list[str] = []
    for 部件 in 收集文档全部部件(doc):
        所有文本.extend(提取部件文本(部件))
    return "\n".join(所有文本)


def _excel单元格转文本(值) -> str:
    if 值 is None:
        return ""
    if isinstance(值, float):
        if 值 == int(值) and abs(值) >= 1e15:
            return f"{int(值)}"
        if 值 == int(值):
            return str(int(值))
        return str(值)
    return str(值)


def _提取excel文本(路径: str) -> str:
    import re
    from openpyxl import load_workbook
    验证office文件格式(路径)
    wb = load_workbook(路径, read_only=True, data_only=True)
    所有文本: list[str] = []
    _纯数字 = re.compile(r'^[\d,.\s]+$')
    _金额 = re.compile(r'(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d{1,2})?\s*(?:万元|亿元|万|亿|元|港元|美元|欧元|日元|英镑)')
    for 工作表 in wb.worksheets:
        for 行 in 工作表.iter_rows(values_only=True):
            行文本 = []
            for 单元格 in 行:
                if 单元格 is None:
                    continue
                if isinstance(单元格, (int, float)):
                    continue
                文本 = str(单元格).strip()
                if not 文本:
                    continue
                if _纯数字.match(文本):
                    continue
                if _金额.search(文本):
                    continue
                行文本.append(文本)
            if 行文本:
                所有文本.append(" ".join(行文本))
    wb.close()
    return "\n".join(所有文本)


def _提取ppt文本(路径: str) -> str:
    from pptx import Presentation
    验证office文件格式(路径)
    prs = Presentation(路径)
    所有文本: list[str] = []
    for 幻灯片 in prs.slides:
        for 形状 in 幻灯片.shapes:
            if 形状.has_text_frame:
                for 段落 in 形状.text_frame.paragraphs:
                    if 段落.text.strip():
                        所有文本.append(段落.text)
            if 形状.has_table:
                for 行 in 形状.table.rows:
                    行文本 = [单元格.text for 单元格 in 行.cells]
                    所有文本.append(" ".join(行文本))
    return "\n".join(所有文本)


def _提取pdf文本(路径: str) -> str:
    import fitz
    doc = fitz.open(路径)
    页面文本列表: list[str] = []
    for 页面 in doc:
        页面文本列表.append(页面.get_text())
    doc.close()
    return "\n".join(页面文本列表)


def 判断是否扫描版pdf(路径: str, 最小文字阈值: int = 50) -> bool:
    import fitz
    doc = fitz.open(路径)
    总字数 = sum(len(页面.get_text().strip()) for 页面 in doc)
    doc.close()
    return 总字数 < 最小文字阈值


def 收集支持的文件(路径: str, 包含子文件夹: bool = False) -> list[str]:
    目标 = Path(路径)
    if 目标.is_file():
        return [str(目标)] if 目标.suffix.lower() in SUPPORTED_EXTENSIONS else []
    if not 目标.is_dir():
        return []
    迭代器 = 目标.rglob("*") if 包含子文件夹 else 目标.glob("*")
    文件列表 = [
        str(文件)
        for 文件 in 迭代器
        if 文件.is_file() and 文件.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(文件列表)
