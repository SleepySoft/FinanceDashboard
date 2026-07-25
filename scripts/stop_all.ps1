# FinanceDashboard - stop backend & frontend processes (Windows)
# Match rules:
#   Backend launcher : any process with "uvicorn main:app" in command line
#   Backend worker   : python multiprocessing-fork child of a launcher or of a dead parent
#   Frontend         : node/vite processes under the FinanceDashboard directory

$ErrorActionPreference = 'SilentlyContinue'
$script:stopped = 0

function Stop-One($proc, $why) {
    if ($null -eq $proc) { return }
    Write-Host ("  Stopping {0} (PID {1}) - {2}" -f $proc.Name, $proc.ProcessId, $why)
    Stop-Process -Id $proc.ProcessId -Force
    $script:stopped++
}

# ── Backend: uvicorn launchers ──
$launchers = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'uvicorn main:app' })
$launcherIds = @($launchers | ForEach-Object { $_.ProcessId })
$launchers | ForEach-Object { Stop-One $_ 'backend (uvicorn main:app)' }

# ── Backend: multiprocessing-fork workers (spawned by --reload) ──
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match 'python' -and $_.CommandLine -match 'multiprocessing-fork' -and $_.CommandLine -match 'parent_pid=(\d+)'
} | ForEach-Object {
    $parentId = [int]$Matches[1]
    $parentAlive = $null -ne (Get-Process -Id $parentId -ErrorAction SilentlyContinue)
    if (($launcherIds -contains $parentId) -or (-not $parentAlive)) {
        Stop-One $_ "backend worker (parent_pid=$parentId)"
    }
}

# ── Frontend: vite under this project ──
Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match 'vite' -and $_.CommandLine -match 'FinanceDashboard'
} | ForEach-Object { Stop-One $_ 'frontend (vite)' }

if ($script:stopped -eq 0) {
    Write-Host '  No running services found.'
}
