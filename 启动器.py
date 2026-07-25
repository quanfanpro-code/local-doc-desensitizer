from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
主程序目录 = CURRENT_DIR / "主程序"


def 检查依赖() -> list[str]:
    缺失列表 = []
    for 模块名 in ["customtkinter", "docx", "openpyxl", "pptx", "fitz", "ahocorasick", "requests"]:
        try:
            importlib.import_module(模块名)
        except ImportError:
            缺失列表.append(模块名)
    return 缺失列表


def 安装依赖(缺失列表: list[str]) -> bool:
    需求文件 = CURRENT_DIR / "requirements.txt"
    if not 需求文件.exists():
        return False
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(需求文件)],
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def 启动主程序():
    import os
    sys.path.insert(0, str(主程序目录))
    os.chdir(str(CURRENT_DIR))
    from 主程序.app import 脱敏工具GUI
    import customtkinter as ctk
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = 脱敏工具GUI()
    app.mainloop()


def main():
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()

    缺失 = 检查依赖()
    if 缺失:
        确认 = messagebox.askyesno(
            "环境自检",
            f"检测到以下依赖未安装：\n\n{', '.join(缺失)}\n\n"
            "是否立即安装？（需要网络连接）",
        )
        if not 确认:
            messagebox.showerror("错误", "缺少必要依赖，无法启动。")
            sys.exit(1)
        root.destroy()
        print(f"正在安装依赖：{', '.join(缺失)}...")
        if not 安装依赖(缺失):
            print("依赖安装失败，请手动运行：pip install -r requirements.txt")
            sys.exit(1)
        root = tk.Tk()
        root.withdraw()

    root.destroy()
    启动主程序()


if __name__ == "__main__":
    main()
