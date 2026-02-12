#!/usr/bin/env python3
"""
Discord 私人頻道內容提取器 - 主程式入口

此程式結合了 Discord Bot 和 Flask 網頁伺服器：
- Discord Bot 負責監控並提取私人頻道的訊息
- Flask 伺服器負責提供網頁介面供查看和下載訊息

使用方法：
    python main.py [--bot-only] [--web-only] [--fetch-history]
"""

import argparse
import asyncio
import logging
import sys
import os
import threading
from datetime import datetime

# 添加專案根目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import DISCORD_BOT_TOKEN, CHANNEL_IDS, WEB_HOST, WEB_PORT
from bot.data_handler import DataHandler
from bot.discord_bot import DiscordExtractorBot
from web.app import app

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_flask():
    """在獨立執行緒中運行 Flask 伺服器"""
    logger.info(f'啟動 Flask 網頁伺服器於 http://{WEB_HOST}:{WEB_PORT}')
    try:
        app.run(host=WEB_HOST, port=WEB_PORT, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f'Flask 伺服器錯誤: {e}')


async def run_bot_with_history(bot, fetch_history_flag):
    """運行 Discord Bot，可選擇是否獲取歷史訊息"""
    try:
        # 如果需要獲取歷史訊息
        if fetch_history_flag:
            logger.info('開始獲取頻道歷史訊息...')
            await bot.fetch_all_channels_history(limit_per_channel=None)
            logger.info('歷史訊息獲取完成')

        # 啟動 Bot
        await bot.start(DISCORD_BOT_TOKEN)
    except KeyboardInterrupt:
        logger.info('收到中斷訊號，正在關閉...')
    except Exception as e:
        logger.error(f'Bot 運行錯誤: {e}')
        raise


def main():
    """主函數"""
    parser = argparse.ArgumentParser(
        description='Discord 私人頻道內容提取器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
    python main.py                    # 同時啟動 Bot 和網頁伺服器
    python main.py --bot-only         # 只啟動 Discord Bot
    python main.py --web-only         # 只啟動網頁伺服器
    python main.py --fetch-history    # 啟動並獲取歷史訊息
        """
    )
    parser.add_argument(
        '--bot-only',
        action='store_true',
        help='只啟動 Discord Bot，不啟動網頁伺服器'
    )
    parser.add_argument(
        '--web-only',
        action='store_true',
        help='只啟動網頁伺服器，不啟動 Discord Bot'
    )
    parser.add_argument(
        '--fetch-history',
        action='store_true',
        help='啟動時獲取頻道的歷史訊息'
    )
    parser.add_argument(
        '--history-limit',
        type=int,
        default=None,
        help='獲取歷史訊息的數量限制（預設：無限制）'
    )

    args = parser.parse_args()

    # 檢查 Token
    if not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        logger.error('錯誤：未設置 Discord Bot Token！')
        logger.error('請在 config/settings.py 中設置 DISCORD_BOT_TOKEN')
        sys.exit(1)

    # 檢查頻道 ID
    if not CHANNEL_IDS or CHANNEL_IDS == [123456789012345678, 987654321098765432]:
        logger.warning('警告：未設置監控頻道 ID！')
        logger.warning('請在 config/settings.py 中設置 CHANNEL_IDS')

    # 初始化數據處理器
    logger.info('初始化數據處理器...')
    data_handler = DataHandler()

    # 初始化 Discord Bot
    logger.info('初始化 Discord Bot...')
    bot = DiscordExtractorBot(channel_ids=CHANNEL_IDS, data_handler=data_handler)

    if args.bot_only:
        # 只啟動 Bot
        logger.info('模式：只啟動 Discord Bot')
        asyncio.run(run_bot_with_history(bot, args.fetch_history))
    elif args.web_only:
        # 只啟動網頁伺服器
        logger.info('模式：只啟動網頁伺服器')
        logger.info(f'請訪問 http://localhost:{WEB_PORT} 查看訊息')
        run_flask()
    else:
        # 同時啟動 Bot 和網頁伺服器
        logger.info('模式：同時啟動 Discord Bot 和網頁伺服器')

        # 在背景執行緒中啟動 Flask
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logger.info(f'Flask 伺服器已啟動，請訪問 http://localhost:{WEB_PORT}')

        # 運行 Discord Bot
        asyncio.run(run_bot_with_history(bot, args.fetch_history))


if __name__ == '__main__':
    main()
