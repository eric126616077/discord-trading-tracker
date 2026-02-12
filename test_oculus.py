#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OCULUS 格式測試"""

import re
import sys
import os

# 添加專案路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.trading_parser import TradingSignalParser

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

parser = TradingSignalParser()

print("\n【英文格式】")
print(test_message_en)
signals_en = parser.parse_message(test_message_en)
print(f"\n找到 {len(signals_en)} 個信號:")
for s in signals_en:
    print(f"  股票: {s.ticker}, 履約價: {s.strike_price}, 類型: {s.option_type}, 入場: {s.entry_price}, 動作: {s.action.value}")

print("\n【中文格式】")
print(test_message_cn)
signals_cn = parser.parse_message(test_message_cn)
print(f"\n找到 {len(signals_cn)} 個信號:")
for s in signals_cn:
    print(f"  股票: {s.ticker}, 履約價: {s.strike_price}, 類型: {s.option_type}, 入場: {s.entry_price}, 動作: {s.action.value}")

print("\n" + "=" * 50)
