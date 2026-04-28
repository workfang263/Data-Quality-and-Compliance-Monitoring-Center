@echo off
chcp 65001 >nul
cd /d "%~dp0"
set HTTP_PROXY=socks5h://127.0.0.1:10808
set HTTPS_PROXY=socks5h://127.0.0.1:10808
REM Compute yesterday's date in local time (PowerShell), then pass as --date
for /f %%i in ('powershell -NoProfile -Command "(Get-Date).AddDays(-1).ToString('yyyy-MM-dd')"') do set YDAY=%%i
if exist "C:\Users\EDY\AppData\Local\Programs\Python\Python311\python.exe" (
    "C:\Users\EDY\AppData\Local\Programs\Python\Python311\python.exe" fb_campaign_spend_sync.py --date %YDAY%
) else (
    python fb_campaign_spend_sync.py --date %YDAY%
)
