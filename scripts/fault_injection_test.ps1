# 故障注入测试：损坏各类数据文件后，验证接口仍返回 200（坏文件不拖垮整个程序）
# 测试结束自动恢复原文件
$ErrorActionPreference = "Continue"
$base = "http://127.0.0.1:8010"
$data = "C:\D\code\FinanceDashboard\data"
$bak = "$env:TEMP\fd_fault_test_bak"
Remove-Item $bak -Recurse -Force -ErrorAction SilentlyContinue
New-Item $bak -ItemType Directory | Out-Null

$targets = @(
  "$data\_dashboard.json",
  "$data\_tasks.json",
  "$data\000001.SZ\meta.json",
  "$data\002138.SZ\holdings.json"
)
foreach ($t in $targets) { Copy-Item $t "$bak\$(($t -replace '[\\:]','_'))" }

function Check($name, $url, $expectContains) {
  try {
    $r = Invoke-WebRequest -Uri "$base$url" -UseBasicParsing -TimeoutSec 30
    $ok = $r.StatusCode -eq 200
    $extra = ""
    if ($expectContains) { $extra = " contains[$expectContains]=$($r.Content.Contains($expectContains))" }
    $mark = "FAIL"; if ($ok) { $mark = "PASS" }
    "{0} {1} -> {2}{3}" -f $mark, $name, $r.StatusCode, $extra
  } catch {
    "FAIL $name -> $($_.Exception.Response.StatusCode.value__) $($_.Exception.Message)"
  }
}

try {
  "== 基线（正常数据） =="
  Check "dashboard" "/api/dashboard" "000001.SZ"
  Check "stocks" "/api/stocks" "002138.SZ"
  Check "holdings" "/api/holdings" $null
  Check "requests" "/api/requests" $null
  Check "stock-detail" "/api/stocks/000001.SZ" $null

  "== 注入1: _dashboard.json 半截损坏 =="
  Set-Content "$data\_dashboard.json" '{"prices": {"000001.SZ": {"price": 12.' -NoNewline
  Check "dashboard" "/api/dashboard" "002138.SZ"
  Check "stocks" "/api/stocks" "002138.SZ"
  Check "stock-detail" "/api/stocks/002138.SZ" $null

  "== 注入2: _tasks.json 非法 JSON =="
  Set-Content "$data\_tasks.json" 'not json at all {' -NoNewline
  Check "requests" "/api/requests" $null

  "== 注入3: 单股 meta.json 损坏 =="
  Set-Content "$data\000001.SZ\meta.json" '{bad json,,' -NoNewline
  Check "dashboard" "/api/dashboard" "002138.SZ"
  Check "stocks" "/api/stocks" "002138.SZ"
  Check "stock-detail(坏meta)" "/api/stocks/000001.SZ" $null

  "== 注入4: 单股 holdings.json 损坏 =="
  Set-Content "$data\002138.SZ\holdings.json" '[1,2,' -NoNewline
  Check "holdings" "/api/holdings" $null
  Check "holdings-detail(坏)" "/api/holdings/002138.SZ" $null

  "== 注入5: 报告文件名异常 =="
  Set-Content "$data\000001.SZ\reports\fundamental_extra_2026.md" "# bad report"
  Set-Content "$data\000001.SZ\reports\nounderscore.md" "# no underscore"
  Check "stock-detail(坏报告名)" "/api/stocks/000001.SZ" "fundamental_extra_2026"
  Check "report-get(坏报告名)" "/api/stocks/000001.SZ/reports/fundamental_extra_2026" $null
} finally {
  "== 恢复原文件 =="
  foreach ($t in $targets) { Copy-Item "$bak\$(($t -replace '[\\:]','_'))" $t -Force }
  Remove-Item "$data\000001.SZ\reports\fundamental_extra_2026.md" -Force -ErrorAction SilentlyContinue
  Remove-Item "$data\000001.SZ\reports\nounderscore.md" -Force -ErrorAction SilentlyContinue
  Remove-Item $bak -Recurse -Force -ErrorAction SilentlyContinue
  "restored"
}
