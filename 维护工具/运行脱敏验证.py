"""运行离线验证并保留样例；不永久删除测试文件。"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

项目目录 = Path(__file__).resolve().parents[1]
材料目录 = 项目目录.parent / "脱敏验证材料"
sys.path.insert(0, str(项目目录))


class 验证用临时目录:
    def __init__(self, suffix=None, prefix=None, dir=None, **kwargs):
        材料目录.mkdir(parents=True, exist_ok=True)
        self.name = tempfile.mkdtemp(suffix=suffix, prefix=prefix or "验证_", dir=材料目录)

    def __enter__(self):
        return self.name

    def __exit__(self, *args):
        self.cleanup()

    def cleanup(self):
        # 本机规则要求保留材料，测试入口不调用永久删除。
        return None


def 运行测试(测试集, *, 输出=None):
    return unittest.TextTestRunner(stream=输出 or io.StringIO(), verbosity=2).run(测试集)


def main():
    参数 = argparse.ArgumentParser(description=__doc__)
    参数.add_argument("--module", action="append", default=[])
    参数.add_argument("--all", action="store_true")
    args = 参数.parse_args()
    with ExitStack() as 栈:
        栈.enter_context(patch("tempfile.TemporaryDirectory", 验证用临时目录))
        栈.enter_context(patch("os.unlink", lambda *a, **k: None))
        栈.enter_context(patch("os.remove", lambda *a, **k: None))
        栈.enter_context(patch("shutil.rmtree", lambda *a, **k: None))
        栈.enter_context(patch("requests.sessions.Session.request", side_effect=AssertionError("离线测试不得请求网络")))
        加载器 = unittest.TestLoader()
        测试集 = (加载器.discover(str(项目目录 / "开发测试"), top_level_dir=str(项目目录))
                  if args.all else 加载器.loadTestsFromNames(args.module))
        if 测试集.countTestCases() == 0:
            参数.error("必须选择 --all 或有效 --module")
        结果 = 运行测试(测试集, 输出=sys.stdout)
    print(f"测试材料：{材料目录}")
    return 0 if 结果.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
