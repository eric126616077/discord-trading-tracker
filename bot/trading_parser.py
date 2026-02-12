""" 
期權交易信號解析器
解析 Discord 交易信號消息
"""

import re
from datetime import datetime
from typing import Optional, Dict, List, Any
from enum import Enum

class OrderAction(Enum):
    BUY_TO_OPEN = "BTO"      # 買入開倉
    SELL_TO_CLOSE = "STC"     # 賣出平倉
    SELL_TO_OPEN = "STO"      # 賣出開倉
    BUY_TO_CLOSE = "BTC"      # 買入平倉
    TAKE_PROFIT = "TP"        # 止盈
    STOP_LOSS = "SL"          # 止损
    UPDATE = "UPDATE"         # 更新訂單
    UNKNOWN = "UNKNOWN"

class OrderStatus(Enum):
    OPEN = "open"            # 持倉中
    CLOSED = "closed"        # 已平倉
    WIN = "win"              # 盈利
    LOSS = "loss"            # 虧損

class TradingSignal:
    """交易信號類"""
    
    def __init__(self):
        self.id: str = ""
        self.ticker: str = ""              # 股票代碼 (QQQ, SPY, etc.)
        self.action: OrderAction = OrderAction.UNKNOWN
        self.option_type: str = ""          # "p" (put) 或 "c" (call)
        self.strike_price: float = 0.0      # 執行價格
        self.expiration: Optional[datetime] = None  # 到期日
        self.premium: float = 0.0           # 權利金
        self.quantity: int = 1              # 數量
        self.entry_price: Optional[float] = None  # 入場價格
        self.exit_price: Optional[float] = None    # 出場價格
        self.pnl_percent: Optional[float] = None   # 盈虧百分比
        self.status: OrderStatus = OrderStatus.OPEN
        self.raw_message: str = ""           # 原始消息
        self.channel_id: str = ""
        self.timestamp: datetime = datetime.now()
        self.notes: str = ""                # 備註
        
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ticker": self.ticker,
            "action": self.action.value if self.action else "UNKNOWN",
            "option_type": self.option_type,
            "strike_price": self.strike_price,
            "expiration": self.expiration.strftime("%m/%d/%y") if self.expiration else None,
            "premium": self.premium,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl_percent": self.pnl_percent,
            "status": self.status.value,
            "raw_message": self.raw_message[:100] if self.raw_message else "",
            "channel_id": self.channel_id,
            "timestamp": self.timestamp.isoformat(),
            "notes": self.notes
        }

class TradingSignalParser:
    """交易信號解析器"""
    
    # 匹配格式: BTO $QQQ 613p 02/10 @0.69
    # 或者: QQQ 最高+178%💰
    # 或者: QQQ 我止损了
    
    PATTERNS = {
        # BTO $QQQ 613p 02/10 @0.69 - 必須以 BTO 或 buy to open 開頭
        "bto_pattern": re.compile(
            r'(?i)^\s*(?:BTO|buy to open)\s+\$?([A-Z]+)\s+(\d+)([pc])\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s*@?\$?([\d.]+)'
        ),
        
        # OCULUS 格式: 
        # Ticker:   $QQQ
        # Strike: 64C
        # 注意：OCULUS 是頻道名稱，股票代碼是 $QQQ
        "oculus_pattern": re.compile(
            r'(?i)Ticker\s*[:=]?\s*\$([A-Z]{2,})'
        ),
        
        # OCULUS 中文格式: 
        # 股票代码: $QQQ
        # 行权价: 64C
        "oculus_cn_pattern": re.compile(
            r'(?i)股票代码\s*[:=]?\s*\$([A-Z]{2,})'
        ),
        
        # OCULUS Strike 格式: Strike: 64C 或 行权价: 64C
        "oculus_strike_pattern": re.compile(
            r'(?i)(?:Strike|行权价)\s*[:=]?\s*(\d+)([pcCP])'
        ),
        
        # OCULUS 到期日格式: Expiry 0dte 或 到期日: 3/20
        "oculus_expiry_pattern": re.compile(
            r'(?i)Expiry\s*[:=]?\s*(\d+[dte/]+(?:\d{1,2}/\d{1,2}(?:/\d{2,4})?)?)'
        ),
        
        # OCULUS 中文到期日: 到期日: 3/20
        "oculus_expiry_cn_pattern": re.compile(
            r'(?i)到期日\s*[:=]?\s*(\d+[dte/]+(?:\d{1,2}/\d{1,2}(?:/\d{2,4})?)?)'
        ),
        
        # OCULUS 入場價格: Entry: 1.61 或 入场: 1.61
        "oculus_entry_pattern": re.compile(
            r'(?i)(?:Entry|入场|入場)\s*[:=]?\s*\$?([\d.]+)'
        ),
        
        # OCULUS 更新價格: now 6.10 from 4.00 或 3.70 from 2.55
        "oculus_update_pattern": re.compile(
            r'(?i)(?:now\s+)?([\d.]+)\s*(?:from|從)\s*([\d.]+)'
        ),
        
        # 止盈通知: QQQ 最高+178%💰 - 需要在持倉列表中
        "take_profit_pattern": re.compile(
            r'(?i)^\s*([A-Z]+)\s*(?:最高|止盈|平倉|獲利)[^\d]*\+?([\d.]+)%?'
        ),
        
        # 止損通知: QQQ 我止损了 - 需要在持倉列表中
        "stop_loss_pattern": re.compile(
            r'(?i)^\s*([A-Z]+)\s*(?:我)?(?:止损|止損|停損|虧損|亏损)[^\d]*'
        ),
        
        # STC/平倉: STC $QQQ 613p 02/10 @0.80 - 必須以 STC、平倉 或 賣出 開頭
        "stc_pattern": re.compile(
            r'(?i)^\s*(?:STC|平倉|賣出)\s+\$?([A-Z]+)\s+(\d+)([pc])\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s*@?\$?([\d.]+)'
        ),
        
        # 更新持倉比例
        "update_pattern": re.compile(
            r'(?i)^\s*([A-Z]+)\s*(?:現在|當前)[^\d]*(\d+)%?'
        ),
        
        # ========== JPM Embed 格式解析 ==========
        # 格式: SPY 02/10 693P @.76 (Light entry) 或 SPY 02/10 693P (all out @.81)
        # Title: Open, Update, Close
        "jpm_embed_pattern": re.compile(
            r'(?i)([A-Z]{2,})\s+(\d{1,2})\/(\d{1,2})\s+(\d+\.?\d*)([PpCc])\s*(?:@\s*\$?([\d.]+))?\s*(?:\(([^)]*)\))?'
        ),
        
        # JPM PnL 百分比
        "jpm_pnl_pattern": re.compile(
            r'\(([+\-]?\d+)%\)'
        )
    }
    
    def __init__(self):
        self.signals: List[TradingSignal] = []
        self.positions: Dict[str, TradingSignal] = {}  # ticker -> open position
    
    def parse_message(self, message: str, channel_id: str = "", embeds: List[Dict[str, Any]] = None) -> List[TradingSignal]:
        """解析單條消息（支援嵌入格式）"""
        signals = []
        
        # 清理消息
        clean_message = message.strip()
        
        print(f"\n[DEBUG] 開始解析消息:")
        print(f"[DEBUG] 原始消息: {repr(clean_message[:200])}")
        
        # 優先解析 Embed（如果存在）
        if embeds:
            embed_signals = self._parse_embeds(embeds, channel_id)
            if embed_signals:
                print(f"[DEBUG] Embed 解析成功，找到 {len(embed_signals)} 個信號")
                return embed_signals
        
        # 繼續解析純文字消息
        # ... (existing code continues)
        
        # 優先嘗試 OCULUS 格式 (買入開倉)
        # 新的解析方法：分別提取 Ticker、Strike、Entry
        oculus_ticker_match = self.PATTERNS["oculus_pattern"].search(clean_message)
        oculus_cn_ticker_match = self.PATTERNS["oculus_cn_pattern"].search(clean_message)
        
        if oculus_ticker_match:
            print(f"[DEBUG] OCULUS 英文 Ticker 匹配: {oculus_ticker_match.groups()}")
        if oculus_cn_ticker_match:
            print(f"[DEBUG] OCULUS 中文 Ticker 匹配: {oculus_cn_ticker_match.groups()}")
        
        if oculus_ticker_match or oculus_cn_ticker_match:
            ticker_match = oculus_ticker_match or oculus_cn_ticker_match
            ticker = ticker_match.group(1).upper()
            
            # 排除 OCULUS 等頻道名稱
            if ticker not in {'OCULUS', 'DISCORD', 'TELEGRAM', 'SIGNAL', 'TRADING', 'ALERT', 'NOTIFY'}:
                # 提取 Strike
                strike_match = self.PATTERNS["oculus_strike_pattern"].search(clean_message)
                print(f"[DEBUG] OCULUS Strike 匹配: {strike_match.groups() if strike_match else 'None'}")
                
                if strike_match:
                    print(f"[DEBUG] OCULUS 格式解析成功: ticker={ticker}")
                    signal = self._parse_oculus_bto_v2(ticker, strike_match, clean_message, channel_id)
                    if signal:
                        signals.append(signal)
                        print(f"[DEBUG] OCULUS 信號創建成功: {signal.ticker} {signal.strike_price}{signal.option_type}")
            else:
                print(f"[DEBUG] OCULUS Ticker 是頻道名稱，跳過: {ticker}")
        
        # OCULUS 更新價格 (now 6.10 from 4.00)
        if not signals:
            oculus_update_match = self.PATTERNS["oculus_update_pattern"].search(clean_message)
            if oculus_update_match:
                print(f"[DEBUG] OCULUS 更新價格匹配: {oculus_update_match.groups()}")
                # 檢查是否在同一行中有價格更新
                lines = clean_message.split('\n')
                for line in lines:
                    if 'from' in line.lower() or '從' in line:
                        update_match = self.PATTERNS["oculus_update_pattern"].search(line)
                        if update_match:
                            signal = self._parse_oculus_update(update_match, message, channel_id)
                            if signal:
                                signals.append(signal)
                                break
        
        # 嘗試 BTO (買入開倉)
        bto_match = self.PATTERNS["bto_pattern"].search(clean_message)
        if bto_match:
            print(f"[DEBUG] BTO 匹配: {bto_match.groups()}")
            signal = self._parse_bto(bto_match, message, channel_id)
            if signal:
                signals.append(signal)
        
        # 嘗試止盈 (需匹配持倉)
        tp_match = self.PATTERNS["take_profit_pattern"].search(clean_message)
        if tp_match:
            print(f"[DEBUG] 止盈匹配: {tp_match.groups()}")
            signal = self._parse_take_profit(tp_match, message, channel_id)
            if signal:
                signals.append(signal)
        
        # 嘗試止損
        sl_match = self.PATTERNS["stop_loss_pattern"].search(clean_message)
        if sl_match:
            print(f"[DEBUG] 止損匹配: {sl_match.groups()}")
            signal = self._parse_stop_loss(sl_match, message, channel_id)
            if signal:
                signals.append(signal)
        
        # 嘗試 STC (賣出平倉)
        stc_match = self.PATTERNS["stc_pattern"].search(clean_message)
        if stc_match:
            print(f"[DEBUG] STC 匹配: {stc_match.groups()}")
            signal = self._parse_stc(stc_match, message, channel_id)
            if signal:
                signals.append(signal)
        
        print(f"[DEBUG] 解析完成，找到 {len(signals)} 個信號")
        return signals
    
    def _parse_bto(self, match, raw_message: str, channel_id: str) -> Optional[TradingSignal]:
        """解析買入開倉信號"""
        try:
            signal = TradingSignal()
            signal.id = f"bto_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            signal.ticker = match.group(1).upper()
            signal.strike_price = float(match.group(2))
            signal.option_type = match.group(3).lower()
            
            # 解析到期日
            exp_str = match.group(4)
            try:
                signal.expiration = datetime.strptime(exp_str, "%m/%d/%y")
            except ValueError:
                try:
                    signal.expiration = datetime.strptime(exp_str, "%m/%d/%Y")
                except ValueError:
                    pass
            
            signal.premium = float(match.group(5))
            signal.entry_price = signal.premium
            signal.action = OrderAction.BUY_TO_OPEN
            signal.status = OrderStatus.OPEN
            signal.raw_message = raw_message
            signal.channel_id = channel_id
            
            # 更新持倉追蹤
            key = f"{signal.ticker}{signal.strike_price}{signal.option_type}"
            self.positions[key] = signal
            
            return signal
        except Exception as e:
            print(f"解析 BTO 錯誤: {e}")
            return None
    
    def _parse_take_profit(self, match, raw_message: str, channel_id: str) -> Optional[TradingSignal]:
        """解析止盈信號"""
        try:
            ticker = match.group(1).upper()
            pnl_str = match.group(2)
            pnl = float(pnl_str) if pnl_str else None
            
            # 查找對應的持倉
            for key, position in self.positions.items():
                if position.ticker == ticker and position.status == OrderStatus.OPEN:
                    signal = TradingSignal()
                    signal.id = f"tp_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    signal.ticker = ticker
                    signal.action = OrderAction.TAKE_PROFIT
                    signal.status = OrderStatus.WIN if pnl and pnl > 0 else OrderStatus.CLOSED
                    signal.pnl_percent = pnl
                    signal.entry_price = position.entry_price
                    signal.exit_price = position.entry_price * (1 + pnl/100) if pnl else None
                    signal.raw_message = raw_message
                    signal.channel_id = channel_id
                    signal.notes = f"止盈通知，原持倉 PnL: {pnl}%"
                    
                    # 關閉持倉
                    position.status = OrderStatus.WIN
                    position.pnl_percent = pnl
                    position.exit_price = signal.exit_price
                    
                    return signal
            
            # 沒有找到持倉，創建一個簡單的信號
            signal = TradingSignal()
            signal.id = f"tp_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            signal.ticker = ticker
            signal.action = OrderAction.TAKE_PROFIT
            signal.status = OrderStatus.WIN
            signal.pnl_percent = pnl
            signal.raw_message = raw_message
            signal.channel_id = channel_id
            signal.notes = "止盈通知 (未找到原始持倉)"
            
            return signal
        except Exception as e:
            print(f"解析止盈錯誤: {e}")
            return None
    
    def _parse_stop_loss(self, match, raw_message: str, channel_id: str) -> Optional[TradingSignal]:
        """解析止損信號"""
        try:
            ticker = match.group(1).upper()
            
            # 查找對應的持倉
            for key, position in self.positions.items():
                if position.ticker == ticker and position.status == OrderStatus.OPEN:
                    signal = TradingSignal()
                    signal.id = f"sl_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    signal.ticker = ticker
                    signal.action = OrderAction.STOP_LOSS
                    signal.status = OrderStatus.LOSS
                    signal.pnl_percent = -100  # 止損預設為虧損
                    signal.entry_price = position.entry_price
                    signal.raw_message = raw_message
                    signal.channel_id = channel_id
                    signal.notes = f"止損通知，原持倉 PnL: -100%"
                    
                    # 關閉持倉
                    position.status = OrderStatus.LOSS
                    position.exit_price = position.entry_price * 0.5  # 假設虧損50%
                    position.pnl_percent = -50
                    
                    return signal
            
            # 沒有找到持倉
            signal = TradingSignal()
            signal.id = f"sl_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            signal.ticker = ticker
            signal.action = OrderAction.STOP_LOSS
            signal.status = OrderStatus.LOSS
            signal.raw_message = raw_message
            signal.channel_id = channel_id
            signal.notes = "止損通知 (未找到原始持倉)"
            
            return signal
        except Exception as e:
            print(f"解析止損錯誤: {e}")
            return None
    
    def _parse_stc(self, match, raw_message: str, channel_id: str) -> Optional[TradingSignal]:
        """解析賣出平倉信號"""
        try:
            signal = TradingSignal()
            signal.id = f"stc_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            signal.ticker = match.group(1).upper()
            signal.strike_price = float(match.group(2))
            signal.option_type = match.group(3).lower()
            
            exp_str = match.group(4)
            try:
                signal.expiration = datetime.strptime(exp_str, "%m/%d/%y")
            except ValueError:
                try:
                    signal.expiration = datetime.strptime(exp_str, "%m/%d/%Y")
                except ValueError:
                    pass
            
            signal.premium = float(match.group(5))
            signal.exit_price = signal.premium
            signal.action = OrderAction.SELL_TO_CLOSE
            signal.raw_message = raw_message
            signal.channel_id = channel_id
            
            # 查找對應持倉並計算 PnL
            key = f"{signal.ticker}{signal.strike_price}{signal.option_type}"
            if key in self.positions:
                position = self.positions[key]
                if position.entry_price:
                    position.exit_price = signal.exit_price
                    position.pnl_percent = ((signal.exit_price - position.entry_price) / position.entry_price) * 100
                    position.status = OrderStatus.WIN if position.pnl_percent > 0 else OrderStatus.LOSS
                    position.action = OrderAction.SELL_TO_CLOSE
                    signal.entry_price = position.entry_price
                    signal.pnl_percent = position.pnl_percent
                    signal.status = position.status
                    
                    # 從持倉中移除
                    del self.positions[key]
            
            return signal
        except Exception as e:
            print(f"解析 STC 錯誤: {e}")
            return None
    
    def _parse_oculus_bto_v2(self, ticker: str, strike_match, raw_message: str, channel_id: str) -> Optional[TradingSignal]:
        """解析 OCULUS 格式買入開倉信號 - 新版本"""
        try:
            signal = TradingSignal()
            signal.id = f"oculus_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            signal.ticker = ticker
            signal.strike_price = float(strike_match.group(1))
            signal.option_type = strike_match.group(2).lower()
            
            # 解析入場價格
            entry_match = self.PATTERNS["oculus_entry_pattern"].search(raw_message)
            if entry_match:
                signal.premium = float(entry_match.group(1))
                signal.entry_price = signal.premium
            else:
                signal.premium = 0.0
                signal.entry_price = None
            
            signal.action = OrderAction.BUY_TO_OPEN
            signal.status = OrderStatus.OPEN
            signal.raw_message = raw_message
            signal.channel_id = channel_id
            
            # 嘗試解析到期日 (支援 0dte 格式)
            expiry_match = self.PATTERNS["oculus_expiry_pattern"].search(raw_message)
            if not expiry_match:
                expiry_match = self.PATTERNS["oculus_expiry_cn_pattern"].search(raw_message)
            
            if expiry_match:
                exp_str = expiry_match.group(1).strip().lower()
                if '0dte' in exp_str:
                    signal.expiration = datetime.now()
                    signal.notes = "0dte - 今天到期"
                else:
                    try:
                        if '/' in exp_str:
                            parts = exp_str.split('/')
                            if len(parts) == 3:
                                signal.expiration = datetime.strptime(exp_str, "%m/%d/%Y")
                            elif len(parts) == 2:
                                signal.expiration = datetime.strptime(exp_str, "%m/%d")
                                signal.expiration = signal.expiration.replace(year=datetime.now().year)
                    except ValueError:
                        pass
            
            # 檢測彩票標記 (Lotto/彩票)
            if 'lotto' in raw_message.lower() or '彩票' in raw_message:
                signal.notes = (signal.notes + " | 🎰 彩票" if signal.notes else "🎰 彩票") + " (高風險)"
            
            # 更新持倉追蹤
            key = f"{signal.ticker}{signal.strike_price}{signal.option_type}"
            self.positions[key] = signal
            
            return signal
        except Exception as e:
            print(f"解析 OCULUS BTO v2 錯誤: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _parse_oculus_bto(self, match, raw_message: str, channel_id: str) -> Optional[TradingSignal]:
        """解析 OCULUS 格式買入開倉信號"""
        try:
            # 增強：確保 ticker 不是 OCULUS 或其他頻道名稱
            ticker_candidate = match.group(1).upper()
            print(f"[DEBUG] _parse_oculus_bto: ticker_candidate = {ticker_candidate}")
            
            # 排除常見的頻道名稱
            forbidden_names = {'OCULUS', 'DISCORD', 'TELEGRAM', 'SIGNAL', 'TRADING', 'ALERT', 'NOTIFY'}
            if ticker_candidate in forbidden_names:
                print(f"[DEBUG] _parse_oculus_bto: {ticker_candidate} 是頻道名稱，跳過")
                return None
            
            signal = TradingSignal()
            signal.id = f"oculus_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            signal.ticker = ticker_candidate
            signal.strike_price = float(match.group(2))
            signal.option_type = match.group(3).lower()
            print(f"[DEBUG] _parse_oculus_bto: strike={signal.strike_price}, option={signal.option_type}")
            
            # 解析入場價格 - 使用單獨的正則表達式
            entry_pattern = re.compile(r'(?i)Entry[:\s]*\$?([\d.]+)', re.DOTALL)
            entry_cn_pattern = re.compile(r'(?i)入场(?:价)?[:\s]*\$?([\d.]+)', re.DOTALL)
            
            entry_match = entry_pattern.search(raw_message)
            if not entry_match:
                entry_match = entry_cn_pattern.search(raw_message)
            
            if entry_match:
                signal.premium = float(entry_match.group(1))
                signal.entry_price = signal.premium
            else:
                signal.premium = 0.0
                signal.entry_price = None
            
            signal.action = OrderAction.BUY_TO_OPEN
            signal.status = OrderStatus.OPEN
            signal.raw_message = raw_message
            signal.channel_id = channel_id
            
            # 嘗試解析到期日
            expiry_match = self.PATTERNS["oculus_expiry_pattern"].search(raw_message)
            if not expiry_match:
                expiry_match = self.PATTERNS["oculus_expiry_cn_pattern"].search(raw_message)
            
            if expiry_match:
                exp_str = expiry_match.group(1)
                # 處理 0dte 格式
                if '0dte' in exp_str.lower():
                    signal.expiration = datetime.now()
                else:
                    try:
                        exp_str = exp_str.strip()
                        if '/' in exp_str:
                            parts = exp_str.split('/')
                            if len(parts) == 3:
                                signal.expiration = datetime.strptime(exp_str, "%m/%d/%Y")
                            elif len(parts) == 2:
                                signal.expiration = datetime.strptime(exp_str, "%m/%d")
                                signal.expiration = signal.expiration.replace(year=datetime.now().year)
                    except ValueError:
                        pass
            
            # 更新持倉追蹤
            key = f"{signal.ticker}{signal.strike_price}{signal.option_type}"
            self.positions[key] = signal
            
            return signal
        except Exception as e:
            print(f"解析 OCULUS BTO 錯誤: {e}")
            return None
    
    def _parse_oculus_update(self, match, raw_message: str, channel_id: str) -> Optional[TradingSignal]:
        """解析 OCULUS 價格更新信號"""
        try:
            current_price = float(match.group(1))
            entry_price = float(match.group(2))
            
            # 計算盈虧百分比
            pnl_percent = ((current_price - entry_price) / entry_price) * 100
            
            # 嘗試找對應的持倉
            ticker = None
            for key, position in self.positions.items():
                if position.entry_price == entry_price and position.status == OrderStatus.OPEN:
                    ticker = position.ticker
                    # 更新持倉價格
                    position.entry_price = current_price
                    break
            
            # 沒有找到持倉，創建更新信號
            signal = TradingSignal()
            signal.id = f"update_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            signal.ticker = ticker if ticker else "UNKNOWN"
            signal.action = OrderAction.UPDATE
            signal.status = OrderStatus.OPEN
            signal.entry_price = entry_price
            signal.exit_price = current_price
            signal.pnl_percent = pnl_percent
            signal.raw_message = raw_message
            signal.channel_id = channel_id
            signal.notes = f"價格更新: {current_price} from {entry_price} ({pnl_percent:+.1f}%)"
            
            return signal
        except Exception as e:
            print(f"解析 OCULUS 更新錯誤: {e}")
            return None
    
    def _parse_embeds(self, embeds: List[Dict[str, Any]], channel_id: str) -> List[TradingSignal]:
        """解析 Discord Embed 格式的交易訊息（如 JPM）"""
        signals = []
        
        try:
            for embed in embeds:
                if not isinstance(embed, dict):
                    continue
                
                title = embed.get('title', '') or ''
                description = embed.get('description', '') or ''
                footer = embed.get('footer', {}).get('text', '') or ''
                
                print(f"\n[DEBUG] 解析 Embed:")
                print(f"[DEBUG]   Title: {title}")
                print(f"[DEBUG]   Description: {description[:100]}")
                print(f"[DEBUG]   Footer: {footer[:50]}")
                
                # 判斷是否為 JPM 交易訊息
                if not ('Jpm' in footer or 'JPM' in title or 'jpm' in title.lower()):
                    continue
                
                # 解析標題確定動作類型
                action_type = 'unknown'
                title_lower = title.lower().strip()
                
                if 'open' in title_lower:
                    action_type = 'open'
                elif 'update' in title_lower:
                    action_type = 'update'
                elif 'close' in title_lower or 'all out' in description.lower():
                    action_type = 'close'
                else:
                    # 從 description 判斷
                    if '+' in description and '%' in description:
                        action_type = 'update'
                    elif 'out' in description.lower() or '平倉' in description:
                        action_type = 'close'
                
                # 解析內容
                desc_match = self.PATTERNS["jpm_embed_pattern"].search(description)
                
                if desc_match:
                    print(f"[DEBUG] JPM Embed 匹配成功: {desc_match.groups()}")
                    
                    ticker = desc_match.group(1).upper()
                    exp_month = desc_match.group(2)
                    exp_day = desc_match.group(3)
                    strike_price = float(desc_match.group(4))
                    option_type = desc_match.group(5).lower()
                    price_str = desc_match.group(6)
                    notes = desc_match.group(7) or ''
                    
                    # 解析 PnL 百分比
                    pnl_match = self.PATTERNS["jpm_pnl_pattern"].search(description)
                    pnl_percent = float(pnl_match.group(1)) if pnl_match else None
                    
                    # 解析價格
                    premium = float(price_str) if price_str else 0.0
                    
                    signal = TradingSignal()
                    signal.id = f"jpm_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    signal.ticker = ticker
                    signal.strike_price = strike_price
                    signal.option_type = option_type
                    signal.premium = premium
                    signal.raw_message = f"[EMBED] {title}\n{description}"
                    signal.channel_id = channel_id
                    
                    # 解析到期日
                    try:
                        exp_str = f"{exp_month}/{exp_day}"
                        signal.expiration = datetime.strptime(exp_str, "%m/%d")
                        signal.expiration = signal.expiration.replace(year=datetime.now().year)
                    except ValueError:
                        pass
                    
                    # 設置動作和狀態
                    if action_type == 'open':
                        signal.action = OrderAction.BUY_TO_OPEN
                        signal.status = OrderStatus.OPEN
                        signal.entry_price = premium
                        signal.notes = notes if notes else "JPM 買入開倉"
                        # 更新持倉追蹤
                        key = f"{signal.ticker}{signal.strike_price}{signal.option_type}"
                        self.positions[key] = signal
                        
                    elif action_type == 'update':
                        signal.action = OrderAction.UPDATE
                        signal.status = OrderStatus.OPEN
                        signal.entry_price = premium
                        signal.pnl_percent = pnl_percent
                        signal.notes = notes if notes else f"PnL: {pnl_percent:+.1f}%" if pnl_percent else "更新"
                        
                        # 更新持倉追蹤
                        key = f"{signal.ticker}{signal.strike_price}{signal.option_type}"
                        if key in self.positions:
                            self.positions[key].entry_price = premium
                            self.positions[key].pnl_percent = pnl_percent
                            
                    elif action_type == 'close':
                        signal.action = OrderAction.SELL_TO_CLOSE
                        signal.status = OrderStatus.CLOSED
                        signal.exit_price = premium
                        signal.pnl_percent = pnl_percent
                        signal.notes = notes if notes else "已平倉"
                        
                        # 查找並關閉持倉
                        key = f"{signal.ticker}{signal.strike_price}{signal.option_type}"
                        if key in self.positions:
                            position = self.positions[key]
                            position.exit_price = premium
                            position.pnl_percent = pnl_percent
                            position.status = OrderStatus.CLOSED
                            position.action = OrderAction.SELL_TO_CLOSE
                            del self.positions[key]
                    
                    signals.append(signal)
                    print(f"[DEBUG] JPM 信號創建: {signal.ticker} {signal.action.value} {signal.strike_price}{signal.option_type}")
                    
        except Exception as e:
            print(f"[ERROR] 解析 Embed 錯誤: {e}")
            import traceback
            traceback.print_exc()
        
        return signals
    
    def get_statistics(self) -> dict:
        """獲取交易統計"""
        total = len([s for s in self.signals if s.action in [OrderAction.BUY_TO_OPEN, OrderAction.SELL_TO_CLOSE]])
        wins = len([s for s in self.signals if s.status == OrderStatus.WIN])
        losses = len([s for s in self.signals if s.status == OrderStatus.LOSS])
        
        win_rate = (wins / total * 100) if total > 0 else 0
        
        pnls = [s.pnl_percent for s in self.signals if s.pnl_percent is not None]
        avg_pnl = sum(pnls) / len(pnls) if pnls else 0
        
        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 2),
            "avg_pnl": round(avg_pnl, 2),
            "open_positions": len(self.positions),
            "total_signals": len(self.signals)
        }
