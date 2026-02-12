"""
交易數據處理器 - 儲存和管理交易信號
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from bot.trading_parser import TradingSignal, TradingSignalParser

# 數據保留天數
DATA_RETENTION_DAYS = 3

class TradingDataHandler:
    """交易數據處理器"""
    
    def __init__(self, data_file: str = None):
        """初始化交易數據處理器"""
        # 預設數據文件路徑
        if data_file is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(base_dir, 'data')
            os.makedirs(data_dir, exist_ok=True)
            self.data_file = os.path.join(data_dir, 'trading_signals.json')
        else:
            self.data_file = data_file
        
        # 交易信號列表
        self.signals: List[TradingSignal] = []
        
        # 解析器
        self.parser = TradingSignalParser()
        
        # 初始化時載入現有數據
        self.load_data()
    
    def _cleanup_old_data(self):
        """清理超過保留期限的數據"""
        cutoff_date = datetime.now() - timedelta(days=DATA_RETENTION_DAYS)
        original_count = len(self.signals)
        
        self.signals = [s for s in self.signals 
                        if s.timestamp and s.timestamp >= cutoff_date]
        
        removed_count = original_count - len(self.signals)
        if removed_count > 0:
            print(f"🧹 自動清理: 刪除 {removed_count} 條超過 {DATA_RETENTION_DAYS} 天的舊數據")
    
    def add_signal(self, signal: TradingSignal):
        """添加交易信號"""
        self.signals.append(signal)
        self.save_data()
    
    def parse_and_add_message(self, message: str, channel_id: str = "") -> List[TradingSignal]:
        """解析消息並添加交易信號"""
        signals = self.parser.parse_message(message, channel_id)
        for signal in signals:
            self.add_signal(signal)
        return signals
    
    def get_all_signals(self) -> List[dict]:
        """獲取所有交易信號"""
        return [s.to_dict() for s in self.signals]
    
    def get_open_positions(self) -> List[dict]:
        """獲取持倉中的訂單"""
        return [s.to_dict() for s in self.signals if s.status.value == 'open']
    
    def get_statistics(self) -> dict:
        """獲取交易統計"""
        return self.parser.get_statistics()
    
    def save_data(self):
        """保存數據到文件"""
        # 先清理舊數據
        self._cleanup_old_data()
        
        try:
            data = {
                "signals": [s.to_dict() for s in self.signals],
                "last_updated": datetime.now().isoformat()
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存交易數據失敗: {e}")
    
    def load_data(self):
        """從文件載入數據"""
        if not os.path.exists(self.data_file):
            return
        
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 重建信號對象
            for s_data in data.get('signals', []):
                signal = TradingSignal()
                signal.id = s_data.get('id', '')
                signal.ticker = s_data.get('ticker', '')
                signal.action = signal.action.UNKNOWN
                signal.option_type = s_data.get('option_type', '')
                signal.strike_price = s_data.get('strike_price', 0.0)
                signal.premium = s_data.get('premium', 0.0)
                signal.quantity = s_data.get('quantity', 1)
                signal.entry_price = s_data.get('entry_price')
                signal.exit_price = s_data.get('exit_price')
                signal.pnl_percent = s_data.get('pnl_percent')
                signal.status = signal.status.OPEN
                signal.raw_message = s_data.get('raw_message', '')
                signal.channel_id = s_data.get('channel_id', '')
                signal.notes = s_data.get('notes', '')
                
                # 解析時間戳
                if s_data.get('timestamp'):
                    try:
                        signal.timestamp = datetime.fromisoformat(s_data['timestamp'])
                    except:
                        pass
                
                # 解析動作
                action_map = {
                    'BTO': signal.action.BUY_TO_OPEN,
                    'STC': signal.action.SELL_TO_CLOSE,
                    'TP': signal.action.TAKE_PROFIT,
                    'SL': signal.action.STOP_LOSS
                }
                action_str = s_data.get('action', '')
                if action_str in action_map:
                    signal.action = action_map[action_str]
                
                # 解析狀態
                status_map = {
                    'open': signal.status.OPEN,
                    'closed': signal.status.CLOSED,
                    'win': signal.status.WIN,
                    'loss': signal.status.LOSS
                }
                status_str = s_data.get('status', 'open')
                if status_str in status_map:
                    signal.status = status_map[status_str]
                
                self.signals.append(signal)
                
        except Exception as e:
            print(f"載入交易數據失敗: {e}")
    
    def clear_all(self):
        """清除所有數據"""
        self.signals = []
        self.parser.signals = []
        self.parser.positions = {}
        if os.path.exists(self.data_file):
            os.remove(self.data_file)
