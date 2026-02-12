"""
Discord 私人頻道內容提取器 - 配置文件
"""

import os

# Discord Bot 配置
DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

# Discord 用戶 Token（個人帳號版本）
# ⚠️ 風險警告：使用個人 Token 可能違反 Discord ToS
# ⚠️ 重要：請勿直接輸入 Token，使用環境變數 DISCORD_USER_TOKEN
USER_TOKEN = os.environ.get('DISCORD_USER_TOKEN', '')

# 要監控的頻道 ID 列表
# 請將以下替換為你要監控的頻道 ID
# 注意：頻道 ID 必須是整數類型
CHANNEL_IDS = [
    1458011589624987699,  # jpm
    1459878042955677869,  # oculus
    1454140095442583715,  # tuk
]

# 頻道 ID 獲取方法：
# 1. 在 Discord 中開啟「開發者模式」
#    - Discord 設定 > 進階 > 開啟「開發者模式」
# 2. 右鍵點擊頻道 > 「複製 ID」

# 網頁伺服器配置
WEB_HOST = os.environ.get('WEB_HOST', '0.0.0.0')
WEB_PORT = int(os.environ.get('WEB_PORT', 5000))
WEB_DEBUG = os.environ.get('WEB_DEBUG', False)

# 數據儲存配置
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
CSV_FILE = os.path.join(DATA_DIR, 'channels.csv')

# 媒體下載配置
MEDIA_DIR = os.path.join(DATA_DIR, 'media')
DOWNLOAD_ATTACHMENTS = True
MAX_ATTACHMENT_SIZE_MB = 50  # 最大附件大小限制

# 日志配置
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
