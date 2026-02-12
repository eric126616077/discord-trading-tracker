"""
Flask 網頁伺服器 - Discord 交易追蹤器
"""

from flask import Flask, render_template, jsonify, request, Response
import json
import os
import sys
import traceback
from datetime import datetime

# 添加專案根目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import WEB_HOST, WEB_PORT

app = Flask(__name__)


def get_data_handler():
    """保留但不再使用"""
    pass


@app.route('/')
def index():
    """首頁 - 重新導向到交易儀表板"""
    from flask import redirect
    return redirect('/trading')


# ============ 舊版 Discord 訊息提取 (已停用) ============
# @app.route('/channel/<channel_id>')
# def channel_view(channel_id):
#     """頻道詳情頁"""
#     return render_template('channel.html', channel_id=channel_id)
#
# @app.route('/api/statistics')
# def get_statistics():
#     """獲取統計資訊"""
#     ...
#
# @app.route('/api/channels')
# def get_channels():
#     """獲取所有頻道列表"""
#     ...
#
# @app.route('/api/messages')
# def get_messages():
#     """獲取所有訊息或按條件篩選"""
#     ...


# ============ 舊版 Discord 訊息提取 (已停用) ============
# 這些路由不再使用，全部功能已整合到交易追蹤器
# @app.route('/channel/<channel_id>')
# @app.route('/api/channel/<channel_id>/messages')
# @app.route('/api/message/<message_id>')
# @app.route('/api/export')
# @app.route('/api/export/json')
# @app.route('/api/media/<path:filename>')


@app.route('/api/health')
def health_check():
    """健康檢查"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat()
    })


# ============ 訊息監控 API（客戶端音效用）==========

_extractor = None

def set_extractor(ext):
    """設定正在運行的提取器"""
    global _extractor
    _extractor = ext

@app.route('/api/messages/latest')
def get_latest_message():
    """取得最新訊息時間戳（用於客戶端檢測新訊息）"""
    try:
        tracker = get_trading_tracker()
        messages = tracker.get_all_messages()
        
        if messages:
            # 取得最新訊息
            latest = messages[0]  # 已經按時間倒序
            return jsonify({
                'has_new': True,
                'latest_timestamp': latest.get('timestamp', ''),
                'latest_id': latest.get('id', ''),
                'count': len(messages)
            })
        
        return jsonify({
            'has_new': False,
            'latest_timestamp': '',
            'latest_id': '',
            'count': 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ 交易儀表板 API ============

@app.route('/trading')
def trading_dashboard():
    """交易儀表板頁面"""
    return render_template('trading.html')


@app.route('/debug')
def debug_page():
    """調試頁面"""
    return render_template('debug.html')


def get_trading_tracker():
    """動態導入 TradingTracker 以避免循環引用"""
    from bot.trading_tracker import TradingTracker
    return TradingTracker()


@app.route('/api/trading')
def get_trading_data():
    """獲取交易數據"""
    try:
        tracker = get_trading_tracker()
        return jsonify({
            'orders': tracker.get_all_orders(),
            'open_orders': tracker.get_open_orders(),
            'closed_orders': tracker.get_closed_orders(),
            'statistics': tracker.get_statistics(),
            'messages': tracker.get_all_messages()  # 添加 messages
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/trading/orders')
def get_trading_orders():
    """獲取所有訂單"""
    try:
        tracker = get_trading_tracker()
        orders = tracker.get_all_orders()
        
        # 支援篩選
        status = request.args.get('status')  # open, closed
        ticker = request.args.get('ticker')
        limit = request.args.get('limit', type=int)
        
        if status:
            if status == 'open':
                orders = tracker.get_open_orders()
            elif status == 'closed':
                orders = tracker.get_closed_orders()
        
        if ticker:
            orders = [o for o in orders if o.get('ticker', '').upper() == ticker.upper()]
        
        if limit:
            orders = orders[:limit]
        
        return jsonify({
            'orders': orders,
            'total': len(orders)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/trading/orders/<order_id>')
def get_order_detail(order_id):
    """獲取訂單詳情"""
    try:
        tracker = get_trading_tracker()
        order = tracker.get_order_by_id(order_id)
        
        if order:
            return jsonify({'order': order})
        return jsonify({'error': 'Order not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/trading/statistics')
def get_trading_statistics():
    """獲取統計數據"""
    try:
        tracker = get_trading_tracker()
        return jsonify(tracker.get_statistics())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/trading/messages')
def get_all_messages():
    """獲取所有訊息"""
    try:
        tracker = get_trading_tracker()
        messages = tracker.get_all_messages()
        
        # 支援篩選
        has_order = request.args.get('has_order')  # true, false
        channel_id = request.args.get('channel_id')
        limit = request.args.get('limit', type=int)
        offset = request.args.get('offset', type=int, default=0)
        
        if has_order is not None:
            filter_value = has_order.lower() == 'true'
            messages = [m for m in messages if m.get('has_order') == filter_value]
        
        if channel_id:
            messages = [m for m in messages if m.get('channel_id') == channel_id]
        
        # 按時間倒序
        messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        total = len(messages)
        if limit:
            messages = messages[offset:offset + limit]
        
        return jsonify({
            'messages': messages,
            'total': total,
            'limit': limit,
            'offset': offset
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/trading/test', methods=['POST'])
def test_parse_message():
    """測試解析訊息"""
    try:
        data = request.get_json()
        message = data.get('message', '')
        channel_id = data.get('channel_id', '')
        
        tracker = get_trading_tracker()
        order_ids = tracker.add_message(message, channel_id)
        
        orders = [tracker.get_order_by_id(oid) for oid in order_ids]
        
        return jsonify({
            'parsed_orders': orders,
            'statistics': tracker.get_statistics()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/trading/clear', methods=['POST'])
def clear_trading_data():
    """清除所有數據"""
    try:
        tracker = get_trading_tracker()
        tracker.clear_all()
        return jsonify({'status': 'ok', 'message': '已清除所有數據'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/trading/deduplicate', methods=['POST'])
def deduplicate_data():
    """清理重複數據"""
    try:
        tracker = get_trading_tracker()
        result = tracker.deduplicate()
        return jsonify({
            'status': 'ok', 
            'message': f'已清理重複數據',
            'removed_messages': result.get('removed_messages', 0),
            'remaining_messages': result.get('remaining_messages', 0)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/trading/debug')
def debug_trading_data():
    """調試：查看原始數據"""
    try:
        tracker = get_trading_tracker()
        return jsonify({
            'orders_count': len(tracker.orders),
            'messages_count': len(tracker.all_messages),
            'open_positions_count': len(tracker.open_positions),
            'data_file_exists': os.path.exists(tracker.data_file),
            'data_file_path': tracker.data_file
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/api/trading/export')
def export_trading_data():
    """導出數據"""
    try:
        tracker = get_trading_tracker()
        data = {
            'exported_at': datetime.now().isoformat(),
            'statistics': tracker.get_statistics(),
            'orders': tracker.get_all_orders(),
            'messages': tracker.get_all_messages()
        }
        
        return Response(
            json.dumps(data, ensure_ascii=False, indent=2),
            mimetype='application/json; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename=trading_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.errorhandler(404)
def not_found(e):
    """404 錯誤處理"""
    return render_template('error.html', error='Page not found'), 404


@app.errorhandler(500)
def server_error(e):
    """500 錯誤處理"""
    return render_template('error.html', error='Server error'), 500


def create_app():
    """創建 Flask 應用程式"""
    return app


if __name__ == '__main__':
    app.run(host=WEB_HOST, port=WEB_PORT, debug=True)
