"""
數據處理模組 - 負責儲存和管理 Discord 訊息數據
"""

import csv
import json
import os
import asyncio
import aiohttp
import requests
from datetime import datetime
from urllib.parse import urlparse
import sys

# 添加專案根目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import CSV_FILE, MEDIA_DIR, DOWNLOAD_ATTACHMENTS, MAX_ATTACHMENT_SIZE_MB


class DataHandler:
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
        # 保留中文、英文、數字、底線、連字符、點
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        return filename.strip()

    def _get_attachment_info(self, attachment):
        """獲取附件資訊"""
        return {
            'id': attachment.id,
            'filename': attachment.filename,
            'url': attachment.url,
            'size': attachment.size,
            'content_type': attachment.content_type,
            'height': attachment.height,
            'width': attachment.width
        }

    def _get_embed_info(self, embed):
        """獲取嵌入資訊"""
        info = {
            'type': embed.type,
        }
        if embed.title:
            info['title'] = embed.title
        if embed.description:
            info['description'] = embed.description[:500]  # 限制長度
        if embed.url:
            info['url'] = embed.url
        if embed.color:
            info['color'] = str(embed.color)
        if embed.image:
            info['image'] = {
                'url': embed.image.url,
                'width': embed.image.width,
                'height': embed.image.height
            }
        if embed.thumbnail:
            info['thumbnail'] = {
                'url': embed.thumbnail.url,
                'width': embed.thumbnail.width,
                'height': embed.thumbnail.height
            }
        if embed.footer:
            info['footer'] = embed.footer.text
        if embed.timestamp:
            info['timestamp'] = str(embed.timestamp)
        return info

    async def _download_attachment(self, attachment, channel_id):
        """非同步下載附件"""
        if not DOWNLOAD_ATTACHMENTS:
            return None

        try:
            # 檢查檔案大小
            size_mb = attachment.size / (1024 * 1024)
            if size_mb > MAX_ATTACHMENT_SIZE_MB:
                print(f"附件 {attachment.filename} 大小超過限制 ({size_mb:.2f}MB)，跳過下載")
                return None

            # 創建頻道資料夾
            channel_dir = os.path.join(self.media_dir, str(channel_id))
            os.makedirs(channel_dir, exist_ok=True)

            # 清理檔案名稱
            safe_filename = self._sanitize_filename(attachment.filename)
            save_path = os.path.join(channel_dir, safe_filename)

            # 如果檔案已存在，添加數字後綴
            if os.path.exists(save_path):
                base, ext = os.path.splitext(safe_filename)
                counter = 1
                while os.path.exists(save_path):
                    safe_filename = f"{base}_{counter}{ext}"
                    save_path = os.path.join(channel_dir, safe_filename)
                    counter += 1

            # 下載檔案
            print(f"正在下載附件: {attachment.filename}")
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as resp:
                    if resp.status == 200:
                        with open(save_path, 'wb') as f:
                            async for chunk in resp.content.iter_chunked(8192):
                                f.write(chunk)
                        print(f"已下載: {save_path}")
                        return save_path

        except Exception as e:
            print(f"下載附件失敗 {attachment.filename}: {e}")
            return None

    async def save_message(self, message):
        """儲存單條訊息"""
        try:
            # 獲取附件資訊
            attachments_data = []
            for attachment in message.attachments:
                attachment_info = self._get_attachment_info(attachment)
                # 非同步下載附件
                download_path = await self._download_attachment(attachment, message.channel.id)
                if download_path:
                    attachment_info['local_path'] = download_path
                attachments_data.append(attachment_info)

            # 獲取嵌入資訊
            embeds_data = [self._get_embed_info(embed) for embed in message.embeds]

            # 獲取提及的用戶
            mentions = [m.name for m in message.mentions]

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
                len(embeds_data),
                str(message.type),
                json.dumps(mentions, ensure_ascii=False),
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
                    # 解析 JSON 欄位
                    if row.get('attachments'):
                        try:
                            row['attachments'] = json.loads(row['attachments'])
                        except:
                            row['attachments'] = []
                    if row.get('mentions'):
                        try:
                            row['mentions'] = json.loads(row['mentions'])
                        except:
                            row['mentions'] = []
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
