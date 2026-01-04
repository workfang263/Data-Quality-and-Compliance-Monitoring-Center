@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo 启动新系统（Vue + FastAPI）
echo ========================================
echo.

echo [1/2] 启动后端 API...
start "后端API" cmd /k "cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul

echo [2/2] 启动前端...
start "前端" cmd /k "cd frontend && npm run dev"

echo.
echo ========================================
echo 启动完成！
echo ========================================
echo.
echo 后端API: http://localhost:8000
echo API文档: http://localhost:8000/docs
echo 前端页面: http://localhost:5173
echo.
echo 按任意键关闭此窗口（服务将继续运行）...
pause >nul


