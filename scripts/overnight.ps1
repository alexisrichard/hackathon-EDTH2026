# Kick off both AIS full backfill and Kaggle downloads. Designed to run unattended.
# Usage: powershell -File scripts/overnight.ps1
#
# Each task runs in its own job. Logs land at data/cache/overnight_*.log.
# Kill with: Get-Job | Stop-Job; Get-Job | Remove-Job

$ErrorActionPreference = "Continue"
$root = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $root

New-Item -ItemType Directory -Force -Path data\cache | Out-Null
$ts = Get-Date -Format "yyyy-MM-dd_HHmm"
$aisLog = "data\cache\overnight_ais_$ts.log"
$kgLog  = "data\cache\overnight_kaggle_$ts.log"

# Refresh PATH so aws + python are available in the spawned jobs
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
$env:PYTHONIOENCODING = "utf-8"
$py = "$root\.venv\Scripts\python.exe"

Write-Output "Starting overnight tasks at $ts"
Write-Output "  Danish AIS log    -> $aisLog"
Write-Output "  Kaggle log        -> $kgLog"
Write-Output ""

# Start as background processes — they will outlive this script
$gfwLog = "data\cache\overnight_gfw_$ts.log"

$aisProc = Start-Process -FilePath $py `
  -ArgumentList "scripts\ingest\danish_ais.py","full" `
  -WorkingDirectory $root `
  -RedirectStandardOutput $aisLog `
  -RedirectStandardError "$aisLog.err" `
  -WindowStyle Hidden `
  -PassThru

$kgProc = Start-Process -FilePath $py `
  -ArgumentList "scripts\ingest\fetch_kaggle.py" `
  -WorkingDirectory $root `
  -RedirectStandardOutput $kgLog `
  -RedirectStandardError "$kgLog.err" `
  -WindowStyle Hidden `
  -PassThru

$gfwProc = Start-Process -FilePath $py `
  -ArgumentList "scripts\ingest\fetch_gfw.py" `
  -WorkingDirectory $root `
  -RedirectStandardOutput $gfwLog `
  -RedirectStandardError "$gfwLog.err" `
  -WindowStyle Hidden `
  -PassThru

Write-Output "AIS    PID $($aisProc.Id)"
Write-Output "Kaggle PID $($kgProc.Id)"
Write-Output "GFW    PID $($gfwProc.Id)  (~10 min, lightweight)"
Write-Output ""
Write-Output "Tail logs while you sleep with:"
Write-Output "  Get-Content $aisLog -Tail 5 -Wait"
Write-Output "  Get-Content $kgLog  -Tail 5 -Wait"
Write-Output "  Get-Content $gfwLog -Tail 5 -Wait"
Write-Output ""
Write-Output "Stop them with:"
Write-Output "  Stop-Process -Id $($aisProc.Id),$($kgProc.Id),$($gfwProc.Id) -Force"
