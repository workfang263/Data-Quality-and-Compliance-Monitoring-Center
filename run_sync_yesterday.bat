@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Shoplazza 直连，不设代理
set HTTP_PROXY=
set HTTPS_PROXY=
REM 同步昨天的 Shoplazza 数据（data_sync.py 无参数时默认同步昨天）
if exist "C:\Users\EDY\AppData\Local\Programs\Python\Python311\python.exe" (
    "C:\Users\EDY\AppData\Local\Programs\Python\Python311\python.exe" data_sync.py
) else (
    python data_sync.py
)
