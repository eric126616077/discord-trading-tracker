"""
Discord Bot 核心邏輯 - 監控並提取私人頻道訊息
"""

import discord
from discord.ext import commands
import asyncio
import logging
import sys
import os

# 添加專案根目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import CHANNEL_IDS

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DiscordExtractorBot(commands.Bot):
    """Discord 私人頻道內容提取 Bot"""

    def __init__(self, channel_ids=None, data_handler=None):
        # 啟用所有必要的 Intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guild_messages = True
        intents.guilds = True

        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )

        self.channel_ids = channel_ids or CHANNEL_IDS
        self.data_handler = data_handler
        self._setup_logging()

    def _setup_logging(self):
        """設置日誌"""
        self.logger = logging.getLogger('DiscordBot')

    async def on_ready(self):
        """Bot 登入完成後的回調"""
        self.logger.info(f'=================================')
        self.logger.info(f'Bot 已成功登入！')
        self.logger.info(f'用戶名稱: {self.user.name}')
        self.logger.info(f'用戶 ID: {self.user.id}')
        self.logger.info(f'=================================')

        # 監控的頻道列表
        if self.channel_ids:
            self.logger.info(f'正在監控以下頻道 ID:')
            for channel_id in self.channel_ids:
                self.logger.info(f'  - {channel_id}')
        else:
            self.logger.warning('未設置任何監控頻道！')

        # 同步應用程序命令
        try:
            synced = await self.sync_application_commands()
            self.logger.info(f'已同步 {len(synced)} 個應用程序命令')
        except Exception as e:
            self.logger.error(f'同步命令失敗: {e}')

    async def on_message(self, message):
        """收到新訊息時的回調"""
        # 忽略機器人的訊息
        if message.author.bot:
            return

        # 檢查是否是需要監控的頻道
        if self.channel_ids and message.channel.id not in self.channel_ids:
            return

        # 處理訊息
        if self.data_handler:
            try:
                await self.data_handler.save_message(message)
            except Exception as e:
                self.logger.error(f'儲存訊息失敗: {e}')
                import traceback
                traceback.print_exc()

        # 處理命令（如果有的話）
        await self.process_commands(message)

    async def on_message_edit(self, before, after):
        """訊息編輯時的回調"""
        if before.id != after.id:
            return

        if self.channel_ids and after.channel.id not in self.channel_ids:
            return

        self.logger.info(f'訊息被編輯: {after.id} in {after.channel.name}')

    async def on_message_delete(self, message):
        """訊息刪除時的回調"""
        if self.channel_ids and message.channel.id not in self.channel_ids:
            return

        self.logger.info(f'訊息被刪除: {message.id} in {message.channel.name}')

    async def on_channel_create(self, channel):
        """頻道創建時的回調"""
        if isinstance(channel, discord.TextChannel):
            self.logger.info(f'新頻道創建: {channel.name} ({channel.id})')

    async def on_member_join(self, member):
        """新成員加入時的回調"""
        self.logger.info(f'新成員加入: {member.name}')

    async def on_member_remove(self, member):
        """成員離開時的回調"""
        self.logger.info(f'成員離開: {member.name}')

    async def fetch_history(self, channel_id, limit=None):
        """獲取頻道歷史訊息"""
        channel = self.get_channel(channel_id)
        if not channel:
            try:
                channel = await self.fetch_channel(channel_id)
            except discord.NotFound:
                self.logger.error(f'找不到頻道: {channel_id}')
                return
            except discord.Forbidden:
                self.logger.error(f'沒有權限訪問頻道: {channel_id}')
                return

        self.logger.info(f'正在獲取頻道 {channel.name} 的歷史訊息...')

        messages_fetched = 0
        async for message in channel.history(limit=limit):
            if self.data_handler:
                await self.data_handler.save_message(message)
            messages_fetched += 1

        self.logger.info(f'已獲取 {messages_fetched} 條歷史訊息')

    async def fetch_all_channels_history(self, limit_per_channel=None):
        """獲取所有監控頻道的歷史訊息"""
        for channel_id in self.channel_ids:
            try:
                await self.fetch_history(channel_id, limit_per_channel)
            except Exception as e:
                self.logger.error(f'獲取頻道 {channel_id} 歷史失敗: {e}')

    def run_with_token(self, token):
        """使用指定 Token 啟動 Bot"""
        self.logger.info('正在啟動 Discord Bot...')
        try:
            super().run(token, reconnect=True)
        except discord.LoginFailure:
            self.logger.error('登入失敗：Token 無效！')
            raise
        except Exception as e:
            self.logger.error(f'啟動失敗: {e}')
            raise
