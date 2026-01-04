@echo off
cd /d "%~dp0"
set HTTP_PROXY=socks5h://127.0.0.1:10808
set HTTPS_PROXY=socks5h://127.0.0.1:10808
REM 优先使用完整路径，如果不存在则使用 PATH 中的 python
if exist "C:\Users\EDY\AppData\Local\Programs\Python\Python311\python.exe" (
    "C:\Users\EDY\AppData\Local\Programs\Python\Python311\python.exe" sync_yesterday_fb_spend.py
) else (
    python sync_yesterday_fb_spend.py
)




