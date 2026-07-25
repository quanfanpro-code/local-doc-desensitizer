from __future__ import annotations

import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
项目根目录 = CURRENT_DIR.parent

OK = "[OK]"
FAIL = "[FAIL]"
WARN = "[WARN]"


def 运行自检() -> bool:
    print("=" * 50)
    print("本地文档脱敏工具 - 环境自检")
    print("=" * 50)

    全部通过 = True

    print(f"\nPython 版本：{sys.version}")
    print(f"项目目录：{项目根目录}")

    检查项 = [
        ("customtkinter", "GUI框架"),
        ("ahocorasick", "AC自动机批量替换（pyahocorasick）"),
        ("docx", "Word文档解析（python-docx）"),
        ("openpyxl", "Excel文档解析"),
        ("pptx", "PPT文档解析（python-pptx）"),
        ("fitz", "PDF解析（PyMuPDF）"),
        ("requests", "HTTP请求"),
    ]

    print("\n依赖检查：")
    for 模块名, 说明 in 检查项:
        try:
            __import__(模块名)
            print(f"  {OK} {模块名} ({说明})")
        except ImportError:
            print(f"  {FAIL} {模块名} ({说明}) - 未安装")
            全部通过 = False

    print("\n目录结构检查：")
    必要目录 = ["主程序", "开发测试", "维护工具"]
    for 目录名 in 必要目录:
        目录路径 = 项目根目录 / 目录名
        if 目录路径.is_dir():
            print(f"  {OK} {目录名}/")
        else:
            print(f"  {FAIL} {目录名}/ - 不存在")
            全部通过 = False

    必要文件 = [
        "主程序/app.py",
        "主程序/ner引擎.py",
        "主程序/文档解析器.py",
        "主程序/格式保持器.py",
        "主程序/脱敏处理器.py",
        "主程序/mineru桥接.py",
        "requirements.txt",
    ]
    print("\n核心文件检查：")
    for 文件路径 in 必要文件:
        完整路径 = 项目根目录 / 文件路径
        if 完整路径.is_file():
            print(f"  {OK} {文件路径}")
        else:
            print(f"  {FAIL} {文件路径} - 不存在")
            全部通过 = False

    import shutil
    print("\n外部工具检查：")
    mineru路径 = shutil.which("mineru")
    if mineru路径:
        print(f"  {OK} MinerU CLI：{mineru路径}")
    else:
        print(f"  {WARN} MinerU CLI 未找到（扫描版PDF需要，其他格式不受影响）")

    print("\n" + "=" * 50)
    if 全部通过:
        print("环境自检通过！所有必要依赖已安装。")
    else:
        print("环境自检发现问题，请运行：pip install -r requirements.txt")
    print("=" * 50)

    return 全部通过


if __name__ == "__main__":
    运行自检()
