# Store-ops backfill script (last N days, default 7 days including today)
# - Default: both shops, all employees
# - Employee mode: pass -EmployeeSlug quqi (sync only that employee)

param(
    [string] $BaseUrl = "http://127.0.0.1:8000",
    [string] $InternalKey = $env:STORE_OPS_SYNC_SECRET,
    [int] $Days = 7,
    [string] $EndDate = "",
    [string[]] $ShopDomains = @("shutiaoes.myshoplaza.com", "newgges.myshoplaza.com"),
    [string] $EmployeeSlug = "",
    [int] $PollIntervalSec = 3,
    [int] $TimeoutSec = 900
)

$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if (-not $InternalKey) {
    Write-Error "Missing STORE_OPS_SYNC_SECRET. Set env var or pass -InternalKey."
    exit 1
}
if ($Days -le 0) {
    Write-Error "-Days must be > 0"
    exit 1
}
if ($PollIntervalSec -le 0) {
    Write-Error "-PollIntervalSec must be > 0"
    exit 1
}
if ($TimeoutSec -le 0) {
    Write-Error "-TimeoutSec must be > 0"
    exit 1
}

try {
    if ($EndDate) {
        $end = [DateTime]::ParseExact($EndDate, "yyyy-MM-dd", $null).Date
    } else {
        $end = (Get-Date).Date
    }
} catch {
    Write-Error "Invalid EndDate format. Use YYYY-MM-DD."
    exit 1
}

$start = $end.AddDays(-($Days - 1))
$bizDates = @()
for ($d = $start; $d -le $end; $d = $d.AddDays(1)) {
    $bizDates += $d.ToString("yyyy-MM-dd")
}

$payload = @{
    biz_dates = $bizDates
    shop_domains = $ShopDomains
}
if ($EmployeeSlug) {
    $payload.employee_slugs = @($EmployeeSlug.ToLower())
}

$uri = "$BaseUrl/api/internal/store-ops/sync"
$headers = @{
    "X-Internal-Key" = $InternalKey
    "Content-Type" = "application/json"
}

Write-Host "========== STORE OPS BACKFILL =========="
Write-Host "BaseUrl: $BaseUrl"
Write-Host "Date range: $($start.ToString('yyyy-MM-dd')) ~ $($end.ToString('yyyy-MM-dd')) ($Days days)"
Write-Host "Shops: $($ShopDomains -join ', ')"
if ($EmployeeSlug) {
    Write-Host "Employee mode: $($EmployeeSlug.ToLower())"
} else {
    Write-Host "Employee mode: ALL"
}

try {
    $response = Invoke-RestMethod -Uri $uri -Method Post -Headers $headers -Body ($payload | ConvertTo-Json -Depth 6) -TimeoutSec 120
} catch {
    Write-Error ("Failed to trigger sync: {0}" -f $_)
    exit 1
}

$syncRunId = $response.data.sync_run_id
if (-not $syncRunId) {
    Write-Error ("sync_run_id missing in response: {0}" -f ($response | ConvertTo-Json -Depth 6 -Compress))
    exit 1
}
Write-Host ("Accepted: sync_run_id={0}" -f $syncRunId)

$runUri = "$BaseUrl/api/internal/store-ops/sync-run/$syncRunId"
$deadline = (Get-Date).AddSeconds($TimeoutSec)
$lastStatus = ""

while ($true) {
    if ((Get-Date) -gt $deadline) {
        Write-Error ("Timeout (>{0}s). Check manually: {1}" -f $TimeoutSec, $runUri)
        exit 1
    }
    try {
        $runRes = Invoke-RestMethod -Uri $runUri -Method Get -Headers $headers -TimeoutSec 60
    } catch {
        Write-Warning ("Status query failed, retrying: {0}" -f $_)
        Start-Sleep -Seconds $PollIntervalSec
        continue
    }
    $status = [string]$runRes.data.status
    if ($status -ne $lastStatus) {
        Write-Host ("Status: {0}" -f $status)
        $lastStatus = $status
    }
    if ($status -eq "success" -or $status -eq "partial" -or $status -eq "failed") {
        Write-Host ""
        Write-Host "========== RESULT =========="
        Write-Host ("status: {0}" -f $status)
        Write-Host ("orders_seen: {0}" -f $runRes.data.orders_seen)
        Write-Host ("orders_upserted_paid: {0}" -f $runRes.data.orders_upserted_paid)
        Write-Host ("orders_skipped_not_paid: {0}" -f $runRes.data.orders_skipped_not_paid)
        Write-Host ("error_count: {0}" -f $runRes.data.error_count)
        if ($status -eq "failed") {
            exit 1
        }
        exit 0
    }
    Start-Sleep -Seconds $PollIntervalSec
}
