# 店铺运营：定时触发同步（供 Windows 任务计划程序调用）
# 密钥：用户环境变量 STORE_OPS_SYNC_SECRET，或参数 -InternalKey "..."
# 手动测试：$env:STORE_OPS_SYNC_SECRET="密钥"; powershell -NoProfile -ExecutionPolicy Bypass -File "...\store_ops_sync_hourly.ps1"

param(
    [string] $BaseUrl = "http://127.0.0.1:8000",
    [string] $InternalKey = $env:STORE_OPS_SYNC_SECRET
)

# param() 必须是首个可执行语句；UTF-8 输出放在 param 之后
$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if (-not $InternalKey) {
    Write-Error "请设置环境变量 STORE_OPS_SYNC_SECRET，或在脚本中传入 -InternalKey"
    exit 1
}

$uri = "$BaseUrl/api/internal/store-ops/sync"
try {
    $response = Invoke-RestMethod -Uri $uri -Method Post -Headers @{
        "X-Internal-Key" = $InternalKey
        "Content-Type"     = "application/json"
    } -Body "{}" -TimeoutSec 120
    Write-Host "OK:" ($response | ConvertTo-Json -Compress)
    exit 0
} catch {
    Write-Error $_
    exit 1
}
