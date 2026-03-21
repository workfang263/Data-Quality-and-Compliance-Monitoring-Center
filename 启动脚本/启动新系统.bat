@echo off
cd /d "%~dp0.."
start "后端 8000" cmd /k "cd /d "%~dp0..\backend" && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
start "前端 5173" cmd /k "cd /d "%~dp0..\frontend" && npm run dev -- --port 5173"
