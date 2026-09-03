from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

try:
    import customtkinter as ctk
    from tkinter import filedialog, messagebox
except ImportError:
    ctk = None
    filedialog = None
    messagebox = None

try:
    from .文档解析器 import 收集支持的文件
    from .脱敏处理器 import 脱敏处理器
    from .ner引擎 import 全局映射表
    from .mineru桥接 import 探测lm_studio状态
except ImportError:
    CURRENT_DIR = Path(__file__).resolve().parent
    # 主程序目录 + 项目根目录都入路径，直接运行 python 主程序/app.py 时
    # 子模块里的 "from 主程序.xxx" 包导入才能找到
    for _p in (str(CURRENT_DIR.parent), str(CURRENT_DIR)):
        if _p not in sys.path:
            sys.path.insert(0, _p)
    from 文档解析器 import 收集支持的文件
    from 脱敏处理器 import 脱敏处理器
    from ner引擎 import 全局映射表
    from mineru桥接 import 探测lm_studio状态

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = PROJECT_ROOT / "settings.json"


def load_settings(settings_path: str) -> dict:
    path = Path(settings_path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_settings(settings_path: str, settings: dict) -> None:
    path = Path(settings_path)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


文件对话框类型 = [
    (
        "支持的文件",
        "*.txt *.md *.docx *.xlsx *.pptx *.pdf",
    )
]


class 脱敏工具GUI(ctk.CTk if ctk else object):
    def __init__(self):
        if ctk is None:
            raise RuntimeError("未安装 customtkinter，请先安装 requirements.txt 中的依赖。")

        super().__init__()
        self.settings = load_settings(str(SETTINGS_PATH))
        self.is_processing = False
        self.cancel_flag = False
        self._processor = None
        self._开始时间 = None
        self._计时after_id = None
        self._计时running = False

        self.title("本地文档脱敏工具")
        self.geometry("860x700")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.header_card_style = {
            "corner_radius": 12,
            "fg_color": ("#F6F8FB", "#151A22"),
            "border_width": 1,
            "border_color": ("#D7DEE8", "#222A36"),
        }
        self.surface_card_style = {
            "corner_radius": 12,
            "fg_color": ("#F9FAFB", "#181E27"),
            "border_width": 1,
            "border_color": ("#E3E8EF", "#242D3A"),
        }
        self.action_button_style = {
            "width": 132,
            "height": 36,
            "fg_color": ("#2F77B5", "#1F5E95"),
            "hover_color": ("#2A6CA5", "#1A527F"),
        }
        self.secondary_button_style = {
            "width": 116,
            "height": 32,
            "fg_color": "#1565C0",
            "hover_color": "#0D47A1",
        }
        self.ghost_button_style = {
            "width": 116,
            "height": 32,
            "fg_color": "transparent",
            "hover_color": ("#E5E7EB", "#2F3642"),
            "border_width": 1,
            "border_color": ("#9CA3AF", "#4B5563"),
        }

        self.build_ui()
        self.append_log("系统就绪。选择文件后点击【开始脱敏】或【开始还原】。")
        self._检测lm状态()

    def build_ui(self):
        self.settings_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.settings_frame.grid(row=0, column=0, padx=24, pady=(18, 10), sticky="ew")
        self.settings_frame.grid_columnconfigure(0, weight=3)
        self.settings_frame.grid_columnconfigure(1, weight=2)

        self.input_card = ctk.CTkFrame(self.settings_frame, **self.surface_card_style)
        self.input_card.grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        self.input_card.grid_columnconfigure(0, weight=1)

        self.input_title = ctk.CTkLabel(
            self.input_card, text="输入来源", font=ctk.CTkFont(size=13, weight="bold")
        )
        self.input_title.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="w")

        self.entry_input = ctk.CTkEntry(
            self.input_card,
            height=34,
            placeholder_text="选择单个文件或一个文件夹",
            state="readonly",
        )
        self.entry_input.grid(row=1, column=0, padx=16, pady=(0, 10), sticky="ew")

        self.input_actions = ctk.CTkFrame(self.input_card, fg_color="transparent")
        self.input_actions.grid(row=2, column=0, padx=16, pady=(0, 14), sticky="w")

        self.btn_select_file = ctk.CTkButton(
            self.input_actions, text="选择文件", command=self.browse_file, **self.secondary_button_style
        )
        self.btn_select_file.grid(row=0, column=0, padx=(0, 10), sticky="w")

        self.btn_select_folder = ctk.CTkButton(
            self.input_actions, text="选择文件夹", command=self.browse_folder, **self.secondary_button_style
        )
        self.btn_select_folder.grid(row=0, column=1, padx=(0, 10), sticky="w")

        self.checkbox_subfolders = ctk.CTkCheckBox(
            self.input_actions, text="包含子文件夹", font=ctk.CTkFont(size=12)
        )
        self.checkbox_subfolders.grid(row=0, column=2, sticky="w")

        self.output_card = ctk.CTkFrame(self.settings_frame, **self.surface_card_style)
        self.output_card.grid(row=0, column=1, padx=(8, 0), sticky="nsew")
        self.output_card.grid_columnconfigure(0, weight=1)

        self.output_title = ctk.CTkLabel(
            self.output_card, text="输出位置", font=ctk.CTkFont(size=13, weight="bold")
        )
        self.output_title.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="w")

        self.entry_output = ctk.CTkEntry(
            self.output_card,
            height=34,
            placeholder_text="可选：留空则输出到原文件目录",
            state="readonly",
        )
        self.entry_output.grid(row=1, column=0, padx=16, pady=(0, 10), sticky="ew")

        self.output_actions = ctk.CTkFrame(self.output_card, fg_color="transparent")
        self.output_actions.grid(row=2, column=0, padx=16, pady=(0, 14), sticky="w")

        self.btn_select_output = ctk.CTkButton(
            self.output_actions, text="选择目录", command=self.browse_output, **self.secondary_button_style
        )
        self.btn_select_output.grid(row=0, column=0, padx=(0, 10), sticky="w")

        self.btn_clear_output = ctk.CTkButton(
            self.output_actions, text="清空", command=self.clear_output, **self.ghost_button_style
        )
        self.btn_clear_output.grid(row=0, column=1, sticky="w")

        self.ctrl_card = ctk.CTkFrame(self, **self.surface_card_style)
        self.ctrl_card.grid(row=1, column=0, padx=24, pady=(0, 10), sticky="ew")
        self.ctrl_card.grid_columnconfigure(0, weight=2)
        self.ctrl_card.grid_columnconfigure(1, weight=1)
        self.ctrl_card.grid_columnconfigure(2, weight=3)

        lm_frame = ctk.CTkFrame(self.ctrl_card, fg_color="transparent")
        lm_frame.grid(row=0, column=0, padx=(14, 6), pady=12, sticky="ew")
        lm_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            lm_frame, text="LLM 配置", font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=0, column=0, columnspan=3, pady=(0, 6), sticky="w")

        # 模式切换：本地 LM Studio / 在线 API
        self.llm_mode_var = ctk.StringVar(
            value="在线 API" if self.settings.get("llm_mode") == "online" else "本地 LM Studio"
        )
        ctk.CTkSegmentedButton(
            lm_frame,
            values=["本地 LM Studio", "在线 API"],
            variable=self.llm_mode_var,
            command=self._切换llm模式,
        ).grid(row=1, column=0, columnspan=3, pady=(0, 8), sticky="ew")

        # ---- 本地模式配置区 ----
        self.lm_frame_local = ctk.CTkFrame(lm_frame, fg_color="transparent")
        self.lm_frame_local.grid(row=2, column=0, columnspan=3, sticky="ew")
        self.lm_frame_local.grid_columnconfigure(1, weight=1)

        self.lm_port_var = ctk.StringVar(
            value=str(self.settings.get("lm_port", 1234))
        )

        ctk.CTkLabel(self.lm_frame_local, text="端口:", font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, padx=(0, 6), sticky="w"
        )

        ctk.CTkEntry(
            self.lm_frame_local,
            textvariable=self.lm_port_var,
            width=80,
            height=30,
        ).grid(row=0, column=1, padx=(0, 8), sticky="w")

        ctk.CTkButton(
            self.lm_frame_local,
            text="测试连接",
            width=80,
            height=30,
            font=ctk.CTkFont(size=12),
            fg_color="#1565C0",
            hover_color="#0D47A1",
            command=self._测试lm连接,
        ).grid(row=0, column=2, sticky="w")

        # ---- 在线模式配置区（默认不显示，切换时再 grid）----
        self.lm_frame_online = ctk.CTkFrame(lm_frame, fg_color="transparent")
        self.lm_frame_online.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.lm_frame_online, text="API 地址:", font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, padx=(0, 6), sticky="w"
        )
        self.online_api_base_var = ctk.StringVar(
            value=self.settings.get("online_api_base", "")
        )
        self.entry_online_base = ctk.CTkEntry(
            self.lm_frame_online,
            textvariable=self.online_api_base_var,
            height=30,
            placeholder_text="如 http://119.6.186.168:40040",
        )
        self.entry_online_base.grid(row=0, column=1, columnspan=2, padx=(0, 8), sticky="ew")
        self.entry_online_base.bind("<FocusOut>", lambda e: self._保存在线配置())

        ctk.CTkLabel(self.lm_frame_online, text="API 密钥:", font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, padx=(0, 6), sticky="w"
        )
        self.online_api_key_var = ctk.StringVar(
            value=self.settings.get("online_api_key", "")
        )
        self.entry_online_key = ctk.CTkEntry(
            self.lm_frame_online,
            textvariable=self.online_api_key_var,
            height=30,
            show="*",
            placeholder_text="sk-xxx",
        )
        self.entry_online_key.grid(row=1, column=1, padx=(0, 4), sticky="ew")
        self.entry_online_key.bind("<FocusOut>", lambda e: self._保存在线配置())

        self.checkbox_show_key = ctk.CTkCheckBox(
            self.lm_frame_online, text="显示", font=ctk.CTkFont(size=11),
            command=self._切换密钥显示,
        )
        self.checkbox_show_key.grid(row=1, column=2, padx=(0, 8), sticky="w")

        ctk.CTkLabel(self.lm_frame_online, text="模型名:", font=ctk.CTkFont(size=12)).grid(
            row=2, column=0, padx=(0, 6), sticky="w"
        )
        self.online_model_var = ctk.StringVar(
            value=self.settings.get("online_model", "")
        )
        self.entry_online_model = ctk.CTkEntry(
            self.lm_frame_online,
            textvariable=self.online_model_var,
            height=30,
            placeholder_text="如 Qwen3-32B-0709（可点右侧拉取列表）",
        )
        self.entry_online_model.grid(row=2, column=1, padx=(0, 4), sticky="ew")
        self.entry_online_model.bind("<FocusOut>", lambda e: self._保存在线配置())

        self.btn_fetch_models = ctk.CTkButton(
            self.lm_frame_online,
            text="拉取列表",
            width=80,
            height=30,
            font=ctk.CTkFont(size=12),
            fg_color="#1565C0",
            hover_color="#0D47A1",
            command=self._拉取模型列表,
        )
        self.btn_fetch_models.grid(row=2, column=2, padx=(0, 8), sticky="w")

        ctk.CTkButton(
            self.lm_frame_online,
            text="测试连接",
            width=80,
            height=30,
            font=ctk.CTkFont(size=12),
            fg_color="#1565C0",
            hover_color="#0D47A1",
            command=self._测试lm连接,
        ).grid(row=3, column=2, pady=(4, 0), sticky="w")

        # ---- 共用状态标签（两种模式都用这个）----
        self.lm_status_label = ctk.CTkLabel(
            lm_frame,
            text="LLM: 检测中...",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60"),
        )
        self.lm_status_label.grid(row=3, column=0, columnspan=3, pady=(4, 0), sticky="w")

        # 根据当前模式显示对应的配置区
        if self.settings.get("llm_mode") == "online":
            self.lm_frame_local.grid_forget()
            self.lm_frame_online.grid(row=2, column=0, columnspan=3, sticky="ew")
        else:
            self.lm_frame_online.grid_forget()
            self.lm_frame_local.grid(row=2, column=0, columnspan=3, sticky="ew")

        # ---- 脱敏选项 ----
        options_frame = ctk.CTkFrame(self.ctrl_card, fg_color="transparent")
        options_frame.grid(row=0, column=1, padx=(6, 6), pady=12, sticky="nsew")

        选项标题 = ctk.CTkLabel(
            options_frame, text="脱敏选项", font=ctk.CTkFont(size=13, weight="bold")
        )
        选项标题.grid(row=0, column=0, columnspan=2, pady=(0, 6), sticky="w")

        self.checkbox_date = ctk.CTkCheckBox(
            options_frame, text="日期脱敏", font=ctk.CTkFont(size=12),
            command=self._日期脱敏切换,
        )
        self.checkbox_date.grid(row=1, column=0, columnspan=2, padx=(0, 0), pady=(0, 3), sticky="w")
        # 默认勾选日期脱敏
        self.checkbox_date.select()

        self.checkbox_date_full = ctk.CTkCheckBox(
            options_frame, text="含精确月日", font=ctk.CTkFont(size=12),
        )
        self.checkbox_date_full.grid(row=2, column=0, columnspan=2, padx=(20, 0), pady=(0, 3), sticky="w")
        # 默认不勾选精确月日

        self.checkbox_amount = ctk.CTkCheckBox(
            options_frame, text="金额脱敏", font=ctk.CTkFont(size=12),
        )
        self.checkbox_amount.grid(row=3, column=0, columnspan=2, padx=(0, 0), pady=(0, 0), sticky="w")
        # 默认不勾选金额脱敏

        self.checkbox_abbr_audit = ctk.CTkCheckBox(
            options_frame, text="简称强力审核", font=ctk.CTkFont(size=12),
            command=self._简称强力审核切换,
        )
        self.checkbox_abbr_audit.grid(row=4, column=0, columnspan=2, padx=(0, 0), pady=(6, 0), sticky="w")
        if self.settings.get("force_abbr_audit"):
            self.checkbox_abbr_audit.select()

        right_frame = ctk.CTkFrame(self.ctrl_card, fg_color="transparent")
        right_frame.grid(row=0, column=2, padx=(6, 14), pady=12, sticky="ew")
        right_frame.grid_columnconfigure(3, weight=1)

        self.btn_start_desensitize = ctk.CTkButton(
            right_frame,
            text="开始脱敏",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.start_desensitize,
            fg_color="#1565C0",
            hover_color="#0D47A1",
            width=84,
            height=28,
        )
        self.btn_start_desensitize.grid(row=0, column=0, padx=(0, 6), sticky="w")

        self.btn_start_restore = ctk.CTkButton(
            right_frame,
            text="开始还原",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.start_restore,
            fg_color="#1565C0",
            hover_color="#0D47A1",
            width=84,
            height=28,
        )
        self.btn_start_restore.grid(row=0, column=1, padx=(0, 6), sticky="w")

        self.btn_cancel = ctk.CTkButton(
            right_frame,
            text="取消处理",
            command=self.cancel_processing,
            state="disabled",
            fg_color="transparent",
            hover_color=("#E5E7EB", "#2F3642"),
            border_width=1,
            border_color=("#9CA3AF", "#4B5563"),
            text_color=("#374151", "#D1D5DB"),
            width=76,
            height=28,
        )
        self.btn_cancel.grid(row=0, column=2, padx=(0, 10), sticky="w")

        self.progress_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        self.progress_frame.grid(row=0, column=3, sticky="ew")
        self.progress_frame.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(self.progress_frame, text="就绪", font=ctk.CTkFont(size=12))
        self.status_label.grid(row=0, column=0, sticky="w")

        self.progress_text = ctk.CTkLabel(self.progress_frame, text="", font=ctk.CTkFont(size=12))
        self.progress_text.grid(row=0, column=1, sticky="e")

        self.progressbar = ctk.CTkProgressBar(self.progress_frame, height=3)
        self.progressbar.set(0)
        self.progressbar.grid(row=1, column=0, columnspan=2, pady=(6, 0), sticky="ew")

        self.log_card = ctk.CTkFrame(self, **self.surface_card_style)
        self.log_card.grid(row=2, column=0, padx=24, pady=(0, 18), sticky="nsew")
        self.log_card.grid_columnconfigure(0, weight=1)
        self.log_card.grid_rowconfigure(1, weight=1)

        self.log_title = ctk.CTkLabel(
            self.log_card, text="处理日志", font=ctk.CTkFont(size=14, weight="bold")
        )
        self.log_title.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="w")

        self.计时标签 = ctk.CTkLabel(
            self.log_card, text="", font=ctk.CTkFont(size=12),
            text_color=("#6B7280", "#9CA3AF"),
        )
        self.计时标签.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="e")

        self.text_log = ctk.CTkTextbox(
            self.log_card,
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
            text_color=("#1F2937", "#D1D5DB"),
            fg_color=("#FFFFFF", "#111827"),
            border_width=1,
            border_color=("#E5E7EB", "#2B3545"),
        )
        self.text_log.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self.text_log.configure(state="disabled")

    def browse_file(self):
        file_path = filedialog.askopenfilename(
            title="选择文件",
            filetypes=文件对话框类型,
        )
        if file_path:
            self.set_entry_value(self.entry_input, file_path)
            self.append_log(f"已选择文件：{file_path}")
            self.status_label.configure(text=f"已选择文件：{Path(file_path).name}")

    def browse_folder(self):
        folder_path = filedialog.askdirectory(title="选择文件夹")
        if folder_path:
            self.set_entry_value(self.entry_input, folder_path)
            self.append_log(f"已选择文件夹：{folder_path}")
            self.status_label.configure(text=f"已选择文件夹：{Path(folder_path).name}")

    def browse_output(self):
        folder_path = filedialog.askdirectory(title="选择输出目录")
        if folder_path:
            self.set_entry_value(self.entry_output, folder_path)
            self.append_log(f"已选择输出目录：{folder_path}")

    def clear_output(self):
        self.set_entry_value(self.entry_output, "")
        self.append_log("已清空输出目录，将输出到原文件目录。")

    def _日期脱敏切换(self):
        """日期脱敏主开关切换时，联动精确月日子开关的启用状态"""
        if self.checkbox_date.get():
            self.checkbox_date_full.configure(state="normal")
        else:
            self.checkbox_date_full.deselect()
            self.checkbox_date_full.configure(state="disabled")

    def browse_mapping_file(self):
        file_path = filedialog.askopenfilename(
            title="选择映射表文件",
            filetypes=[("JSON 文件", "*.json")],
        )
        return file_path

    def start_desensitize(self):
        if self.is_processing:
            messagebox.showinfo("提示", "当前已有处理任务在运行，请稍候或先取消。")
            return

        input_path = self.entry_input.get().strip()
        if not input_path:
            messagebox.showwarning("提示", "请先选择文件或文件夹。")
            return

        if not os.path.exists(input_path):
            messagebox.showerror("错误", f"路径不存在：{input_path}")
            return

        output_dir = self.entry_output.get().strip() or None
        if output_dir and not os.path.isdir(output_dir):
            messagebox.showerror("错误", f"输出目录不存在：{output_dir}")
            return

        files = 收集支持的文件(
            input_path,
            包含子文件夹=self.checkbox_subfolders.get() == 1,
        )
        if not files:
            messagebox.showwarning("提示", "没有找到可处理的受支持文件。")
            return

        启用日期 = self.checkbox_date.get() == 1
        启用月日 = self.checkbox_date_full.get() == 1 and 启用日期
        启用金额 = self.checkbox_amount.get() == 1
        processor = 脱敏处理器(
            启用日期=启用日期,
            启用月日=启用月日,
            启用金额=启用金额,
        )
        扫描版列表 = processor.检查扫描版pdf(files)

        是在线 = self.settings.get("llm_mode") == "online"
        try:
            if 是在线:
                try:
                    from .mineru桥接 import 探测在线api状态
                except ImportError:
                    from mineru桥接 import 探测在线api状态
                api_base = self.online_api_base_var.get().strip()
                api_key = self.online_api_key_var.get().strip()
                model = self.online_model_var.get().strip()
                llm_status = 探测在线api状态(api_base, api_key, model)
            else:
                llm_status = 探测lm_studio状态()
        except Exception as e:
            messagebox.showerror("探测失败", f"LLM 状态探测失败：\n{e}")
            return
        没有_lm = not (llm_status.get("已启动") and llm_status.get("模型已加载"))
        前缀 = "在线 API" if 是在线 else "LM Studio"

        if 扫描版列表:
            if 没有_lm:
                messagebox.showwarning(
                    "扫描版PDF需要LLM",
                    f"检测到 {len(扫描版列表)} 个扫描版PDF文件，但 {前缀} 未就绪。\n"
                    f"扫描版PDF必须依赖 LLM 处理，请先确保 {前缀} 已启动并可用。",
                )
                return
            self.append_log(f"检测到 {len(扫描版列表)} 个扫描版PDF，{前缀} 已就绪。")

        if 没有_lm:
            has_ner_files = any(
                Path(f).suffix.lower() in (".docx", ".txt", ".md", ".xlsx", ".pptx")
                for f in files
                if not Path(f).suffix.lower() == ".pdf"
            )
            if has_ner_files:
                reply = messagebox.askyesno(
                    f"{前缀} 未就绪",
                    f"{前缀} 未启动或模型未加载。\n\n"
                    "人名/地名/机构名将无法识别，但其他脱敏规则（手机号、身份证号、金额等）不受影响。\n\n"
                    "是否继续？（仅使用正则规则脱敏）",
                )
                if not reply:
                    return
                self.append_log(f"{前缀} 不可用，仅使用正则规则脱敏（人名/地名/机构名将被跳过）。")

        self.is_processing = True
        self.cancel_flag = False
        self._processor = processor
        self.btn_start_desensitize.configure(state="disabled")
        self.btn_start_restore.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.progressbar.set(0)
        self.progress_text.configure(text=f"0/{len(files)}")
        self.status_label.configure(text="正在脱敏处理")
        self.append_log(f"开始脱敏处理，共 {len(files)} 个文件。")
        if not 启用日期:
            self.append_log("注意：日期脱敏已关闭，日期信息不会被处理。")
        elif not 启用月日:
            self.append_log("注意：仅遮盖年份，精确月日保持原文。")
        if not 启用金额:
            self.append_log("注意：金额脱敏已关闭，金额信息不会被处理。")
        self.计时标签.configure(text="⏱ 00:00:00")
        self._启动计时()
        threading.Thread(
            target=self.run_desensitize,
            args=(files, output_dir),
            daemon=True,
        ).start()

    def start_restore(self):
        if self.is_processing:
            messagebox.showinfo("提示", "当前已有处理任务在运行，请稍候或先取消。")
            return

        input_path = self.entry_input.get().strip()
        if not input_path:
            messagebox.showwarning("提示", "请先选择要还原的文件或文件夹。")
            return

        if not os.path.exists(input_path):
            messagebox.showerror("错误", f"路径不存在：{input_path}")
            return

        output_dir = self.entry_output.get().strip() or None

        files = 收集支持的文件(
            input_path,
            包含子文件夹=self.checkbox_subfolders.get() == 1,
        )
        if not files:
            messagebox.showwarning("提示", "没有找到可还原的文件。")
            return

        processor = 脱敏处理器()
        self.is_processing = True
        self.cancel_flag = False
        self._processor = processor
        self.btn_start_desensitize.configure(state="disabled")
        self.btn_start_restore.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.progressbar.set(0)
        self.progress_text.configure(text=f"0/{len(files)}")
        self.status_label.configure(text="正在还原")
        self.append_log(f"开始还原处理，共 {len(files)} 个文件，将自动匹配映射表。")
        self.计时标签.configure(text="⏱ 00:00:00")
        self._启动计时()
        threading.Thread(
            target=self.run_restore,
            args=(files, output_dir),
            daemon=True,
        ).start()

    def cancel_processing(self):
        if not self.is_processing:
            return
        self.cancel_flag = True
        if self._processor is not None and hasattr(self._processor, "请求取消"):
            self._processor.请求取消()
        self.append_log("已请求取消，正在尝试停止当前任务。")

    def run_desensitize(self, files: list[str], output_dir: str | None):
        processor = self._processor
        文件总数 = len(files)

        def progress_callback(message: str):
            self.after(0, self.append_log, message)
            self.after(0, self.update_status_text, message)
            import re
            m = re.search(r'\[(\d+)/(\d+)\]', message)
            if m:
                当前 = int(m.group(1))
                总数 = int(m.group(2))
                self.after(0, lambda: self.progress_text.configure(text=f"{当前}/{总数}"))
                self.after(0, lambda: self.progressbar.configure(value=当前 / 总数))

        try:
            result = processor.处理文件列表(files, output_dir, progress_callback)
            if self.cancel_flag:
                self.after(0, self.update_status_text, f"已取消：成功 {result.成功数}，失败 {result.失败数}")
            elif result.失败数 > 0:
                self.after(0, self.update_status_text, f"脱敏完成：成功 {result.成功数}，失败 {result.失败数}")
            else:
                self.after(0, self.update_status_text, f"脱敏完成：全部成功 {result.成功数} 个文件")
            for 映射表 in result.映射表路径列表:
                self.after(0, self.append_log, f"映射表已保存：{映射表}")
            for 失败文件, 错误信息 in result.失败文件:
                self.after(0, self.append_log, f"失败：{Path(失败文件).name} - {错误信息}")
        finally:
            self._processor = None
            self.after(0, self.reset_ui)

    def run_restore(self, files: list[str], output_dir: str | None):
        processor = self._processor
        文件总数 = len(files)

        def progress_callback(message: str):
            self.after(0, self.append_log, message)
            self.after(0, self.update_status_text, message)
            import re
            m = re.search(r'\[(\d+)/(\d+)\]', message)
            if m:
                当前 = int(m.group(1))
                self.after(0, lambda: self.progress_text.configure(text=f"{当前}/{文件总数}"))
                self.after(0, lambda: self.progressbar.configure(value=当前 / 文件总数))

        try:
            result = processor.还原文件列表(files, 映射表路径=None, 输出目录=output_dir, 进度回调=progress_callback)
            if result.失败数 > 0:
                self.after(0, self.update_status_text, f"还原完成：成功 {result.成功数}，失败 {result.失败数}")
            else:
                self.after(0, self.update_status_text, f"还原完成：全部成功 {result.成功数} 个文件")
            for 失败文件, 错误信息 in result.失败文件:
                self.after(0, self.append_log, f"失败：{Path(失败文件).name} - {错误信息}")
        finally:
            self._processor = None
            self.after(0, self.reset_ui)

    def reset_ui(self):
        self.is_processing = False
        self.cancel_flag = False
        self._processor = None
        self._停止计时()
        self.btn_start_desensitize.configure(state="normal")
        self.btn_start_restore.configure(state="normal")
        self.btn_cancel.configure(state="disabled")

    def update_status_text(self, text: str):
        self.status_label.configure(text=text)

    def set_entry_value(self, entry, value: str):
        entry.configure(state="normal")
        entry.delete(0, "end")
        entry.insert(0, value)
        entry.configure(state="readonly")

    def _切换llm模式(self, 选择值: str):
        """segmented button 回调：切换本地/在线模式"""
        if self.is_processing:
            # 处理中拒绝切换，回滚到原选中段
            原 = "在线 API" if self.settings.get("llm_mode") == "online" else "本地 LM Studio"
            self.llm_mode_var.set(原)
            messagebox.showinfo("提示", "处理中无法切换 LLM 模式，请先取消当前任务。")
            return
        新模式 = "online" if 选择值 == "在线 API" else "local"
        self.settings["llm_mode"] = 新模式
        save_settings(str(SETTINGS_PATH), self.settings)
        # 切换显示对应的子 frame
        if 新模式 == "online":
            self.lm_frame_local.grid_forget()
            self.lm_frame_online.grid(row=2, column=0, columnspan=3, sticky="ew")
        else:
            self.lm_frame_online.grid_forget()
            self.lm_frame_local.grid(row=2, column=0, columnspan=3, sticky="ew")
        self.append_log(f"已切换到 {'在线 API' if 新模式 == 'online' else '本地 LM Studio'} 模式")
        self._刷新lm状态()

    def _保存在线配置(self):
        """在线配置输入框失焦时保存到 settings.json"""
        self.settings["online_api_base"] = self.online_api_base_var.get().strip()
        self.settings["online_api_key"] = self.online_api_key_var.get().strip()
        self.settings["online_model"] = self.online_model_var.get().strip()
        save_settings(str(SETTINGS_PATH), self.settings)

    def _切换密钥显示(self):
        """切换密钥输入框的显示/隐藏"""
        if self.checkbox_show_key.get():
            self.entry_online_key.configure(show="")
        else:
            self.entry_online_key.configure(show="*")

    def _拉取模型列表(self):
        """调 /v1/models 拉取可用模型列表，成功后打印到日志并自动填第一个"""
        api_base = self.online_api_base_var.get().strip()
        api_key = self.online_api_key_var.get().strip()
        if not api_base or not api_key:
            messagebox.showwarning("提示", "请先填写 API 地址和密钥")
            return
        self.append_log("正在拉取模型列表...")
        def _do():
            try:
                try:
                    from .mineru桥接 import 获取在线api模型列表
                except ImportError:
                    from mineru桥接 import 获取在线api模型列表
                模型列表 = 获取在线api模型列表(api_base, api_key)
                模型id列表 = [str(m.get("id") or "") for m in 模型列表 if m.get("id")]
                self.after(0, self._拉取模型列表完成, 模型id列表, None)
            except Exception as e:
                self.after(0, self._拉取模型列表完成, [], str(e))
        threading.Thread(target=_do, daemon=True).start()

    def _拉取模型列表完成(self, 模型id列表: list, 错误):
        """拉取模型列表的回调"""
        if 错误:
            self.append_log(f"拉取模型列表失败：{错误}")
            messagebox.showerror("拉取失败", f"拉取模型列表失败：\n{错误}\n\n请检查 API 地址和密钥，或手动填写模型名。")
            return
        if not 模型id列表:
            self.append_log("拉取成功但模型列表为空")
            return
        预览 = ', '.join(模型id列表[:10]) + ('...' if len(模型id列表) > 10 else '')
        self.append_log(f"拉取成功，共 {len(模型id列表)} 个模型：{预览}")
        # 如果当前模型名为空，自动填第一个
        当前模型 = self.online_model_var.get().strip()
        if not 当前模型:
            self.online_model_var.set(模型id列表[0])
            self._保存在线配置()

    def _测试lm连接(self):
        """测试连接按钮：根据当前模式验证对应后端"""
        if self.settings.get("llm_mode") == "online":
            # 在线模式
            api_base = self.online_api_base_var.get().strip()
            api_key = self.online_api_key_var.get().strip()
            if not api_base:
                messagebox.showwarning("提示", "请先填写 API 地址")
                return
            if not api_key:
                messagebox.showwarning("提示", "请先填写 API 密钥")
                return
            self._保存在线配置()
            self.append_log("正在测试在线 API 连接...")
            self._刷新lm状态()
        else:
            # 本地模式（现有逻辑）
            raw = self.lm_port_var.get().strip()
            try:
                port = int(raw)
                if not (1 <= port <= 65535):
                    raise ValueError
            except ValueError:
                messagebox.showerror("错误", "端口号必须是 1-65535 之间的整数")
                return
            self.settings["lm_port"] = port
            save_settings(str(SETTINGS_PATH), self.settings)
            self.append_log(f"LM Studio 端口已设置为 {port}，正在检测连接...")
            self._刷新lm状态()

    def _检测lm状态(self):
        """根据当前模式调对应的状态检测函数"""
        是在线 = self.settings.get("llm_mode") == "online"
        # Tkinter 变量只能在主线程读，先取好值再进后台线程
        api_base = self.online_api_base_var.get().strip() if 是在线 else ""
        api_key = self.online_api_key_var.get().strip() if 是在线 else ""
        model = self.online_model_var.get().strip() if 是在线 else ""
        def _do():
            try:
                if 是在线:
                    try:
                        from .mineru桥接 import 探测在线api状态
                    except ImportError:
                        from mineru桥接 import 探测在线api状态
                    status = 探测在线api状态(api_base, api_key, model)
                    if status["已启动"] and status["模型已加载"]:
                        模型名 = status.get("模型名称") or "未知"
                        self.after(0, self._更新lm状态, True, f"已连接（模型：{模型名}）")
                    elif status["已启动"]:
                        self.after(0, self._更新lm状态, False, "已连接但模型未匹配")
                    else:
                        self.after(0, self._更新lm状态, False, "未连接")
                else:
                    status = 探测lm_studio状态()
                    if status["已启动"] and status["模型已加载"]:
                        模型名 = status.get("模型名称", "未知")
                        self.after(0, self._更新lm状态, True, 模型名)
                    elif status["已启动"]:
                        self.after(0, self._更新lm状态, False, "模型加载中")
                    else:
                        self.after(0, self._更新lm状态, False, "未启动")
            except Exception:
                self.after(0, self._更新lm状态, False, "连接失败")
        threading.Thread(target=_do, daemon=True).start()

    def _更新lm状态(self, 可用: bool, 信息: str):
        """更新状态标签，文案根据当前模式"""
        是在线 = self.settings.get("llm_mode") == "online"
        前缀 = "在线 API" if 是在线 else "LM Studio"
        if 可用:
            self.lm_status_label.configure(
                text=f"● {前缀}: {信息}",
                text_color=("#22C55E", "#4ADE80"),
            )
            self.append_log(f"{前缀} 已就绪（{信息}）")
            if 是在线:
                # 在线模式首次连接成功时给费用提示
                if not getattr(self, '_online_fee_warned', False):
                    self._online_fee_warned = True
                    messagebox.showinfo("提示", "在线 API 连接成功！\n\n注意：在线 API 调用会产生费用，大文档脱敏可能花几毛到几块。")
        else:
            self.lm_status_label.configure(
                text=f"○ {前缀}: {信息}",
                text_color=("#EF4444", "#F87171"),
            )
            self.append_log(f"{前缀} {信息}（人名/地名/机构名识别不可用，其他脱敏规则不受影响）")

    def _刷新lm状态(self):
        """重置状态标签为检测中，文案根据当前模式"""
        是在线 = self.settings.get("llm_mode") == "online"
        前缀 = "在线 API" if 是在线 else "LM Studio"
        self.lm_status_label.configure(text=f"{前缀}: 检测中...", text_color=("gray50", "gray60"))
        self._检测lm状态()

    def _简称强力审核切换(self):
        self.settings["force_abbr_audit"] = self.checkbox_abbr_audit.get() == 1
        save_settings(str(SETTINGS_PATH), self.settings)
        if self.settings["force_abbr_audit"]:
            self.append_log("简称强力审核：已开启（会增加在线调用次数，且可能有误伤）")
        else:
            self.append_log("简称强力审核：已关闭")

    def append_log(self, message: str):
        self.text_log.configure(state="normal")
        self.text_log.insert("end", f"{message}\n")
        self.text_log.see("end")
        self.text_log.configure(state="disabled")

    def _启动计时(self):
        import time as _time
        self._开始时间 = _time.time()
        self._计时running = True
        self._更新计时显示()

    def _停止计时(self):
        self._计时running = False
        if self._计时after_id is not None:
            self.after_cancel(self._计时after_id)
            self._计时after_id = None
        if self._开始时间 is not None:
            import time as _time
            历时 = _time.time() - self._开始时间
            时 = int(历时 // 3600)
            分 = int((历时 % 3600) // 60)
            秒 = int(历时 % 60)
            self.计时标签.configure(text=f"耗时 {时:02d}:{分:02d}:{秒:02d}")
            self._开始时间 = None

    def _更新计时显示(self):
        if not self._计时running or self._开始时间 is None:
            return
        import time as _time
        历时 = _time.time() - self._开始时间
        时 = int(历时 // 3600)
        分 = int((历时 % 3600) // 60)
        秒 = int(历时 % 60)
        self.计时标签.configure(text=f"⏱ {时:02d}:{分:02d}:{秒:02d}")
        self._计时after_id = self.after(1000, self._更新计时显示)


if __name__ == "__main__":
    if ctk is None:
        raise RuntimeError("未安装 customtkinter，请先运行 pip install -r requirements.txt")
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = 脱敏工具GUI()
    app.mainloop()
