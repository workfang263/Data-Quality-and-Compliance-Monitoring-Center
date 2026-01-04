@echo off
chcp 65001 >nul 2>&1
echo 启动 Shoplazza 数据看板...
echo.

REM 检查端口是否被占用
python -c "from check_port import is_port_in_use, find_available_port; port=8502; import sys; sys.stdout.reconfigure(encoding='utf-8'); in_use=is_port_in_use(port); print(f'检查端口 {port}...'); print('端口已被占用' if in_use else '端口可用'); sys.exit(1 if in_use else 0)" 2>nul
if %errorlevel% equ 1 (
    echo [警告] 端口 8502 已被占用！
    echo.
    echo 正在查找可用端口...
    python -c "from check_port import find_available_port; import sys; sys.stdout.reconfigure(encoding='utf-8'); port=find_available_port(8502); print(f'建议使用端口: {port}' if port else '未找到可用端口')" 2>nul
    echo.
    echo 请修改配置文件 config.py 中的端口号，或关闭占用 8502 端口的程序
    echo.
    pause
    exit /b 1
)

echo 端口检查通过
echo.
echo 访问地址: http://localhost:8502
echo 或局域网访问: http://你的IP地址:8502
echo.
streamlit run dashboard.py --server.port 8502 --server.address 0.0.0.0
pause


