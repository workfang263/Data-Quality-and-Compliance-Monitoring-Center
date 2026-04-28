@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Set proxy environment variables (Python script will also set them, but set here as backup)
set HTTP_PROXY=socks5h://127.0.0.1:10808
set HTTPS_PROXY=socks5h://127.0.0.1:10808
REM Sync today's campaign-level spend incrementally (REPLACE INTO, no cleanup)
if exist "C:\Users\EDY\AppData\Local\Programs\Python\Python311\python.exe" (
    "C:\Users\EDY\AppData\Local\Programs\Python\Python311\python.exe" fb_campaign_spend_sync.py --incremental
) else (
    python fb_campaign_spend_sync.py --incremental
)
