@echo off
cd /d "%~dp0"
REM 优先使用完整路径，如果不存在则使用 PATH 中的 python
if exist "C:\Users\EDY\AppData\Local\Programs\Python\Python311\python.exe" (
    "C:\Users\EDY\AppData\Local\Programs\Python\Python311\python.exe" data_sync.py --realtime
) else (
    python data_sync.py --realtime
)


