# Windows 任务计划程序自动配置脚本
# 功能：自动创建"数据同步监控"定时任务

# 检查是否以管理员权限运行
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "❌ 请以管理员权限运行此脚本！" -ForegroundColor Red
    Write-Host "右键点击 PowerShell，选择'以管理员身份运行'" -ForegroundColor Yellow
    pause
    exit
}

# 项目路径
$projectPath = "D:\projects\line chart"
$batFile = Join-Path $projectPath "run_db_watcher.bat"
$pythonExe = "C:\Users\EDY\AppData\Local\Programs\Python\Python311\python.exe"

# 检查文件是否存在
if (-not (Test-Path $batFile)) {
    Write-Host "❌ 找不到批处理文件: $batFile" -ForegroundColor Red
    pause
    exit
}

# 任务名称
$taskName = "数据同步监控"

# 检查任务是否已存在
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if ($existingTask) {
    Write-Host "⚠️  任务 '$taskName' 已存在" -ForegroundColor Yellow
    $response = Read-Host "是否删除并重新创建？(Y/N)"
    if ($response -eq "Y" -or $response -eq "y") {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host "✅ 已删除旧任务" -ForegroundColor Green
    } else {
        Write-Host "取消操作" -ForegroundColor Yellow
        pause
        exit
    }
}

# 创建任务操作（执行批处理文件）
$action = New-ScheduledTaskAction -Execute $batFile -WorkingDirectory $projectPath

# 创建触发器（每5分钟执行一次）
$trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 365) -Once -At (Get-Date)

# 创建任务设置
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

# 创建任务主体（使用最高权限，不管用户是否登录）
$principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

# 注册任务
try {
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description "监控数据同步脚本运行状态，每5分钟检查一次，超过20分钟未更新则发送钉钉告警" `
        -Force

    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Green
    Write-Host "✅ 任务创建成功！" -ForegroundColor Green
    Write-Host "=" * 80 -ForegroundColor Green
    Write-Host ""
    Write-Host "任务名称: $taskName" -ForegroundColor Cyan
    Write-Host "执行文件: $batFile" -ForegroundColor Cyan
    Write-Host "执行频率: 每 5 分钟执行一次" -ForegroundColor Cyan
    Write-Host "运行权限: SYSTEM（最高权限）" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "查看任务: 运行 taskschd.msc" -ForegroundColor Yellow
    Write-Host "测试任务: 在任务计划程序中右键任务 -> 运行" -ForegroundColor Yellow
    Write-Host ""
} catch {
    Write-Host "❌ 任务创建失败: $_" -ForegroundColor Red
    pause
    exit
}

pause

