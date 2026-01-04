@echo off
chcp 65001 >nul
REM 查看监控日志文件（UTF-8 编码）
cd /d "%~dp0"
if exist logs\db_watcher.log (
    echo ========================================
    echo 监控日志（最新 20 行）
    echo ========================================
    powershell -Command "Get-Content logs\db_watcher.log -Tail 20 -Encoding UTF8"
    echo ========================================
) else (
    echo 日志文件不存在: logs\db_watcher.log
)
pause

