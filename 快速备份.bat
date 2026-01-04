@echo off
chcp 65001 >nul
echo ====================================
echo   快速备份脚本
echo ====================================
echo.

:: 检查是否已初始化 Git
if not exist .git (
    echo [错误] 未找到 Git 仓库，请先运行"初始化Git仓库.bat"
    pause
    exit /b 1
)

echo [1/3] 查看当前状态...
git status
echo.

echo [2/3] 添加所有文件到暂存区...
git add .
if errorlevel 1 (
    echo [错误] 添加文件失败
    pause
    exit /b 1
)
echo [成功] 文件已添加到暂存区
echo.

echo [3/3] 请输入提交说明（描述这次做了什么修改）：
set /p COMMIT_MSG="提交说明: "

if "%COMMIT_MSG%"=="" (
    set COMMIT_MSG=自动备份：%date% %time%
)

git commit -m "%COMMIT_MSG%"
if errorlevel 1 (
    echo [错误] 提交失败（可能没有需要提交的更改）
    pause
    exit /b 1
)
echo.
echo [成功] 代码已提交到本地仓库！
echo.

:: 检查是否配置了远程仓库
git remote -v >nul 2>&1
if errorlevel 1 (
    echo [提示] 未配置远程仓库
    echo [建议] 如需备份到云端，请先配置远程仓库：
    echo    git remote add origin 您的仓库地址
    echo    git push -u origin main
) else (
    echo [提示] 检测到远程仓库，是否推送到远程？
    set /p PUSH="输入 y 推送到远程，其他键跳过: "
    if /i "%PUSH%"=="y" (
        echo [执行] 推送到远程仓库...
        git push
        if errorlevel 1 (
            echo [错误] 推送失败，请检查网络连接和远程仓库配置
        ) else (
            echo [成功] 代码已推送到远程仓库！
        )
    )
)

echo.
echo ====================================
echo   备份完成！
echo ====================================
echo.
pause




