"""X1：PDF 脱敏/还原不得涂白图片像素，也不得用白色填充遮挡背景。

当前实现 fill=(1,1,1) 且 apply_redactions(graphics=0) 未指定 images：
- images 默认涂白与脱敏区域重叠的图片像素
- 白色填充进一步遮挡该区域背景与线条
两条路径（新定位写回、旧既有映射）的脱敏与还原都必须保留背景。
"""
from pathlib import Path
import io
import unittest

from 维护工具.运行脱敏验证 import 验证用临时目录
from 主程序.ner引擎 import 全局映射表
from 主程序.识别结果 import 出现记录, 识别结果


def _造图文pdf(路径):
    """红色图片铺满一块区域，敏感文字写在图片上方（与图片重叠）。返回图片区域。"""
    import pymupdf
    from PIL import Image
    with pymupdf.open() as doc:
        page = doc.new_page()
        data = io.BytesIO()
        Image.new("RGB", (200, 100), (200, 30, 30)).save(data, format="PNG")
        图区 = pymupdf.Rect(50, 50, 250, 150)
        page.insert_image(图区, stream=data.getvalue())
        page.insert_text((60, 100), "电话 13800138000", fontsize=12)
        doc.save(路径)
    return 图区


def _区域红色占比(pdf路径, 矩形):
    import pymupdf
    with pymupdf.open(pdf路径) as doc:
        pix = doc[0].get_pixmap(clip=矩形)
        红 = 0
        for y in range(pix.height):
            for x in range(pix.width):
                r, g, b = pix.pixel(x, y)[:3]
                if r > 120 and g < 100 and b < 100:
                    红 += 1
        return 红 / (pix.width * pix.height)


def _新流程脱敏(路径, 目录):
    from 主程序.文档解析器 import 读取文档块
    from 主程序.格式保持器 import 保存定位脱敏
    块 = 读取文档块(str(路径))
    目标 = [b for b in 块 if "13800138000" in b.原文]
    assert 目标, "造样失败：未读到敏感文字块"
    b = 目标[0]
    s = b.原文.index("13800138000")
    结果 = 识别结果(出现=[出现记录(b.编号, s, s + 11, "13800138000", "mobile_phone")])
    映射 = 全局映射表()
    输出 = 保存定位脱敏(str(路径), 块, 结果, 映射, 目录)
    return 输出, 映射


def _敏感文字框(路径):
    """敏感文字所在字符框的合并矩形——涂白/遮挡就发生在这个小区域。"""
    import pymupdf
    from 主程序.文档解析器 import 读取文档块
    块 = 读取文档块(str(路径))
    b = [x for x in 块 if "13800138000" in x.原文][0]
    s = b.原文.index("13800138000")
    框 = pymupdf.Rect(b.位置["字符框"][s])
    for r in b.位置["字符框"][s + 1:s + 11]:
        框 |= pymupdf.Rect(r)
    return 框


class TestPDF背景保留(unittest.TestCase):

    def test_新流程脱敏保留背景图片且原文字移除(self):
        from 主程序.格式保持器 import 保存定位脱敏  # noqa: F401 确保入口在
        with 验证用临时目录() as d:
            路径 = Path(d) / "图文.pdf"
            _造图文pdf(路径)
            字框 = _敏感文字框(路径)
            原占比 = _区域红色占比(路径, 字框)
            self.assertGreater(原占比, 0.5, "造样失败：敏感文字下方不是红色背景")
            输出, _ = _新流程脱敏(路径, d)
            import pymupdf
            with pymupdf.open(输出) as doc:
                文本 = doc[0].get_text()
            self.assertNotIn("13800138000", 文本, "原敏感文字未被移除")
            self.assertIn("[手机号1]", 文本)
            新占比 = _区域红色占比(输出, 字框)
            self.assertGreater(新占比, 0.5 * 原占比,
                               f"敏感文字区域的背景被涂白或遮挡：红色占比 {原占比:.2f} -> {新占比:.2f}")

    def test_新流程还原保留背景图片且原文回来(self):
        from 主程序.格式保持器 import 还原并保存原格式
        with 验证用临时目录() as d:
            路径 = Path(d) / "图文.pdf"
            _造图文pdf(路径)
            字框 = _敏感文字框(路径)
            原占比 = _区域红色占比(路径, 字框)
            输出, 映射 = _新流程脱敏(路径, d)
            映射路径 = Path(d) / "映射.json"
            映射.保存到文件(映射路径)
            重载 = 全局映射表()
            重载.从文件加载(映射路径)
            还原 = 还原并保存原格式(输出, 重载, d)
            import pymupdf
            with pymupdf.open(还原) as doc:
                文本 = doc[0].get_text()
            self.assertIn("13800138000", 文本, "还原后原敏感文字未回来")
            新占比 = _区域红色占比(还原, 字框)
            self.assertGreater(新占比, 0.5 * 原占比,
                               f"还原路径背景被涂白或遮挡：红色占比 {原占比:.2f} -> {新占比:.2f}")

    def test_旧映射路径脱敏保留背景图片(self):
        from 主程序.格式保持器 import _脱敏pdf
        with 验证用临时目录() as d:
            路径 = Path(d) / "图文.pdf"
            _造图文pdf(路径)
            字框 = _敏感文字框(路径)
            原占比 = _区域红色占比(路径, 字框)
            映射 = 全局映射表()
            映射.查找或创建("13800138000", "mobile_phone")
            输出 = _脱敏pdf(str(路径), 映射, str(Path(d) / "图文_脱敏.pdf"))
            import pymupdf
            with pymupdf.open(输出) as doc:
                文本 = doc[0].get_text()
            self.assertNotIn("13800138000", 文本)
            新占比 = _区域红色占比(输出, 字框)
            self.assertGreater(新占比, 0.5 * 原占比,
                               f"旧映射路径背景被涂白或遮挡：红色占比 {原占比:.2f} -> {新占比:.2f}")


if __name__ == "__main__":
    unittest.main()
