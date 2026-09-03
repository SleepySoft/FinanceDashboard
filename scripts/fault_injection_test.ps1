# 故障注入测试：损坏各类数据文件后，验证单个坏文件不会拖垮接口。
# 所有目标在测试前备份，测试结束后自动恢复（原本不存在的文件会删除）。
$ErrorActionPreference = "Stop"
$base = if ($env:FD_TEST_BASE_URL) { $env:FD_TEST_BASE_URL } else { "http://127.0.0.1:8010" }
$root = Split-Path $PSScriptRoot -Parent
$data = Join-Path $root "data"
$bak = Join-Path $env:TEMP ("fd_fault_test_" + [guid]::NewGuid().ToString("N"))
$headers = @{}
$tokenFile = Join-Path $root "agent_token.txt"
if (Test-Path $tokenFile) {
  $headers["X-API-Key"] = (Get-Content $tokenFile -Raw).Trim()
}

New-Item $bak -ItemType Directory | Out-Null
$backups = @{}
$failures = 0

function Backup-Target($path) {
  $index = $backups.Count
  if (Test-Path $path) {
    $copy = Join-Path $bak "$index.bak"
    Copy-Item $path $copy
    $backups[$path] = $copy
  } else {
    $backups[$path] = $null
  }
}

function Check($name, $url, $expectContains) {
  try {
    $response = Invoke-WebRequest -Uri "$base$url" -Headers $headers -UseBasicParsing -TimeoutSec 30
    $contains = !$expectContains -or $response.Content.Contains($expectContains)
    $ok = $response.StatusCode -eq 200 -and $contains
    if (!$ok) { $script:failures++ }
    $mark = if ($ok) { "PASS" } else { "FAIL" }
    "$mark $name -> $($response.StatusCode) contains[$expectContains]=$contains"
  } catch {
    $script:failures++
    "FAIL $name -> $($_.Exception.Message)"
  }
}

$dashboard = Join-Path $data "_dashboard.json"
$tasks = Join-Path $data "_tasks.json"
$anomalies = Join-Path $data "_anomalies.json"
$providers = Join-Path $data "_providers.json"
$records = Join-Path $data "_backtest_records.json"
$stockDir = Join-Path $data "000001.SZ"
$meta = Join-Path $stockDir "meta.json"
$briefs = Join-Path $stockDir "briefs.json"
$notes = Join-Path $stockDir "notes.md"
$holdings = Join-Path $stockDir "holdings.json"
$badReport1 = Join-Path $stockDir "reports\fundamental_extra_2026.md"
$badReport2 = Join-Path $stockDir "reports\nounderscore.md"
$targets = @($dashboard, $tasks, $anomalies, $providers, $records, $meta, $briefs, $notes, $holdings)
foreach ($target in $targets) { Backup-Target $target }

try {
  "== 基线 =="
  Check "dashboard" "/api/dashboard" "000001.SZ"
  Check "requests" "/api/requests" $null
  Check "anomalies" "/api/anomalies/latest" $null
  Check "providers" "/api/providers" "providers"
  Check "backtest-records" "/api/backtest/records" "records"

  "== 非法或错误类型 JSON =="
  [IO.File]::WriteAllText($dashboard, '{"prices":{"BAD":"not-an-object"}}')
  Check "dashboard/bad-price-entry" "/api/dashboard" "000001.SZ"

  [IO.File]::WriteAllText($tasks, '[7,null,{"id":"safe","status":"pending"}]')
  Check "requests/bad-elements" "/api/requests" "safe"

  [IO.File]::WriteAllText($meta, '{bad json,,')
  Check "dashboard/bad-meta" "/api/dashboard" "000333.SZ"
  Check "stock-detail/bad-meta" "/api/stocks/000001.SZ" "000001.SZ"

  [IO.File]::WriteAllText($briefs, '[42,null,{"id":"valid","date":"2026-01-01"}]')
  Check "briefs/bad-elements" "/api/stocks/000001.SZ/briefs" "valid"

  [IO.File]::WriteAllText($holdings, '{"trades":"bad","t_trades":{},"adj_events":null,"summary":[]}')
  Check "holdings/bad-fields" "/api/holdings/000001.SZ" "has_data"

  [IO.File]::WriteAllText($anomalies, '{broken')
  Check "anomalies/bad-json" "/api/anomalies/latest" "stocks"

  [IO.File]::WriteAllText($providers, '[1,2,3]')
  Check "providers/bad-root" "/api/providers" "eastmoney"

  [IO.File]::WriteAllText($records, '[null,7,{"id":"valid-record","created_at":"2026-01-01"}]')
  Check "backtest-records/bad-elements" "/api/backtest/records" "valid-record"

  "== 非 UTF-8 文本与异常报告名 =="
  [IO.File]::WriteAllBytes($notes, [byte[]](0x23, 0x23, 0x20, 0xFF, 0xFE, 0x0A, 0xFF))
  Check "notes/bad-encoding" "/api/stocks/000001.SZ/notes" "notes"

  [IO.File]::WriteAllText($badReport1, "# bad report")
  [IO.File]::WriteAllText($badReport2, "# no underscore")
  Check "stock-detail/bad-report-name" "/api/stocks/000001.SZ" "fundamental_extra_2026"
  Check "report-get/bad-report-name" "/api/stocks/000001.SZ/reports/fundamental_extra_2026" "bad report"
} finally {
  "== 恢复原文件 =="
  foreach ($target in $targets) {
    $copy = $backups[$target]
    if ($null -ne $copy) {
      Copy-Item $copy $target -Force
    } else {
      Remove-Item $target -Force -ErrorAction SilentlyContinue
    }
  }
  Remove-Item $badReport1, $badReport2 -Force -ErrorAction SilentlyContinue
  Remove-Item $bak -Recurse -Force -ErrorAction SilentlyContinue
  "restored"
}

if ($failures -gt 0) {
  throw "$failures fault-injection checks failed"
}
"All fault-injection checks passed"
