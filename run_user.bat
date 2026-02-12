@echo off
chcp 65001 >nul
echo ============================================
echo   Discord 私人頻道內容提取器 - 用戶版
echo ============================================
echo.
cd /d "%~dp0"
python user_main.py
pause
