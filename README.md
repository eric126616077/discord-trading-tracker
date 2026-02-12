# Discord 私人頻道內容提取器

一個用於提取 Discord 私人頻道內容的網頁應用程式，配備現代化的網頁介面。

## 功能特點

- 實時監控 Discord 私人頻道的新訊息
- 提取文字、圖片、檔案等所有媒體內容
- 自動下載附件到本地
- 支援搜尋和篩選訊息
- 匯出 CSV 和 JSON 格式
- 現代化深色主題網頁介面
- 自動重新整理最新內容

## 專案架構

```
discord-extractor/
├── bot/
│   ├── __init__.py
│   ├── discord_bot.py      # Discord Bot 核心邏輯
│   └── data_handler.py      # 數據處理與 CSV 儲存
├── web/
│   ├── app.py               # Flask 網頁伺服器
│   ├── templates/
│   │   ├── index.html       # 主頁面（訊息列表）
│   │   └── channel.html     # 頻道詳情頁面
│   └── static/
│       ├── style.css        # 樣式表
│       └── script.js        # 前端 JavaScript
├── data/
│   └── channels.csv         # 頻道數據儲存
├── config/
│   └── settings.py          # 配置文件
├── requirements.txt         # Python 依賴套件
├── main.py                  # 主程式入口
└── README.md                # 說明文件
```

## 安裝步驟

### 1. 安裝 Python 依賴

```bash
pip install -r requirements.txt
```

### 2. 配置 Discord Bot

#### 創建 Discord Bot

1. 前往 [Discord Developer Portal](https://discord.com/developers/applications)
2. 點擊 "New Application"，輸入名稱
3. 在 "Bot" 頁面點擊 "Add Bot"
4. 複製 Bot Token

#### 啟用權限

1. 在 "Privileged Gateway Intents" 中啟用：
   - Message Content Intent（必需）
   - Guild Members（可選）
   - Guild Messages（可選）

2. 邀請 Bot 到伺服器：
   ```
   https://discord.com/api/oauth2/authorize?client_id=YOUR_BOT_ID&permissions=379968&scope=bot
   ```

#### 配置 Token 和頻道 ID

編輯 `config/settings.py`：

```python
# Discord Bot Token
DISCORD_BOT_TOKEN = "你的_Bot_Token"

# 要監控的頻道 ID 列表
CHANNEL_IDS = [
    123456789012345678,  # 替換為你的頻道 ID
    987654321098765432,  # 可以添加多個頻道
]
```

#### 獲取頻道 ID

1. 在 Discord 中開啟「開發者模式」
   - Discord 設定 > 進階 > 開啟「開發者模式」
2. 右鍵點擊頻道 > 「複製 ID」

## 使用方法

### 基礎用法

```bash
# 同時啟動 Discord Bot 和網頁伺服器
python main.py
```

### 進階選項

```bash
# 只啟動 Discord Bot
python main.py --bot-only

# 只啟動網頁伺服器（用於查看已提取的數據）
python main.py --web-only

# 啟動並獲取頻道歷史訊息
python main.py --fetch-history

# 限制歷史訊息數量
python main.py --fetch-history --history-limit 1000
```

### 訪問網頁介面

啟動後，在瀏覽器中訪問：

```
http://localhost:5000
```

## API 端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/` | GET | 首頁 |
| `/channel/<channel_id>` | GET | 頻道詳情頁 |
| `/api/statistics` | GET | 獲取統計資訊 |
| `/api/channels` | GET | 獲取頻道列表 |
| `/api/messages` | GET | 獲取所有訊息 |
| `/api/channel/<channel_id>/messages` | GET | 獲取指定頻道訊息 |
| `/api/export` | GET | 匯出 CSV |
| `/api/export/json` | GET | 匯出 JSON |
| `/api/health` | GET | 健康檢查 |

### API 參數

`/api/messages` 支援以下參數：

| 參數 | 類型 | 說明 |
|------|------|------|
| `channel_id` | string | 頻道 ID 篩選 |
| `author` | string | 作者名稱篩選 |
| `search` | string | 內容搜尋 |
| `limit` | int | 結果數量限制 |
| `offset` | int | 結果偏移量 |

## 數據儲存

### CSV 格式

| 欄位 | 說明 |
|------|------|
| channel_id | 頻道 ID |
| channel_name | 頻道名稱 |
| message_id | 訊息 ID |
| author | 作者名稱 |
| author_id | 作者 ID |
| content | 訊息內容 |
| timestamp | 發送時間 |
| attachments | 附件列表（JSON） |
| embeds_count | 嵌入數量 |
| type | 訊息類型 |
| jump_url | Discord 跳轉連結 |

### 媒體下載

所有附件會自動下載到 `data/media/<channel_id>/` 目錄。

## 注意事項

1. **權限要求**：Bot 必須要有讀取訊息的權限才能提取內容
2. **頻道權限**：確保 Bot 已被添加到目標私人頻道
3. **Rate Limits**：遵守 Discord 的 API 速率限制
4. **儲存空間**：大量下載附件會佔用儲存空間
5. **安全性**：不要分享 Bot Token 或將其上傳到公開倉庫

## 故障排除

### Bot 無法登入

- 檢查 Token 是否正確
- 確認已啟用 Message Content Intent
- 檢查網路連線

### 無法獲取頻道訊息

- 確認 Bot 已被添加到頻道
- 檢查頻道權限設定
- 確認頻道 ID 正確

### 網頁無法訪問

- 確認 Flask 伺服器正在運行
- 檢查防火牆設定
- 確認端口 5000 未被佔用

## 技術棧

- **後端框架**: Flask
- **Discord 函式庫**: discord.py
- **數據儲存**: CSV + 本地檔案
- **前端**: HTML5 + CSS3 + Vanilla JavaScript
- **HTTP 客戶端**: aiohttp + requests

## 授權

MIT License
