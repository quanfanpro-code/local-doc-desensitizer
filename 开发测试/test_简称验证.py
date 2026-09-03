"""验证简称同义词映射：子串实体映射到相同代号"""
from __future__ import annotations
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))

from 主程序.ner引擎 import 全局映射表, NER引擎

映射 = 全局映射表()

# 直接模拟NER识别后的注册逻辑（不调LM Studio）
模拟实体 = [
    ("四川和邦生物科技股份有限公司", "Ni"),
    ("和邦生物", "Ni"),              # 简称，是上述的子串
    ("和邦集团", "Ni"),              # 独立实体
]

# 手动执行注册逻辑（模拟 text_脱敏 中的注册部分）
模拟实体.sort(key=lambda x: len(x[0]), reverse=True)
for 原文, 实体类型 in 模拟实体:
    if 原文 in 映射.正向映射:
        continue
    父实体 = NER引擎._查找父实体(原文, 映射.正向映射)
    if 父实体:
        映射._正向[原文] = 映射._正向[父实体]
        映射._版本 += 1
    else:
        if 实体类型 == "Ni":
            from 主程序.ner引擎 import 判断机构子类型
            子类型 = 判断机构子类型(原文)
            映射.查找或创建(原文, 子类型)
        else:
            映射.查找或创建(原文, 实体类型)

print("=== 映射表 ===")
for 原文, 代号 in sorted(映射.正向映射.items(), key=lambda x: len(x[0]), reverse=True):
    print(f"  {代号} ← {原文}")

文本 = "四川和邦生物科技股份有限公司（以下简称'和邦生物'）由和邦集团控股。"
替换后 = 映射.批量替换文本(文本)
print(f"原文:   {文本}")
print(f"替换后: {替换后}")

# 验证
assert '和邦生物' not in 替换后, f'简称"和邦生物"未被替换！输出="{替换后}"'
assert '和邦集团' not in 替换后, f'"和邦集团"未被替换！输出="{替换后}"'
assert '四川和邦生物科技股份有限公司' not in 替换后, f'全称未被替换！输出="{替换后}"'
# 验证两个简称用了相同代号
代号集合 = set()
for 原文 in ["四川和邦生物科技股份有限公司", "和邦生物"]:
    代号集合.add(映射.正向映射[原文])
assert len(代号集合) == 1, f'全称和简称应使用相同代号，实际={代号集合}'
print()
print("[OK] 全部验证通过：简称和全称均被正确替换，且使用相同代号")
