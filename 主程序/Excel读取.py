"""任务内复用独立 Excel，按有限区域读取公式计算值。"""
from collections import defaultdict
from pathlib import Path

from openpyxl.utils.cell import coordinate_from_string


class Excel公式读取会话:
    def __init__(self, 取消检查=None):
        self._取消检查 = 取消检查
        self._app = None
        self._com = None
        self._启动错误 = ""
        self.问题 = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._释放()

    def _检查取消(self):
        if self._取消检查 and self._取消检查():
            raise RuntimeError("已取消 Excel 读取")

    def _启动(self):
        if self._启动错误:
            raise RuntimeError(self._启动错误)
        if self._app is not None:
            return
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            self._com = pythoncom
            self._app = win32com.client.DispatchEx("Excel.Application")
            self._app.Visible = False
            self._app.DisplayAlerts = False
            self._app.EnableEvents = False
            self._app.AskToUpdateLinks = False
            self._app.AutomationSecurity = 3
        except Exception as exc:
            self._启动错误 = f"无法启动独立 Excel，请检查 Microsoft Excel 和 pywin32：{type(exc).__name__}"
            self._释放()
            raise RuntimeError(self._启动错误) from exc

    def _释放(self):
        app, com = self._app, self._com
        self._app = self._com = None
        try:
            if app is not None:
                app.Quit()
        except Exception as exc:
            self.问题.append(f"本任务 Excel 实例未正常退出：{type(exc).__name__}")
        finally:
            if com is not None:
                com.CoUninitialize()

    def 读取(self, 路径, 单元格列表):
        分组 = defaultdict(list)
        for 表名, 坐标 in 单元格列表:
            列, 行 = coordinate_from_string(坐标)
            分组[(表名, 列)].append((行, 坐标))
        if not 分组:
            return {}
        self._检查取消()
        self._启动()
        book = None
        try:
            book = self._app.Workbooks.Open(str(Path(路径).resolve()), UpdateLinks=0, ReadOnly=True)
            self._检查取消()
            self._app.CalculateFullRebuild()
            结果 = {}
            for (表名, 列), 位置 in 分组.items():
                sheet = book.Worksheets(表名)
                位置 = sorted(set(位置))
                起 = 0
                while 起 < len(位置):
                    self._检查取消()
                    止 = 起 + 1
                    首行 = 位置[起][0]
                    # ponytail: 每列至多取 4096 行；跨列密集表若仍慢再合并矩形。
                    while 止 < len(位置) and 位置[止][0] - 首行 < 4096:
                        止 += 1
                    末行 = 位置[止-1][0]
                    数组 = sheet.Range(f"{列}{首行}:{列}{末行}").Value2
                    if 首行 == 末行:
                        数组 = ((数组,),)
                    for 行, 坐标 in 位置[起:止]:
                        值 = 数组[行-首行][0]
                        # COM 将 Excel 错误传成 HRESULT 整数；同值普通数字不能直接丢弃。
                        if isinstance(值, int) and -2146828288 <= 值 < -2146762752:
                            if sheet.Evaluate(f"ISERROR({坐标})"):
                                continue
                        if 值 is not None:
                            结果[(表名, 坐标)] = 值
                    起 = 止
            return 结果
        finally:
            if book is not None:
                try:
                    book.Close(SaveChanges=False)
                except Exception as exc:
                    self.问题.append(f"工作簿未正常关闭：{Path(路径).name}（{type(exc).__name__}）")
                    self._启动错误 = "本任务 Excel 工作簿关闭失败，后续公式未复算"
                    self._释放()


def 读取Excel公式值(路径, 单元格列表, 会话=None):
    if 会话 is not None:
        return 会话.读取(路径, 单元格列表)
    with Excel公式读取会话() as 独立会话:
        结果 = 独立会话.读取(路径, 单元格列表)
    if 独立会话.问题:
        raise RuntimeError("；".join(独立会话.问题))
    return 结果
