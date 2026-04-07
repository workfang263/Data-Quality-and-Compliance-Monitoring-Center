# 店铺运营：每小时触发一次同步（示例，与 store_ops_sync_hourly.ps1 逻辑一致）
# 正式任务请用：scripts/store_ops_sync_hourly.ps1（见 启动脚本/启动命令说明.md）

param(
    [string] $BaseUrl = "http://127.0.0.1:8000",
    [string] $InternalKey = $env:STORE_OPS_SYNC_SECRET
)

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
