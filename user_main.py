"""
Discord 私人頻道內容提取器 - 使用者帳號版本

⚠️ 風險警告 ⚠️
使用個人帳號 Token 可能違反 Discord ToS，可能導致帳號被封鎖。
建議僅用於測試目的，長期使用請使用 Bot。

使用方法：
    python user_main.py
"""

import asyncio
import json
import os
import sys
import threading
import time
from datetime import datetime

# 添加專案根目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config.settings import (
    USER_TOKEN, CHANNEL_IDS, CSV_FILE, MEDIA_DIR,
    DOWNLOAD_ATTACHMENTS, WEB_HOST, WEB_PORT
)
from bot.data_handler_user import UserDataHandler
from bot.trading_tracker import TradingTracker
from web.app import app

# 全域變數 - 用於 Flask API 存取
_extractor = None

def get_extractor():
    """取得正在運行的提取器"""
    return _extractor

print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   Discord 私人頻道內容提取器 - 使用者帳號版本              ║
║                                                          ║
║   ⚠️  警告：使用個人 Token 有風險  ⚠️                     ║
║                                                          ║
║   - 可能違反 Discord ToS                                 ║
║   - 可能導致帳號被封鎖                                    ║
║   - 不建議長期使用                                        ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
""")


class DiscordUserExtractor:
    """使用 Discord WebSocket 監控訊息"""

    def __init__(self, data_handler, trading_tracker, channel_ids):
        self.data_handler = data_handler
        self.trading_tracker = trading_tracker
        self.channel_ids = [int(cid) for cid in channel_ids]
        self.running = False
        self.gateway_url = "wss://gateway.discord.gg/?encoding=json&v=9"
        self.heartbeat_interval = None
        self.session_id = None
        self.sequence = None

    async def connect(self):
        """連接到 Discord Gateway - 實時監控版本"""
        import websockets
        import requests

        print("正在連接 Discord...")

        # 驗證 Token 是否有效（先測試 HTTP API）
        try:
            resp = requests.get(
                "https://discord.com/api/v9/users/@me",
                headers={"Authorization": USER_TOKEN},
                timeout=10
            )
            if resp.status_code == 401:
                print("錯誤：Token 無效或已過期")
                return False
            elif resp.status_code == 200:
                user_data = resp.json()
                print(f"✓ Token 驗證成功: {user_data['username']}#{user_data['discriminator']}")
            else:
                print(f"警告：API 返回狀態碼 {resp.status_code}")
        except requests.exceptions.Timeout:
            print("錯誤：網路連線超時，請檢查網路設定")
            return False
        except Exception as e:
            print(f"警告：驗證 API 失敗: {e}")

        # 獲取 Gateway URL
        try:
            resp = requests.get(
                "https://discord.com/api/v9/gateway",
                headers={"Authorization": USER_TOKEN},
                timeout=10
            )
            if resp.status_code == 401:
                print("錯誤：Token 無效或已過期")
                return False
            gateway_info = resp.json()
            self.gateway_url = gateway_info["url"] + "/?v=9&encoding=json"
            print(f"Gateway URL: {self.gateway_url}")
        except Exception as e:
            print(f"獲取 Gateway URL 失敗: {e}")
            return False

        # 持續監控直到手動停止
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while consecutive_errors < max_consecutive_errors:
            try:
                print(f"\n🔄 正在建立 Gateway 連接... (連續錯誤: {consecutive_errors}/{max_consecutive_errors})")
                
                async with websockets.connect(
                    self.gateway_url,
                    open_timeout=60,
                    close_timeout=10,
                    ping_interval=20,      # 每 20 秒發送 ping
                    ping_timeout=10        # ping 超時 10 秒
                ) as websocket:
                    print("✅ Gateway 連接成功 - 開始監控實時訊息")
                    consecutive_errors = 0
                    self.running = True
                    
                    # 主循環：接收訊息
                    while self.running:
                        try:
                            message = await asyncio.wait_for(
                                websocket.recv(),
                                timeout=30  # 30秒超時
                            )
                            await self.handle_message(websocket, message)
                            
                        except asyncio.TimeoutError:
                            # 發送心跳保持連接
                            await self.send_heartbeat(websocket)
                            print("💓 Heartbeat 發送 - 連接活躍")
                            
                        except websockets.ConnectionClosed as e:
                            print(f"⚠️ 連接關閉: {e}")
                            consecutive_errors += 1
                            break
                            
                        except Exception as e:
                            print(f"⚠️ 接收訊息錯誤: {e}")
                            consecutive_errors += 1
                            await asyncio.sleep(2)
                            break

            except websockets.ConnectionClosed as e:
                print(f"❌ Gateway 連接關閉: {e}")
                consecutive_errors += 1
                
            except Exception as e:
                print(f"❌ Gateway 連接錯誤: {e}")
                consecutive_errors += 1
                await asyncio.sleep(5)  # 錯誤後等待
                
            # 重新連接前等待
            if consecutive_errors < max_consecutive_errors and self.running:
                wait_time = consecutive_errors * 3
                print(f"⏳ 等待 {wait_time} 秒後重新連接...")
                await asyncio.sleep(wait_time)

        print("❌ 已達最大連續錯誤次數，停止監控")
        return False

    async def handle_message(self, websocket, message):
        """處理 Gateway 訊息 - 實時監控增強版"""
        import json as json_lib

        data = json_lib.loads(message)
        op = data.get("op")

        if op == 0:  # Dispatch
            self.sequence = data.get("s")
            event_type = data.get("t")
            event_data = data.get("d", {})

            if event_type == "READY":
                await self.on_ready(websocket, data["d"])
                
            elif event_type == "MESSAGE_CREATE":
                channel_id = event_data.get("channel_id")
                print(f"\n📨 收到新訊息! 頻道: {channel_id}")
                await self.on_message(event_data)
                
            elif event_type == "MESSAGE_UPDATE":
                print(f"✏️ 訊息已編輯: {event_data.get('id')}")
                await self.on_message_update(event_data)
                
            elif event_type == "MESSAGE_DELETE":
                print(f"🗑️ 訊息已刪除: {event_data.get('id')}")
                await self.on_message_delete(event_data)
                
            elif event_type == "RESUMED":
                print("✅ 連接已恢復 (Resumed)")
                
            elif event_type == "INVALID_SESSION":
                print("⚠️ 連接無效，需要重新驗證")
                self.running = False

        elif op == 10:  # Hello
            self.heartbeat_interval = data["d"]["heartbeat_interval"] / 1000
            print(f"💓 Heartbeat 間隔: {self.heartbeat_interval:.1f}秒")
            # 開始身份驗證
            await self.authenticate(websocket)

        elif op == 11:  # Heartbeat ACK
            print("💓 Heartbeat ACK 收到")

        elif op == 9:  # Invalid Session
            print("⚠️ 連接被 Discord 拒絕，5秒後重新連接...")
            self.running = False

    async def authenticate(self, websocket):
        """發送身份驗證"""
        import json

        # 識別為用戶
        identify_data = {
            "op": 2,
            "d": {
                "token": USER_TOKEN,
                "properties": {
                    "os": "windows",
                    "browser": "Chrome",
                    "device": "pc"
                },
                "presence": {
                    "status": "online",
                    "activities": [],
                    "since": 0,
                    "afk": False
                }
            }
        }

        await websocket.send(json.dumps(identify_data))
        print("已發送身份驗證...")

    async def on_ready(self, websocket, data):
        """準備就緒 - 開始實時監控"""
        user = data.get('user', {})
        print(f"\n{'='*60}")
        print(f"✅ 【Discord 連接成功】")
        print(f"   用戶: {user.get('username')}#{user.get('discriminator')}")
        print(f"   用戶 ID: {user.get('id')}")
        print(f"   監控頻道數: {len(self.channel_ids)}")
        for cid in self.channel_ids:
            print(f"   - {cid}")
        print(f"{'='*60}")
        
        # 先獲取歷史訊息
        print(f"\n📥 Step 1: 獲取歷史訊息...")
        await self.request_messages(websocket)
        
        # 開始實時監控
        print(f"\n🔴 【實時監控已啟動】")
        print(f"   等待新訊息... (按 Ctrl+C 停止)")
        print(f"{'='*60}\n")

    async def request_messages(self, websocket):
        """請求頻道歷史訊息 - 使用 REST API"""
        import json

        print("\n正在通過 REST API 獲取歷史訊息...")
        
        for channel_id in self.channel_ids:
            print(f"\n正在獲取頻道 {channel_id} 的歷史訊息...")
            success = await self.fetch_channel_messages_via_rest(channel_id)
            
            if not success:
                print(f"  ⚠️ 頻道 {channel_id} 獲取失敗，可能沒有權限")
            
            await asyncio.sleep(0.5)  # 避免請求過快

    async def fetch_channel_messages_via_rest(self, channel_id):
        """通過 REST API 獲取頻道訊息"""
        import requests
        import json as json_lib
        
        url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
        headers = {"Authorization": USER_TOKEN}
        params = {"limit": 100}
        
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            
            if resp.status_code == 200:
                messages_data = resp.json()
                if messages_data:
                    print(f"  📥 獲取到 {len(messages_data)} 條歷史訊息")
                    orders_created = 0
                    
                    for msg_data in messages_data:
                        message = self.convert_message_format(msg_data)
                        await self.data_handler.save_message(message)
                        
                        # 記錄訊息
                        content = msg_data.get('content', '')
                        embeds = msg_data.get('embeds', [])
                        msg_id = msg_data.get('id', '')
                        timestamp = msg_data.get('timestamp', '')
                        
                        # 合併嵌入內容
                        embed_content = ''
                        for embed in embeds:
                            if isinstance(embed, dict):
                                if embed.get('title'):
                                    embed_content += embed['title'] + '\n'
                                if embed.get('description'):
                                    embed_content += embed['description'] + '\n'
                        
                        full_content = content + ('\n' + embed_content if embed_content else '')
                        
                        if full_content:
                            order_ids = self.trading_tracker.add_message(
                                content=full_content,
                                channel_id=str(channel_id),
                                message_id=msg_id,
                                timestamp=timestamp,
                                embeds=embeds
                            )
                            if order_ids:
                                orders_created += len(order_ids)
                                for oid in order_ids:
                                    order = self.trading_tracker.get_order_by_id(oid)
                                    if order:
                                        print(f"    📊 {order['ticker']} | {order['notes']}")
                    
                    if orders_created > 0:
                        print(f"  ✅ 共建立 {orders_created} 筆訂單")
                    else:
                        print(f"  ℹ️ 沒有發現交易訂單")
                    
                    return True
                else:
                    print(f"  ℹ️ 頻道沒有訊息")
                    return True
                    
            elif resp.status_code == 403:
                print(f"  ❌ 沒有權限訪問此頻道 (403)")
                return False
                
            elif resp.status_code == 404:
                print(f"  ❌ 頻道不存在 (404)")
                return False
                
            elif resp.status_code == 429:
                print(f"  ⚠️ 被限流了，請稍後重試 (429)")
                return False
                
            else:
                print(f"  ❌ 未知錯誤: {resp.status_code}")
                return False
                
        except Exception as e:
            print(f"  ❌ 請求失敗: {e}")
            return False

    async def on_message(self, data):
        """收到新訊息 - 實時監控"""
        channel_id = str(data.get("channel_id"))
        message_id = data.get("id")
        content = data.get("content", "")
        author = data.get("author", {}).get("username", "Unknown")
        timestamp = data.get("timestamp", "")
        
        # 檢查是否是需要監控的頻道
        if channel_id not in [str(cid) for cid in self.channel_ids]:
            return

        print(f"\n{'='*60}")
        print(f"📨 【實時訊息】")
        print(f"   頻道: {channel_id}")
        print(f"   作者: {author}")
        print(f"   時間: {timestamp}")
        print(f"   內容: {content[:200]}{'...' if len(content) > 200 else ''}")
        print(f"{'='*60}")

        try:
            content = data.get('content', '')
            embeds = data.get('embeds', [])
            
            # 如果有 Embed，則合併 Embed 內容到 content
            embed_content = ''
            for embed in embeds:
                if isinstance(embed, dict):
                    # 提取 embed title
                    if embed.get('title'):
                        embed_content += embed['title'] + '\n'
                    # 提取 embed description
                    if embed.get('description'):
                        embed_content += embed['description'] + '\n'
                    # 提取 embed fields (OCULUS 常見格式)
                    if embed.get('fields'):
                        for field in embed['fields']:
                            if field.get('name') and field.get('value'):
                                embed_content += f"{field['name']}: {field['value']}\n"
            
            # 合併 content 和 embed_content
            full_content = content
            if embed_content:
                full_content = content + '\n' + embed_content
            
            # 轉換為與 Bot 相容的格式
            message = self.convert_message_format(data)
            await self.data_handler.save_message(message)
            print(f"✅ 訊息已儲存 (ID: {message_id})")
            
            # 記錄訊息並解析交易訂單
            if full_content:
                order_ids = self.trading_tracker.add_message(
                    content=full_content,
                    channel_id=channel_id,
                    message_id=message_id,
                    timestamp=timestamp,
                    embeds=embeds  # 傳遞嵌入列表
                )
                
                if order_ids:
                    print(f"\n📊 【交易訂單更新】")
                    for oid in order_ids:
                        order = self.trading_tracker.get_order_by_id(oid)
                        if order:
                            # 顯示訂單摘要
                            ticker = order['ticker']
                            status = order['status']
                            pnl = order.get('pnl_percent')
                            
                            print(f"   {ticker} | {order['notes']}")
                            if pnl is not None:
                                pnl_emoji = "🟢" if pnl > 0 else "🔴"
                                print(f"   {pnl_emoji} PnL: {pnl:+.1f}%")
                            else:
                                print(f"   🔵 持倉中 @ ${order.get('entry_price')}")
                    print()
                else:
                    # 普通訊息，顯示內容預覽
                    preview = content[:100] + "..." if len(content) > 100 else content
                    print(f"   💬 {preview}")
                        
        except Exception as e:
            print(f"❌ 處理訊息失敗: {e}")

    def convert_message_format(self, data):
        """轉換為與 discord.py 相容的格式"""
        # 模擬 discord.py 的訊息物件結構
        return type('Message', (), {
            'id': data.get('id'),
            'channel': type('Channel', (), {
                'id': data.get('channel_id'),
                'name': 'unknown'
            })(),
            'author': type('Author', (), {
                'name': data.get('author', {}).get('username', 'Unknown'),
                'id': data.get('author', {}).get('id'),
                'avatar': type('Avatar', (), {
                    'url': f"https://cdn.discordapp.com/avatars/{data.get('author', {}).get('id')}/{data.get('author', {}).get('avatar')}.png" if data.get('author', {}).get('avatar') else None
                })()
            })(),
            'content': data.get('content', ''),
            'created_at': datetime.fromisoformat(data.get('timestamp').replace('Z', '+00:00')) if data.get('timestamp') else datetime.now(),
            'edited_at': datetime.fromisoformat(data.get('edited_timestamp').replace('Z', '+00:00')) if data.get('edited_timestamp') else None,
            'attachments': [type('Attachment', (), {
                'id': a.get('id'),
                'filename': a.get('filename'),
                'url': a.get('url'),
                'size': a.get('size'),
                'content_type': a.get('content_type'),
                'height': a.get('height'),
                'width': a.get('width')
            })() for a in data.get('attachments', [])],
            'embeds': data.get('embeds', []),
            'type': data.get('type', 0),
            'mentions': data.get('mentions', []),
            'jump_url': f"https://discord.com/channels/@me/{data.get('channel_id')}/{data.get('id')}"
        })

    async def on_message_update(self, data):
        """訊息編輯"""
        print(f"訊息已編輯: {data.get('id')}")

    async def on_message_delete(self, data):
        """訊息刪除"""
        print(f"訊息已刪除: {data.get('id')}")

    async def send_heartbeat(self, websocket):
        """發送心跳 - 保持連接活躍"""
        import json

        if self.sequence:
            heartbeat = {"op": 1, "d": self.sequence}
            try:
                await websocket.send(json.dumps(heartbeat))
                print(f"💓 Heartbeat sent (seq: {self.sequence})")
            except Exception as e:
                print(f"❌ Heartbeat 發送失敗: {e}")

    def stop(self):
        """停止監控"""
        print("\n🛑 收到停止訊號，正在關閉監控...")
        self.running = False


def run_flask(extractor):
    """啟動 Flask 伺服器"""
    from web.app import set_extractor
    set_extractor(extractor)
    print(f"啟動 Flask 網頁伺服器於 http://{WEB_HOST}:{WEB_PORT}")
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False, use_reloader=False)


async def main():
    """主函數"""
    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   Discord 期權交易追蹤器 - 實時監控版本                    ║
║                                                          ║
║   ⚠️  警告：使用個人 Token 有風險  ⚠️                     ║
║                                                          ║
║   - 可能違反 Discord ToS                                 ║
║   - 可能導致帳號被封鎖                                    ║
║   - 不建議長期使用                                        ║
║                                                          ║
║   🌐 訪問交易儀表板: http://0.0.0.0:{PORT}/trading        ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
""".format(PORT=WEB_PORT))

    # 檢查 Token
    if not USER_TOKEN or USER_TOKEN == "YOUR_USER_TOKEN_HERE":
        print("\n錯誤：未設置 Discord Token！")
        print("請在 config/settings.py 中設置 USER_TOKEN")
        print("\n獲取 Token 方法：")
        print("1. 在 Discord 中按 F12 打開開發者工具")
        print("2. 切換到 Network 標籤")
        print("3. 刷新頁面")
        print("4. 找到任何請求，查看 Headers")
        print("5. 找到 'authorization' 或 'x-super-properties'")
        return

    if not CHANNEL_IDS or CHANNEL_IDS == [123456789012345678]:
        print("\n警告：未設置監控頻道 ID！")
        print("請在 config/settings.py 中設置 CHANNEL_IDS")
        return

    # 初始化數據處理器
    print("初始化數據處理器...")
    data_handler = UserDataHandler(csv_file=CSV_FILE, media_dir=MEDIA_DIR)
    
    # 初始化交易追蹤器
    print("初始化交易追蹤器...")
    trading_tracker = TradingTracker()

    # 初始化提取器
    global _extractor
    extractor = DiscordUserExtractor(data_handler, trading_tracker, CHANNEL_IDS)

    # 在背景啟動 Flask
    flask_thread = threading.Thread(target=run_flask, args=(extractor,), daemon=True)
    flask_thread.start()
    print(f"✅ Flask 伺服器已啟動")
    print(f"🌐 交易儀表板: http://127.0.0.1:5000/trading")
    print(f"📊 API 接口: http://127.0.0.1:5000/api/trading")

    # 開始監控
    print(f"\n{'='*60}")
    print("🚀 開始連接 Discord...")
    print("="*60)
    success = await extractor.connect()

    if not success:
        print("\n連接失敗，請檢查 Token 和網路連線")
    else:
        print("\n監控已停止")


def run():
    """運行主程式"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n" + "="*60)
        print("🛑 使用者中斷 - 程式結束")
        print("="*60)
    except Exception as e:
        print(f"\n錯誤: {e}")


if __name__ == "__main__":
    run()
