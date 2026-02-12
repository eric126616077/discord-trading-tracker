# Discord 交易追蹤器 - Render 部署指南

## 1. 上傳到 GitHub

### 建立 GitHub 專案
```powershell
cd discord-extractor

# 初始化 Git
git init
git add .
git commit -m "Prepare for Render deployment"

# 建立 GitHub 專案
# 1. 去 https://github.com/new
# 2. 專案名稱: discord-trading-tracker
# 3. 建立後複製 SSH/HTTPS URL

# 推送
git remote add origin https://github.com/你的帳號/discord-trading-tracker.git
git branch -M main
git push -u origin main
```

## 2. Render 部署步驟

### 建立 Render 帳號
1. 去 https://render.com
2. 用 GitHub 帳號登入

### 建立 Web Service
1. Dashboard → "New" → "Web Service"
2. "Connect your GitHub repository"
3. 選擇 `discord-trading-tracker`
4. 設定：
   - Name: `discord-trading-tracker`
   - Root Directory: `discord-extractor`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python user_main.py`
5. "Create Web Service"

### 設定環境變數 (重要!)
在 Render dashboard → 你的 service → "Environment"：
```
PORT = 10000  # Render 會自動設定
DISCORD_BOT_TOKEN = (可选 Bot Token)
```

### 重要設定
在 "Advanced" 中勾選：
- ✅ "Use a persistent disk" (可選，保存數據)

## 3. 訪問網站

部署完成後，Render 會提供 URL，例如：
```
https://discord-trading-trader.onrender.com/trading
```

## 4. 問題解決

### 網頁空白
- 去 "Logs" 查看錯誤
- 確保 requirements.txt 正確

### Discord 連接問題
- 用戶 Token 在伺服器上可能不穩定
- 建議使用 Bot Token

### 數據丟失
- Render 免費版的文件系統是臨時的
- 重啟後數據會丟失
- 需要數據持久化請付費或使用資料庫

## 5. 更新部署

修改程式碼後：
```powershell
git add .
git commit -m "Update"
git push
```
Render 會自動重新部署。
