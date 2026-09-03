from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


LMSTUDIO_HTTP_CONFIG_PATH = (
    Path.home() / ".lmstudio" / ".internal" / "http-server-config.json"
)


def 读取lm_studio配置() -> dict:
    try:
        return json.loads(LMSTUDIO_HTTP_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


SETTINGS_PATH = Path(__file__).resolve().parents[1] / "settings.json"


def 读取用户设置() -> dict:
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def 探测lm_studio地址() -> str:
    用户设置 = 读取用户设置()
    用户端口 = 用户设置.get("lm_port")
    if 用户端口:
        try:
            端口 = int(用户端口)
            return f"http://127.0.0.1:{端口}/v1"
        except (TypeError, ValueError):
            pass
    配置 = 读取lm_studio配置()
    主机 = str(配置.get("networkInterface") or "127.0.0.1").strip() or "127.0.0.1"
    if 主机 in {"0.0.0.0", "::"}:
        主机 = "127.0.0.1"
    try:
        端口 = int(配置.get("port") or 1234)
    except (TypeError, ValueError):
        端口 = 1234
    return f"http://{主机}:{端口}/v1"


def 获取lm_studio模型列表() -> list[dict]:
    import requests
    地址 = 探测lm_studio地址()
    响应 = requests.get(f"{地址.removesuffix('/v1')}/api/v0/models", timeout=(180, 360))
    响应.raise_for_status()
    return list(响应.json().get("data") or [])


def _是否可用于文本对话(模型信息: dict) -> bool:
    类型 = str(模型信息.get("type") or "").lower()
    return 类型 in {"", "llm", "vlm"}


def 选择首选文本模型(模型列表: list[dict]) -> str:
    if not 模型列表:
        return ""

    for 模型 in 模型列表:
        if str(模型.get("state") or "").lower() != "loaded":
            continue
        if not _是否可用于文本对话(模型):
            continue
        return str(模型.get("id") or "")
    return ""


def 探测lm_studio状态() -> dict:
    结果 = {"已启动": False, "模型名称": "", "模型已加载": False}
    try:
        模型列表 = 获取lm_studio模型列表()
        结果["已启动"] = True
        模型名称 = 选择首选文本模型(模型列表)
        if 模型名称:
            结果["模型已加载"] = True
            结果["模型名称"] = 模型名称
    except Exception:
        pass
    return 结果


# ====== 在线 API（OpenAI 格式兼容）======
# 与上面本地 LM Studio 函数平行，ner引擎根据 llm_mode 选择调用哪一组


def 规范化在线api地址(原始地址: str) -> str:
    """智能规范化在线 API 地址，统一规范化到 /v1 这一级。

    规则：去空白 -> 补协议头 -> 去尾斜杠 -> 正则提取到版本号（/v1、/v3 等）为止 -> 没有则补 /v1。
    处理用户直接从 curl 复制完整地址（含 /v1/chat/completions 或 /v3/chat/completions）的情况。
    """
    地址 = 原始地址.strip()
    if not 地址:
        return ""
    if not 地址.startswith(("http://", "https://")):
        地址 = "https://" + 地址
    地址 = 地址.rstrip("/")
    import re
    m = re.match(r"^(https?://.*?/v\d+)(?:/|$|\?|#)", 地址)
    if m:
        return m.group(1)
    return 地址 + "/v1"


def 获取在线api模型列表(api_base: str, api_key: str) -> list[dict]:
    """调用 GET {api_base}/models 获取模型列表，带 Authorization 头。

    返回格式与 获取lm_studio模型列表() 对齐：[{"id": "...", ...}, ...]
    """
    import requests
    规范化地址 = 规范化在线api地址(api_base)
    if not 规范化地址:
        raise ValueError("API 地址为空")
    if not api_key:
        raise ValueError("API 密钥为空")
    响应 = requests.get(
        f"{规范化地址}/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=(180, 360),
    )
    响应.raise_for_status()
    return list(响应.json().get("data") or [])


def 探测在线api状态(api_base: str, api_key: str, model: str = "") -> dict:
    """检测在线 API 连通性，返回格式与 探测lm_studio状态() 对齐。

    返回：{"已启动": bool, "模型名称": str, "模型已加载": bool}
    """
    结果 = {"已启动": False, "模型名称": "", "模型已加载": False}
    try:
        模型列表 = 获取在线api模型列表(api_base, api_key)
        结果["已启动"] = True
        if model:
            结果["模型名称"] = model
            已匹配 = False
            for m in 模型列表:
                if str(m.get("id") or "") == model:
                    结果["模型已加载"] = True
                    已匹配 = True
                    break
            # 某些服务商（如火山代码模型）的模型名是别名，不出现在 /models 列表里。
            # 列表里找不到时，发一条极小的对话消息做真实冒烟测试，能通就认为可用，
            # 避免把“能用的别名”误判成“模型未匹配”。
            if not 已匹配:
                规范化地址 = 规范化在线api地址(api_base)
                try:
                    import requests
                    _冒烟 = requests.post(
                        f"{规范化地址}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": "OK"}],
                            "temperature": 0.0,
                            "stream": False,
                        },
                        timeout=(30, 60),
                    )
                    _冒烟.raise_for_status()
                    结果["模型已加载"] = True
                except Exception:
                    结果["模型已加载"] = False
        else:
            if 模型列表:
                第一个 = str(模型列表[0].get("id") or "")
                if 第一个:
                    结果["模型已加载"] = True
                    结果["模型名称"] = 第一个
    except Exception:
        pass
    return 结果


class MinerU引擎:
    def 是否可用(self) -> bool:
        return shutil.which("mineru") is not None

    def pdf转文本(self, 文件路径: str, 超时: int = 360) -> str:
        mineru路径 = shutil.which("mineru")
        if not mineru路径:
            raise RuntimeError("未找到官方 mineru 命令，请先安装 MinerU CLI。")

        with tempfile.TemporaryDirectory(prefix="脱敏_mineru_") as 临时目录:
            命令 = [
                mineru路径,
                "-p", 文件路径,
                "-o", 临时目录,
                "-b", "vlm-http-client",
            ]
            try:
                结果 = subprocess.run(
                    命令,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=超时,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
            except subprocess.TimeoutExpired:
                raise RuntimeError(f"MinerU 处理超时（{超时}秒）")

            if 结果.returncode != 0:
                错误信息 = 结果.stderr or 结果.stdout or f"退出码 {结果.returncode}"
                raise RuntimeError(f"MinerU 处理失败：{错误信息}")

            return _提取markdown输出(临时目录)


def _提取markdown输出(目录: str) -> str:
    根 = Path(目录)
    full_md列表 = sorted(根.rglob("full.md"))
    if full_md列表:
        return full_md列表[0].read_text(encoding="utf-8")

    md文件列表 = sorted(
        文件
        for 文件 in 根.rglob("*.md")
        if not 文件.name.endswith("_layout.md") and not 文件.name.endswith("_span.md")
    )
    if len(md文件列表) == 1:
        return md文件列表[0].read_text(encoding="utf-8")

    raise ValueError("MinerU 输出中未找到 Markdown 文件")


默认ocr引擎 = MinerU引擎()
