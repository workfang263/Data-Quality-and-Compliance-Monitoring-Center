@echo off
chcp 65001 >nul
REM 数据库监控脚本 - 检查数据同步状态
cd /d "%~dp0"
REM 优先使用完整路径，如果不存在则使用 PATH 中的 python
if exist "C:\Users\EDY\AppData\Local\Programs\Python\Python311\python.exe" (
    "C:\Users\EDY\AppData\Local\Programs\Python\Python311\python.exe" tests\db_watcher.py >> logs\db_watcher.log 2>&1
) else (
    python tests\db_watcher.py >> logs\db_watcher.log 2>&1
)

