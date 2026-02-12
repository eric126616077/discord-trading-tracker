"""
用戶版本數據處理模組 - 與 bot/data_handler.py 功能相同
"""

import csv
import json
import os
import sys
import asyncio
import aiohttp
import requests
from datetime import datetime
from urllib.parse import urlparse

# 添加專案根目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import CSV_FILE, MEDIA_DIR, DOWNLOAD_ATTACHMENTS, MAX_ATTACHMENT_SIZE_MB


class UserDataHandler:
    """處理訊息數據的儲存和下載"""

    def __init__(self, csv_file=None, media_dir=None):
        self.csv_file = csv_file or CSV_FILE
        self.media_dir = media_dir or MEDIA_DIR
        self._init_csv()
        self._ensure_media_dir()

    def _init_csv(self):
        """初始化 CSV 檔案"""
        os.makedirs(os.path.dirname(self.csv_file), exist_ok=True)
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'channel_id',
                    'channel_name',
                    'message_id',
                    'author',
                    'author_id',
                    'author_avatar',
                    'content',
                    'timestamp',
                    'edited_timestamp',
                    'attachments',
                    'embeds_count',
                    'type',
                    'mentions',
                    'jump_url'
                ])

    def _ensure_media_dir(self):
        """確保媒體下載目錄存在"""
        os.makedirs(self.media_dir, exist_ok=True)

    def _sanitize_filename(self, filename):
        """清理檔案名稱，移除非法字符"""
        import re
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        return filename.strip()

    async def save_message(self, message):
        """儲存單條訊息"""
        try:
            # 獲取附件資訊
            attachments_data = []
            for attachment in message.attachments:
                attachment_info = {
                    'id': attachment.id,
                    'filename': attachment.filename,
                    'url': attachment.url,
                    'size': attachment.size,
                    'content_type': attachment.content_type,
                    'height': attachment.height,
                    'width': attachment.width
                }
                attachments_data.append(attachment_info)

            # 獲取作者頭像 URL
            author_avatar = str(message.author.avatar.url) if message.author.avatar else None

            # 準備數據
            data = [
                str(message.channel.id),
                message.channel.name,
                str(message.id),
                message.author.name,
                str(message.author.id),
                author_avatar,
                message.content or '',
                message.created_at.isoformat(),
                message.edited_at.isoformat() if message.edited_at else '',
                json.dumps(attachments_data, ensure_ascii=False),
                len(message.embeds),
                str(message.type),
                json.dumps([m['username'] for m in message.mentions] if isinstance(message.mentions, list) else []),
                message.jump_url
            ]

            # 寫入 CSV
            with open(self.csv_file, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(data)

            print(f"已儲存訊息: {message.id} from {message.channel.name}")

        except Exception as e:
            print(f"儲存訊息失敗: {e}")
            import traceback
            traceback.print_exc()

    def get_all_messages(self):
        """讀取所有訊息"""
        messages = []
        if not os.path.exists(self.csv_file):
            return messages

        try:
            with open(self.csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    messages.append(row)
        except Exception as e:
            print(f"讀取訊息失敗: {e}")

        return messages

    def get_messages_by_channel(self, channel_id):
        """根據頻道 ID 獲取訊息"""
        messages = []
        for msg in self.get_all_messages():
            if msg.get('channel_id') == str(channel_id):
                messages.append(msg)
        return messages

    def get_channels(self):
        """獲取所有頻道列表"""
        channels = {}
        for msg in self.get_all_messages():
            channel_id = msg.get('channel_id')
            channel_name = msg.get('channel_name')
            if channel_id and channel_id not in channels:
                channels[channel_id] = {
                    'id': channel_id,
                    'name': channel_name,
                    'message_count': 0
                }
            if channel_id:
                channels[channel_id]['message_count'] += 1
        return list(channels.values())

    def get_statistics(self):
        """獲取統計資訊"""
        messages = self.get_all_messages()
        if not messages:
            return {
                'total_messages': 0,
                'total_channels': 0,
                'total_attachments': 0,
                'date_range': None
            }

        total_attachments = sum(
            len(msg.get('attachments', []))
            for msg in messages
        )

        channels = self.get_channels()

        # 計算日期範圍
        timestamps = [
            datetime.fromisoformat(msg['timestamp'])
            for msg in messages
            if msg.get('timestamp')
        ]
        date_range = None
        if timestamps:
            date_range = {
                'earliest': min(timestamps).isoformat(),
                'latest': max(timestamps).isoformat()
            }

        return {
            'total_messages': len(messages),
            'total_channels': len(channels),
            'total_attachments': total_attachments,
            'date_range': date_range
        }
