@echo off
chcp 65001 >nul
echo ====================================
echo   Git 仓库初始化脚本
echo ====================================
echo.

:: 检查是否已安装 Git
git --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Git，请先安装 Git
    echo.
    echo 下载地址：https://git-scm.com/download/win
    echo 或访问：https://gitee.com/mirrors/git-for-windows （国内镜像）
    echo.
    pause
    exit /b 1
)

echo [1/4] 检查 Git 配置...
git config user.name >nul 2>&1
if errorlevel 1 (
    echo [提示] 首次使用 Git，需要配置用户信息
    set /p USER_NAME="请输入您的名字: "
    set /p USER_EMAIL="请输入您的邮箱: "
    git config --global user.name "%USER_NAME%"
    git config --global user.email "%USER_EMAIL%"
    echo [成功] Git 用户信息已配置
) else (
    echo [成功] Git 已配置
    git config user.name
    git config user.email
)
echo.

echo [2/4] 检查是否已初始化 Git 仓库...
if exist .git (
    echo [提示] Git 仓库已存在
) else (
    echo [执行] 初始化 Git 仓库...
    git init
    echo [成功] Git 仓库初始化完成
)
echo.

echo [3/4] 检查 .gitignore 文件...
if exist .gitignore (
    echo [成功] .gitignore 文件已存在
) else (
    echo [警告] .gitignore 文件不存在，建议创建
)
echo.

echo [4/4] 查看当前状态...
git status
echo.

echo ====================================
echo   下一步操作建议：
echo ====================================
echo.
echo 1. 添加所有文件到暂存区：
echo    git add .
echo.
echo 2. 提交更改：
echo    git commit -m "初始提交：备份项目代码"
echo.
echo 3. （可选）连接到远程仓库（GitHub/Gitee）：
echo    git remote add origin 您的仓库地址
echo    git push -u origin main
echo.
echo ====================================
echo.
pause




