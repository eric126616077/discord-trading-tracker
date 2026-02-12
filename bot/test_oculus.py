#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OCULUS 格式測試"""
import re

# 測試英文 OCULUS 格式
test_message_en = """==============================
    OCULUS TRADING  SIGNAL
Ticker:   $QQQ
Strike: 64C
Expiry 2/11
Entry: 1.61

=============================="""

# 測試中文 OCULUS 格式
test_message_cn = """==============================
    OCULUS 交易信号
股票代码:   $QQQ
行权价: 64C
到期日: 2/11
入场价: 1.61

=============================="""

print("=" * 50)
print("測試 OCULUS 格式解析")
print("=" * 50)

# 測試英文 Ticker 模式
oculus_pattern = re.compile(
    r'(?i)Ticker[:\s]*\$?([A-Z]{2,})\s*[\n\r]+.*?Strike[:\s]*(\d+)([pcC])',
    re.DOTALL
)

print("\n【英文格式】")
print(test_message_en)
match = oculus_pattern.search(test_message_en)
if match:
    print(f"\n找到匹配!")
    print(f"  股票代碼: {match.group(1)}")
    print(f"  履約價數字: {match.group(2)}")
    print(f"  Call/Put: {match.group(3)}")
else:
    print("\n沒有找到匹配!")

# 測試中文模式
oculus_cn_pattern = re.compile(
    r'(?i)股票代码[:\s]*\$?([A-Z]{2,})\s*[\n\r]+.*?行权价[:\s]*(\d+)([pcC])',
    re.DOTALL
)

print("\n【中文格式】")
print(test_message_cn)
cn_match = oculus_cn_pattern.search(test_message_cn)
if cn_match:
    print(f"\n找到匹配!")
    print(f"  股票代碼: {cn_match.group(1)}")
    print(f"  履約價數字: {cn_match.group(2)}")
    print(f"  Call/Put: {cn_match.group(3)}")
else:
    print("\n沒有找到匹配!")

# 測試 Entry 解析
print("\n【Entry 解析測試】")
entry_pattern = re.compile(r'(?i)Entry[:\s]*\$?([\d.]+)', re.DOTALL)
entry_match = entry_pattern.search(test_message_en)
if entry_match:
    print(f"  Entry: {entry_match.group(1)}")

entry_cn_pattern = re.compile(r'(?i)入场(?:价)?[:\s]*\$?([\d.]+)', re.DOTALL)
entry_cn_match = entry_cn_pattern.search(test_message_cn)
if entry_cn_match:
    print(f"  入场价: {entry_cn_match.group(1)}")

print("\n" + "=" * 50)
