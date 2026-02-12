"""
期權交易追蹤器 - 簡化版
記錄每筆訂單的入場、出場、盈虧
自動過期訂單處理（基於美國期權交易時間）
"""

import re
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
from enum import Enum

# 澳門時區 (UTC+8)
MACAU_TZ = timezone(timedelta(hours=8))

# 美國東部時區 (ET)
US_EASTERN_TZ = timezone(timedelta(hours=-5))  # EST, 或使用 -4 (EDT) 自動處理夏令時


class OrderStatus(Enum):
    PENDING = "pending"    # 待執行
    OPEN = "open"          # 持倉中
    CLOSED = "closed"      # 已平倉
    EXPIRED = "expired"    # 已過期


class TradeOrder:
    """交易訂單類 - 追蹤每筆獨立訂單"""
    
    def __init__(self):
        self.order_id: str = ""           # 訂單唯一ID
        self.ticker: str = ""              # 股票代碼 (QQQ, SPY)
        self.option_type: str = ""          # "p" (put) 或 "c" (call)
        self.strike_price: float = 0.0      # 執行價格
        self.expiration: str = ""          # 到期日 (MM/DD/YY)
        self.entry_price: Optional[float] = None   # 入場價格
        self.entry_time: Optional[str] = None      # 入場時間
        self.exit_price: Optional[float] = None    # 出場價格
        self.exit_time: Optional[str] = None       # 出場時間
        self.pnl_percent: Optional[float] = None   # 盈虧百分比
        self.status: OrderStatus = OrderStatus.PENDING
        self.messages: List[Dict] = []      # 相關的所有訊息記錄
        self.notes: str = ""                # 備註
        
    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "ticker": self.ticker,
            "option_type": self.option_type,
            "strike_price": self.strike_price,
            "expiration": self.expiration,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time,
            "exit_price": self.exit_price,
            "exit_time": self.exit_time,
            "pnl_percent": self.pnl_percent,
            "status": self.status.value,
            "messages_count": len(self.messages),
            "notes": self.notes
        }


class ChannelMessage:
    """頻道訊息記錄 - 記錄每一條訊息"""
    
    def __init__(self):
        self.id: str = ""
        self.channel_id: str = ""
        self.content: str = ""              # 原始訊息內容
        self.timestamp: str = ""
        self.has_order: bool = False         # 是否包含訂單信息
        self.order_id: Optional[str] = None # 關聯的訂單ID
        
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "content": self.content,
            "timestamp": self.timestamp,
            "has_order": self.has_order,
            "order_id": self.order_id
        }


class TradingTracker:
    """期權交易追蹤器 - 簡化版"""
    
    def __init__(self, data_file: str = None):
        # 初始化數據文件路徑
        if data_file is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(base_dir, 'data')
            os.makedirs(data_dir, exist_ok=True)
            self.data_file = os.path.join(data_dir, 'trading_tracker.json')
        else:
            self.data_file = data_file
        
        # 訂單列表
        self.orders: Dict[str, TradeOrder] = {}
        
        # 所有訊息列表
        self.all_messages: List[ChannelMessage] = []
        
        # 活躍持倉 (用於匹配平倉訂單)
        self.open_positions: Dict[str, TradeOrder] = {}
        
        # 載入現有數據
        self.load_data()
        
        # 檢查並過期處理訂單
        self.check_expired_orders()
    
    def get_current_us_time(self) -> datetime:
        """獲取美國當前時間"""
        # 自動檢測是否在夏令時 (EDT = UTC-4, EST = UTC-5)
        now_utc = datetime.now(timezone.utc)
        
        # 美國夏令時: 3月第二個周日 - 11月第一個周日
        # 簡化處理: 使用 US Eastern Time
        us_tz = timezone(timedelta(hours=-4)) if self._is_daylight_savings_time(now_utc) else timezone(timedelta(hours=-5))
        
        return now_utc.astimezone(us_tz)
    
    def _is_daylight_savings_time(self, dt: datetime) -> bool:
        """檢查是否在夏令時期間"""
        # 簡化: 3月到11月視為夏令時
        month = dt.month
        return 3 <= month <= 11
    
    def parse_expiration_date(self, exp_str: str) -> Optional[datetime]:
        """解析到期日"""
        try:
            # 嘗試 MM/DD/YY 格式
            return datetime.strptime(exp_str, "%m/%d/%y")
        except ValueError:
            try:
                # 嘗試 MM/DD/YYYY 格式
                return datetime.strptime(exp_str, "%m/%d/%Y")
            except ValueError:
                return None
    
    def get_us_market_close_time(self, exp_date: datetime) -> datetime:
        """獲取美國市場收盤時間 (16:00 ET)"""
        # 設置為到期日的 16:00:00
        market_close = exp_date.replace(hour=16, minute=0, second=0, microsecond=0)
        
        # 轉換為美國東部時區
        us_tz = timezone(timedelta(hours=-4)) if self._is_daylight_savings_time(market_close) else timezone(timedelta(hours=-5))
        return market_close.replace(tzinfo=us_tz)
    
    def check_expired_orders(self) -> int:
        """
        檢查並處理過期訂單
        過期時間: 美國時間到期日 16:00 (收盤後)
        返回: 過期的訂單數量
        """
        now_us = self.get_current_us_time()
        expired_count = 0
        
        for key, order in list(self.open_positions.items()):
            if order.status != OrderStatus.OPEN:
                continue
            
            # 解析到期日
            exp_date = self.parse_expiration_date(order.expiration)
            if not exp_date:
                continue
            
            # 獲取美國市場收盤時間
            market_close = self.get_us_market_close_time(exp_date)
            
            # 如果當前美國時間超過收盤時間，訂單過期
            if now_us >= market_close:
                # 過期訂單視為虧損 -100%
                order.status = OrderStatus.EXPIRED
                order.exit_time = now_us.astimezone(MACAU_TZ).isoformat()
                order.pnl_percent = -100
                order.notes = f"過期自動平倉 (美國市場收盤)"
                
                # 從持倉中移除
                del self.open_positions[key]
                expired_count += 1
                
                print(f"📅 訂單過期: {order.ticker} ${order.strike_price}{order.option_type} (到期日: {order.expiration})")
        
        # 保存數據
        if expired_count > 0:
            self.save_data()
        
        return expired_count
    
    def add_message(self, content: str, channel_id: str, message_id: str = "", timestamp: str = "", embeds: List[Dict] = None) -> List[str]:
        """
        添加一條訊息 - 返回關聯的訂單ID列表
        如果消息已存在（基於 message_id），則跳過
        支援 Discord Embed 格式（如 JPM）
        """
        # 生成消息 ID
        msg_id = message_id or datetime.now().strftime("%Y%m%d%H%M%S%f")
        
        # 🔧 去重檢查：如果消息已存在，跳過
        for existing_msg in self.all_messages:
            if existing_msg.id == msg_id:
                # 消息已存在，不重複添加
                return []
        
        # 記錄訊息
        msg = ChannelMessage()
        msg.id = msg_id
        msg.channel_id = channel_id
        msg.content = content
        msg.timestamp = timestamp or datetime.now(MACAU_TZ).isoformat()
        
        # 解析訊息中的訂單信息（支援嵌入格式）
        order_ids = self._parse_and_update_orders(content, channel_id, msg, embeds)
        
        # 標記訊息是否包含訂單
        msg.has_order = len(order_ids) > 0
        for oid in order_ids:
            msg.order_id = oid
        
        self.all_messages.append(msg)
        
        # 只有當有新消息時才保存
        self.save_data()
        
        return order_ids
    
    def _parse_and_update_orders(self, content: str, channel_id: str, msg: ChannelMessage, embeds: List[Dict] = None) -> List[str]:
        """解析訊息並更新訂單（支援 Discord Embed 格式）"""
        order_ids = []
        
        # ========== 優先解析 Discord Embed 格式（如 JPM） ==========
        if embeds:
            embed_signals = self._parse_discord_embeds(embeds, channel_id, msg)
            if embed_signals:
                print(f"[DEBUG] Embed 解析成功，找到 {len(embed_signals)} 個訂單")
                return embed_signals
        
        # 清理訊息內容 - 移除 "DayTrade分享 - 期權:" 前綴
        clean_content = re.sub(r'DayTrade分享\s*[-–]\s*期權\s*:?\s*', '', content, flags=re.IGNORECASE)
        clean_content = clean_content.strip()
        
        # ========== 解析 OCULUS Embed 卡片格式 ==========
        # OCULUS Embed 格式的字段通常是：
        # Ticker | $SPX
        # Strike | 6980C
        # Expiry | 0dte
        # Entry | 2.10
        # 或
        # 股票代码 | $SPX
        # 行权价 | 6980C
        # 到期日 | 0dte
        # 入场 | 2.10
        
        oculus_embed_ticker = re.search(r'(?:Ticker|股票代码)\s*[|]\s*\$?([A-Z]{2,})', clean_content)
        oculus_embed_strike = re.search(r'(?:Strike|行权价)\s*[|]\s*(\d+)([pcCP])', clean_content)
        oculus_embed_entry = re.search(r'(?:Entry|入场|入場)\s*[|]\s*\$?([\d.]+)', clean_content)
        oculus_embed_expiry = re.search(r'(?:Expiry|到期日)\s*[|]\s*(\d{1,2}/\d{1,2}(?:/\d{2,4})?|0dte)', clean_content, re.IGNORECASE)
        oculus_embed_lotto = re.search(r'(?:Lotto|彩票)', clean_content, re.IGNORECASE)
        
        if oculus_embed_ticker and oculus_embed_strike:
            ticker = oculus_embed_ticker.group(1).upper()
            
            if ticker not in ['OCULUS', 'DISCORD', 'TELEGRAM', 'SIGNAL', 'TRADING']:
                strike = float(oculus_embed_strike.group(1))
                opt_type = oculus_embed_strike.group(2).lower()
                premium = float(oculus_embed_entry.group(1)) if oculus_embed_entry else 0.0
                
                # 處理到期日
                if oculus_embed_expiry:
                    exp_str = oculus_embed_expiry.group(1).strip().lower()
                    if '0dte' in exp_str:
                        expiry = "0dte (今天到期)"
                        notes = "0dte - 今天到期"
                    else:
                        expiry = oculus_embed_expiry.group(1)
                        notes = "買入開倉 (OCULUS)"
                else:
                    expiry = "N/A"
                    notes = "買入開倉 (OCULUS)"
                
                # 彩票標記
                if oculus_embed_lotto:
                    notes = notes + " | 🎰 彩票 (高風險)"
                
                # 創建訂單
                order = TradeOrder()
                order.order_id = f"{ticker}_{strike}{opt_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                order.ticker = ticker
                order.strike_price = strike
                order.option_type = opt_type
                order.expiration = expiry
                order.entry_price = premium
                order.entry_time = datetime.now(MACAU_TZ).isoformat()
                order.status = OrderStatus.OPEN
                order.notes = notes
                order.messages.append(msg.to_dict())
                
                self.orders[order.order_id] = order
                self.open_positions[f"{ticker}{strike}{opt_type}"] = order
                order_ids.append(order.order_id)
                
                print(f"[OCULUS Embed] 創建訂單成功: {ticker} {strike}{opt_type} @ {premium}")
                
                return order_ids
        
        # ========== 解析 OCULUS 一般格式買入開倉 ==========
        # OCULUS 是頻道名稱，不是股票代碼
        # 格式 (英文):
        # OCULUS TRADING  SIGNAL
        # Ticker:   $SPX
        # Strike: 6965C
        # Expiry 0dte
        # Entry: 2.55
        #
        # 格式 (中文):
        # OCULUS 交易信号
        # 股票代码:   $SPY
        # 行权价: 715C
        # 到期日 3/20
        # 入场: 3.58
        oculus_ticker_pattern = re.compile(
            r'(?i)Ticker\s*[:=]?\s*\$?([A-Z]{2,})'
        )
        oculus_cn_ticker_pattern = re.compile(
            r'(?i)股票代码\s*[:=]?\s*\$?([A-Z]{2,})'
        )
        oculus_strike_pattern = re.compile(
            r'(?i)(?:Strike|行权价)\s*[:=]?\s*(\d+)([pcCP])'
        )
        
        oculus_ticker_match = oculus_ticker_pattern.search(clean_content)
        oculus_cn_ticker_match = oculus_cn_ticker_pattern.search(clean_content)
        
        if oculus_ticker_match or oculus_cn_ticker_match:
            ticker_match = oculus_ticker_match or oculus_cn_ticker_match
            ticker = ticker_match.group(1).upper()
            
            # 排除 OCULUS 等頻道名稱
            if ticker not in ['OCULUS', 'DISCORD', 'TELEGRAM', 'SIGNAL', 'TRADING']:
                oculus_strike_match = oculus_strike_pattern.search(clean_content)
                
                if oculus_strike_match:
                    strike = float(oculus_strike_match.group(1))
                    opt_type = oculus_strike_match.group(2).lower()
                    
                    # 分開解析入場價格
                    entry_pattern = re.compile(r'(?i)(?:Entry|入场|入場)\s*[:=]?\s*\$?([\d.]+)', re.DOTALL)
                    entry_match = entry_pattern.search(clean_content)
                    premium = float(entry_match.group(1)) if entry_match else 0.0
                    
                    # 嘗試解析到期日 (支援 0dte 格式)
                    expiry = "N/A"
                    expiry_pattern = re.compile(r'(?i)(?:Expiry|到期日)\s*[:=]?\s*(\d{1,2}/\d{1,2}(?:/\d{2,4})?|0dte)', re.DOTALL)
                    exp_match = expiry_pattern.search(clean_content)
                    if exp_match:
                        exp_str = exp_match.group(1).strip().lower()
                        if '0dte' in exp_str:
                            expiry = "0dte (今天到期)"
                            notes = "0dte - 今天到期"
                        else:
                            expiry = exp_match.group(1)
                            notes = "買入開倉 (OCULUS)"
                    
                    # 檢測彩票標記 (Lotto/彩票)
                    if 'lotto' in clean_content.lower() or '彩票' in clean_content:
                        notes = (notes + " | 🎰 彩票" if 'notes' in dir() and notes else "🎰 彩票 (高風險)")
                    
                    # 創建新訂單
                    order = TradeOrder()
                    order.order_id = f"{ticker}_{strike}{opt_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    order.ticker = ticker
                    order.strike_price = strike
                    order.option_type = opt_type
                    order.expiration = expiry
                    order.entry_price = premium
                    order.entry_time = datetime.now(MACAU_TZ).isoformat()
                    order.status = OrderStatus.OPEN
                    order.notes = notes if 'notes' in dir() else "買入開倉 (OCULUS)"
                    order.messages.append(msg.to_dict())
                    
                    self.orders[order.order_id] = order
                    self.open_positions[f"{ticker}{strike}{opt_type}"] = order
                    order_ids.append(order.order_id)
                    
                    print(f"[OCULUS] 創建訂單成功: {ticker} {strike}{opt_type} @ {premium}")
                    
                    return order_ids
        
        # ========== 解析 JPMInvestments 格式 ==========
        # 格式: SPY 02/10 693P @.76 (Light entry)
        # 格式: SPY 02/10 693P @.88 (+15%)
        # 格式: SPY 02/10 693P (all out @.81) 🔥
        
        jpm_pattern = re.compile(
            r'^\s*([A-Z]+)\s+(\d{1,2})/(\d{1,2})\s+(\d+)([PpCc])\s*(?:@(\d+\.?\d*))?\s*(?:\(([^)]*)\))?'
        )
        jpm_match = jpm_pattern.search(clean_content)
        
        if jpm_match:
            ticker = jpm_match.group(1).upper()
            exp_month = int(jpm_match.group(2))
            exp_day = int(jpm_match.group(3))
            strike = float(jpm_match.group(4))
            opt_type = jpm_match.group(5).lower()
            
            # 獲取當前年份
            current_year = datetime.now().year
            expiration = f"{exp_month}/{exp_day}/{str(current_year)[-2:]}"
            
            # 判斷動作 (Open/Update/Close)
            lower_content = clean_content.lower()
            is_close = 'close' in lower_content or 'all out' in lower_content
            
            # 提取價格
            entry_price = None
            exit_price = None
            pnl_percent = None
            notes = ""
            
            # 從 @價格 提取
            if jpm_match.group(6):
                price = float(jpm_match.group(6))
                if is_close:
                    exit_price = price
                else:
                    entry_price = price
            
            # 從括號中提取
            if jpm_match.group(7):
                note_text = jpm_match.group(7)
                notes = note_text
                
                # 提取獲利百分比 (+15%, +25%)
                pnl_match = re.search(r'\(([+-]?\d+)\s*%?\)', note_text)
                if pnl_match:
                    pnl_percent = float(pnl_match.group(1))
                
                # 提取 close 價格 (all out @.81)
                close_match = re.search(r'all out\s*@?\$?([\d.]+)', note_text, re.IGNORECASE)
                if close_match:
                    exit_price = float(close_match.group(1))
            
            # 查找現有持倉
            position_key = f"{ticker}{strike}{opt_type}"
            existing_order = self.open_positions.get(position_key)
            
            if is_close and existing_order:
                # 平倉
                existing_order.status = OrderStatus.CLOSED
                existing_order.exit_price = exit_price
                existing_order.exit_time = datetime.now(MACAU_TZ).isoformat()
                
                if entry_price:
                    existing_order.entry_price = entry_price
                
                if pnl_percent is not None:
                    existing_order.pnl_percent = pnl_percent
                elif exit_price and existing_order.entry_price:
                    existing_order.pnl_percent = round((exit_price - existing_order.entry_price) / existing_order.entry_price * 100, 1)
                
                existing_order.notes = f"平倉 {notes}".strip()
                existing_order.messages.append(msg.to_dict())
                
                # 移出持倉
                del self.open_positions[position_key]
                order_ids.append(existing_order.order_id)
                
                print(f"[JPM] 平倉訂單: {ticker} {strike}{opt_type} @ {exit_price} ({pnl_percent:+.1f}%)")
                
                return order_ids
            elif existing_order:
                # 更新持倉 (Update)
                if entry_price and entry_price != existing_order.entry_price:
                    existing_order.entry_price = entry_price
                if pnl_percent is not None:
                    existing_order.pnl_percent = pnl_percent
                existing_order.notes = f"更新 {notes}".strip() if notes else "JPM 更新"
                existing_order.messages.append(msg.to_dict())
                
                print(f"[JPM] 更新持倉: {ticker} {strike}{opt_type} @ {entry_price} ({pnl_percent:+.1f}%)")
                
                return order_ids
            elif entry_price and not is_close:
                # 新建持倉 (Open)
                order = TradeOrder()
                order.order_id = f"{ticker}_{strike}{opt_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                order.ticker = ticker
                order.strike_price = strike
                order.option_type = opt_type
                order.expiration = expiration
                order.entry_price = entry_price
                order.entry_time = datetime.now(MACAU_TZ).isoformat()
                order.status = OrderStatus.OPEN
                order.notes = f"買入開倉 (JPM) {notes}".strip()
                order.messages.append(msg.to_dict())
                
                self.orders[order.order_id] = order
                self.open_positions[position_key] = order
                order_ids.append(order.order_id)
                
                print(f"[JPM] 創建訂單成功: {ticker} {strike}{opt_type} @ {entry_price}")
                
                return order_ids
        
        # ========== 1. 解析 BTO 買入開倉 ==========
        # 格式: BTO $QQQ 613p 02/10 @0.69
        bto_pattern = re.compile(
            r'(?i)\s*(?:BTO)?\s*\$?([A-Z]+)\s*(\d+)([pc])\s*(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s*@?\$?([\d.]+)'
        )
        bto_match = bto_pattern.search(clean_content)
        if bto_match:
            ticker = bto_match.group(1).upper()
            strike = float(bto_match.group(2))
            opt_type = bto_match.group(3).lower()
            expiration = bto_match.group(4)
            premium = float(bto_match.group(5))
            
            # 創建新訂單
            order = TradeOrder()
            order.order_id = f"{ticker}_{strike}{opt_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            order.ticker = ticker
            order.strike_price = strike
            order.option_type = opt_type
            order.expiration = expiration
            order.entry_price = premium
            order.entry_time = datetime.now(MACAU_TZ).isoformat()
            order.status = OrderStatus.OPEN
            order.notes = "買入開倉 (BTO)"
            order.messages.append(msg.to_dict())
            
            self.orders[order.order_id] = order
            self.open_positions[f"{ticker}{strike}{opt_type}"] = order
            order_ids.append(order.order_id)
            
            return order_ids
        
        # ========== 2. 解析 STC 賣出平倉 ==========
        # 格式: STC $QQQ 613p 02/10 @0.80
        stc_pattern = re.compile(
            r'(?i)\s*(?:STC|平倉|賣出)\s*\$?([A-Z]+)\s*(\d+)([pc])\s*(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s*@?\$?([\d.]+)'
        )
        stc_match = stc_pattern.search(clean_content)
        if stc_match:
            ticker = stc_match.group(1).upper()
            strike = float(stc_match.group(2))
            opt_type = stc_match.group(3).lower()
            expiration = stc_match.group(4)
            exit_price = float(stc_match.group(5))
            
            # 查找對應的持倉
            key = f"{ticker}{strike}{opt_type}"
            if key in self.open_positions:
                order = self.open_positions[key]
                order.exit_price = exit_price
                order.exit_time = datetime.now(MACAU_TZ).isoformat()
                order.status = OrderStatus.CLOSED
                order.pnl_percent = round(((exit_price - order.entry_price) / order.entry_price) * 100, 2)
                order.notes = f"賣出平倉 (STC) @ ${exit_price}"
                order.messages.append(msg.to_dict())
                
                # 從持倉中移除
                del self.open_positions[key]
                order_ids.append(order.order_id)
            
            return order_ids
        
        # ========== 3. 解析止盈通知 ==========
        # 格式: QQQ 最高+178%💰
        tp_pattern = re.compile(
            r'(?i)\s*([A-Z]+)\s*(?:最高|止盈|平倉|獲利|盈)[^\d]*\+?([\d.]+)%?\s*[@$]?'
        )
        tp_match = tp_pattern.search(clean_content)
        if tp_match:
            ticker = tp_match.group(1).upper()
            pnl = float(tp_match.group(2))
            
            # 查找對應的持倉
            for key, order in list(self.open_positions.items()):
                if order.ticker == ticker:
                    order.pnl_percent = pnl
                    order.status = OrderStatus.CLOSED
                    order.exit_time = datetime.now(MACAU_TZ).isoformat()
                    order.notes = f"止盈通知 PnL: +{pnl}%"
                    order.messages.append(msg.to_dict())
                    
                    del self.open_positions[key]
                    order_ids.append(order.order_id)
                    break
            
            return order_ids
        
        # ========== 4. 解析止損通知 ==========
        # 格式: QQQ 我止损了 或 QQQ 止損
        sl_pattern = re.compile(
            r'(?i)\s*([A-Z]+)\s*(?:我)?(?:止损|止損|停損|虧損|亏损)(?:了)?'
        )
        sl_match = sl_pattern.search(clean_content)
        if sl_match:
            ticker = sl_match.group(1).upper()
            
            # 查找對應的持倉
            for key, order in list(self.open_positions.items()):
                if order.ticker == ticker:
                    order.pnl_percent = -50  # 預設虧損50%
                    order.status = OrderStatus.CLOSED
                    order.exit_time = datetime.now(MACAU_TZ).isoformat()
                    order.notes = "止損通知"
                    order.messages.append(msg.to_dict())
                    
                    del self.open_positions[key]
                    order_ids.append(order.order_id)
                    break
            
            return order_ids
        
        # ========== 解析 JPMInvestments 格式 ==========
        # 格式: SPY 02/10 693P @.76 (Light entry)
        # 格式: SPY 02/10 693P @.88 (+15%)
        # 格式: SPY 02/10 693P (all out @.81) 🔥
        
        jpm_pattern = re.compile(
            r'^([A-Z]+)\s+(\d{1,2})\/(\d{1,2})\s+(\d+)([PpCc])\s*(?:@(\d+\.?\d*))?\s*(?:\(([^)]*)\))?',
            re.IGNORECASE
        )
        jpm_match = jpm_pattern.match(clean_content)
        
        if jpm_match:
            ticker = jpm_match.group(1).upper()
            exp_month = jpm_match.group(2)
            exp_day = jpm_match.group(3)
            strike = float(jpm_match.group(4))
            opt_type = jpm_match.group(5).upper()
            price = float(jpm_match.group(6)) if jpm_match.group(6) else 0.0
            notes = jpm_match.group(7) or ''
            
            # 判斷是買入還是平倉
            lower_content = clean_content.lower()
            is_close = 'close' in lower_content or 'all out' in lower_content
            
            # 解析盈虧百分比
            pnl_match = re.search(r'([+-]?\d+)\s*%', notes)
            pnl_percent = float(pnl_match.group(1)) if pnl_match else None
            
            if is_close:
                # 賣出平倉
                key = f"{ticker}{strike}{opt_type}"
                if key in self.open_positions:
                    order = self.open_positions[key]
                    order.exit_price = price
                    order.exit_time = datetime.now(MACAU_TZ).isoformat()
                    order.status = OrderStatus.CLOSED
                    order.pnl_percent = pnl_percent
                    order.notes = f"賣出平倉 (JPM) @ ${price}" if price else "賣出平倉 (JPM)"
                    order.messages.append(msg.to_dict())
                    
                    del self.open_positions[key]
                    order_ids.append(order.order_id)
                    
                    print(f"[JPM] 平倉訂單: {ticker} {strike}{opt_type} @ ${price}")
                    
                return order_ids
            else:
                # 買入開倉
                order = TradeOrder()
                order.order_id = f"{ticker}_{strike}{opt_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                order.ticker = ticker
                order.strike_price = strike
                order.option_type = opt_type
                order.expiration = f"{exp_month}/{exp_day}"
                order.entry_price = price
                order.entry_time = datetime.now(MACAU_TZ).isoformat()
                order.status = OrderStatus.OPEN
                order.notes = f"買入開倉 (JPM) | {notes}" if notes else "買入開倉 (JPM)"
                order.messages.append(msg.to_dict())
                
                self.orders[order.order_id] = order
                self.open_positions[f"{ticker}{strike}{opt_type}"] = order
                order_ids.append(order.order_id)
                
                print(f"[JPM] 創建訂單成功: {ticker} {strike}{opt_type} @ ${price}")
                
                return order_ids
        
        # 如果沒有匹配到訂單相關信息，仍記錄訊息但標記為無訂單
        msg.has_order = False
        
        return order_ids
    
    def _parse_discord_embeds(self, embeds: List[Dict], channel_id: str, msg: ChannelMessage) -> List[str]:
        """
        解析 Discord Embed 格式的交易訊息（如 JPM）
        Embed 格式:
        - title: "Open", "Update", "Close"
        - description: "SPY 02/10 693P @.76 (Light entry)"
        - footer: "Jpm Options | For Informational Purposes Only"
        """
        order_ids = []
        
        try:
            for embed in embeds:
                if not isinstance(embed, dict):
                    continue
                
                title = embed.get('title', '') or ''
                description = embed.get('description', '') or ''
                footer = embed.get('footer', {}).get('text', '') or ''
                
                print(f"\n[DEBUG] 解析 Discord Embed:")
                print(f"[DEBUG]   Title: {title}")
                print(f"[DEBUG]   Description: {description[:100]}")
                print(f"[DEBUG]   Footer: {footer[:50]}")
                
                # 判斷是否為 JPM 交易訊息（通過 footer 判斷）
                if 'Jpm' not in footer and 'JPM' not in footer:
                    continue
                
                # 解析標題確定動作類型
                action_type = 'open'  # 預設為開倉
                title_lower = title.lower().strip()
                
                if 'close' in title_lower or 'closed' in title_lower:
                    action_type = 'close'
                elif 'update' in title_lower:
                    action_type = 'update'
                
                # 從 description 解析交易資訊
                # 格式: SPY 02/10 693P @.76 (Light entry)
                # 或: SPY 02/10 693P (all out @.81) 🔥
                desc_pattern = re.compile(
                    r'([A-Z]{2,})\s+(\d{1,2})\/(\d{1,2})\s+(\d+\.?\d*)([PpCc])\s*(?:@\.?(\d+\.?\d*))?\s*(?:\(([^)]*)\))?'
                )
                desc_match = desc_pattern.search(description)
                
                if desc_match:
                    ticker = desc_match.group(1).upper()
                    exp_month = int(desc_match.group(2))
                    exp_day = int(desc_match.group(3))
                    strike = float(desc_match.group(4))
                    opt_type = desc_match.group(5).lower()
                    price_str = desc_match.group(6)
                    notes = desc_match.group(7) or ''
                    
                    # 解析價格
                    entry_price = None
                    exit_price = None
                    pnl_percent = None
                    
                    if price_str:
                        price = float(price_str)
                        if action_type == 'close':
                            exit_price = price
                        else:
                            entry_price = price
                    
                    # 從括號中解析 PnL 和 close 價格
                    if notes:
                        # 解析 PnL (+15%, +25%, +60%)
                        pnl_match = re.search(r'\(([+\-]?\d+)%\)', notes)
                        if pnl_match:
                            pnl_percent = float(pnl_match.group(1))
                        
                        # 解析 close 價格 (all out @.81)
                        if action_type == 'close':
                            close_match = re.search(r'all out\s*@?\$?([\d.]+)', notes, re.IGNORECASE)
                            if close_match:
                                exit_price = float(close_match.group(1))
                    
                    # 構建到期日
                    current_year = datetime.now().year
                    expiration = f"{exp_month}/{exp_day}/{str(current_year)[-2:]}"
                    
                    # 查找現有持倉
                    position_key = f"{ticker}{strike}{opt_type}"
                    existing_order = self.open_positions.get(position_key)
                    
                    # 創建原始消息記錄
                    msg_content = f"[EMBED] {title}\n{description}"
                    
                    if action_type == 'close' and existing_order:
                        # 平倉
                        existing_order.status = OrderStatus.CLOSED
                        if exit_price:
                            existing_order.exit_price = exit_price
                        existing_order.exit_time = datetime.now(MACAU_TZ).isoformat()
                        if pnl_percent is not None:
                            existing_order.pnl_percent = pnl_percent
                        elif exit_price and existing_order.entry_price:
                            existing_order.pnl_percent = round((exit_price - existing_order.entry_price) / existing_order.entry_price * 100, 1)
                        existing_order.notes = f"JPM 平倉 {notes}".strip() if notes else "JPM 平倉"
                        existing_order.messages.append(msg.to_dict())
                        
                        del self.open_positions[position_key]
                        order_ids.append(existing_order.order_id)
                        
                        pnl_str = f"{pnl_percent:+.1f}%" if pnl_percent is not None else "N/A"
                        print(f"[JPM Embed] 平倉: {ticker} {strike}{opt_type} @ {exit_price} (PnL: {pnl_str})")
                        
                    elif action_type == 'update' and existing_order:
                        # 更新持倉 (Update 只更新 PnL，不改變入場價格)
                        if pnl_percent is not None:
                            existing_order.pnl_percent = pnl_percent
                        # 注意：Update 中的 @價格 是當前價格，不是入場價格，不要覆蓋 entry_price
                        pnl_str = f"{pnl_percent:+.1f}%" if pnl_percent is not None else "N/A"
                        existing_order.notes = f"JPM 更新 {notes}".strip() if notes else f"PnL: {pnl_str}" if pnl_percent else "JPM 更新"
                        existing_order.messages.append(msg.to_dict())
                        
                        print(f"[JPM Embed] 更新: {ticker} {strike}{opt_type} (PnL: {pnl_str})")
                        
                    elif entry_price:
                        # 新建持倉 (Open)
                        order = TradeOrder()
                        order.order_id = f"{ticker}_{strike}{opt_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        order.ticker = ticker
                        order.strike_price = strike
                        order.option_type = opt_type
                        order.expiration = expiration
                        order.entry_price = entry_price
                        order.entry_time = datetime.now(MACAU_TZ).isoformat()
                        order.status = OrderStatus.OPEN
                        order.notes = f"JPM 買入開倉 {notes}".strip() if notes else "JPM 買入開倉"
                        order.messages.append(msg.to_dict())
                        
                        self.orders[order.order_id] = order
                        self.open_positions[position_key] = order
                        order_ids.append(order.order_id)
                        
                        print(f"[JPM Embed] 創建訂單: {ticker} {strike}{opt_type} @ {entry_price}")
                    
                    # 標記為有訂單
                    msg.has_order = len(order_ids) > 0
                    
        except Exception as e:
            print(f"[ERROR] 解析 Embed 失敗: {e}")
            import traceback
            traceback.print_exc()
        
        return order_ids
    
    def get_all_orders(self) -> List[dict]:
        """獲取所有訂單"""
        # 先檢查過期
        self.check_expired_orders()
        
        orders = list(self.orders.values())
        orders.sort(key=lambda x: x.entry_time or "", reverse=True)
        return [o.to_dict() for o in orders]
    
    def get_open_orders(self) -> List[dict]:
        """獲取持倉中的訂單"""
        # 先檢查過期
        self.check_expired_orders()
        
        return [o.to_dict() for o in self.open_positions.values()]
    
    def get_closed_orders(self) -> List[dict]:
        """獲取已平倉訂單 (包括過期)"""
        # 先檢查過期
        self.check_expired_orders()
        
        closed = [o for o in self.orders.values() if o.status in [OrderStatus.CLOSED, OrderStatus.EXPIRED]]
        closed.sort(key=lambda x: x.exit_time or "", reverse=True)
        return [o.to_dict() for o in closed]
    
    def get_all_messages(self) -> List[dict]:
        """獲取所有訊息"""
        return [m.to_dict() for m in self.all_messages]
    
    def get_order_by_id(self, order_id: str) -> Optional[dict]:
        """根據ID獲取訂單"""
        if order_id in self.orders:
            return self.orders[order_id].to_dict()
        return None
    
    def get_statistics(self) -> dict:
        """簡化統計 - 只顯示訂單數量"""
        # 先檢查過期
        self.check_expired_orders()
        
        closed = [o for o in self.orders.values() if o.status == OrderStatus.CLOSED]
        expired = [o for o in self.orders.values() if o.status == OrderStatus.EXPIRED]
        open_orders = list(self.open_positions.values())
        
        wins = len([o for o in closed if o.pnl_percent and o.pnl_percent > 0])
        losses = len([o for o in closed if o.pnl_percent and o.pnl_percent <= 0])
        
        return {
            "total_orders": len(self.orders),
            "open_orders": len(open_orders),
            "closed_orders": len(closed) + len(expired),
            "expired_orders": len(expired),
            "wins": wins,
            "losses": losses,
            "total_messages": len(self.all_messages)
        }
    
    def save_data(self):
        """保存數據"""
        try:
            data = {
                "last_updated": datetime.now(MACAU_TZ).isoformat(),
                "orders": {k: v.to_dict() for k, v in self.orders.items()},
                "messages": [m.to_dict() for m in self.all_messages]
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存數據失敗: {e}")
    
    def load_data(self):
        """載入數據"""
        if not os.path.exists(self.data_file):
            return
        
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 重建訂單
            for oid, odata in data.get('orders', {}).items():
                order = TradeOrder()
                order.order_id = odata.get('order_id', '')
                order.ticker = odata.get('ticker', '')
                order.option_type = odata.get('option_type', '')
                order.strike_price = odata.get('strike_price', 0.0)
                order.expiration = odata.get('expiration', '')
                order.entry_price = odata.get('entry_price')
                order.entry_time = odata.get('entry_time')
                order.exit_price = odata.get('exit_price')
                order.exit_time = odata.get('exit_time')
                order.pnl_percent = odata.get('pnl_percent')
                order.status = OrderStatus(odata.get('status', 'pending'))
                order.notes = odata.get('notes', '')
                
                self.orders[oid] = order
                
                # 重建持倉 (只包括 OPEN 狀態)
                if order.status == OrderStatus.OPEN:
                    key = f"{order.ticker}{order.strike_price}{order.option_type}"
                    self.open_positions[key] = order
            
            # 🔧 重建訊息並去重
            seen_ids = set()
            for mdata in data.get('messages', []):
                msg_id = mdata.get('id', '')
                
                # 去重：只保留第一個相同 ID 的消息
                if msg_id and msg_id not in seen_ids:
                    seen_ids.add(msg_id)
                    msg = ChannelMessage()
                    msg.id = msg_id
                    msg.channel_id = mdata.get('channel_id', '')
                    msg.content = mdata.get('content', '')
                    msg.timestamp = mdata.get('timestamp', '')
                    msg.has_order = mdata.get('has_order', False)
                    msg.order_id = mdata.get('order_id')
                    
                    self.all_messages.append(msg)
                    
        except Exception as e:
            print(f"載入數據失敗: {e}")
    
    def clear_all(self):
        """清除所有數據"""
        self.orders = {}
        self.all_messages = []
        self.open_positions = {}
        if os.path.exists(self.data_file):
            os.remove(self.data_file)
    
    def deduplicate(self) -> dict:
        """清理重複數據"""
        seen_ids = set()
        unique_messages = []
        removed_count = 0
        
        for msg in self.all_messages:
            if msg.id not in seen_ids:
                seen_ids.add(msg.id)
                unique_messages.append(msg)
            else:
                removed_count += 1
        
        self.all_messages = unique_messages
        
        # 重新保存
        self.save_data()
        
        return {
            'removed_messages': removed_count,
            'remaining_messages': len(self.all_messages)
        }
