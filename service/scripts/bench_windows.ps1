# Fallback benchmark when Docker is unavailable: start uvicorn with N workers pinned to 2 logical CPUs,
# sample CPU/RAM of the process tree, run scripts/loadtest.py, write docs/bench_<name>.json.
# Usage (from service/): powershell -ExecutionPolicy Bypass -File scripts\bench_windows.ps1 -Workers 4 -Procs 4 -Conc 16 -Name win_4w_64c
param([int]$Workers = 4, [int]$Procs = 4, [int]$Conc = 16, [int]$Duration = 30, [int]$Port = 8820, [string]$Name = "win")

$svc = Split-Path -Parent $PSScriptRoot
Set-Location $svc
$srv = Start-Process -FilePath python -ArgumentList "-m uvicorn app.main:app --port $Port --workers $Workers --no-access-log --http httptools" -PassThru -WindowStyle Hidden
try {
  for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    try { if ((Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/health" -TimeoutSec 2).StatusCode -eq 200) { break } } catch {}
  }
  Start-Sleep -Seconds 2
  $sampler = Start-Job -ScriptBlock { param($d, $ppid, $sec, $out)
    Set-Location $d
    & powershell -NoProfile -ExecutionPolicy Bypass -File scripts\win_limit_and_sample.ps1 -ParentPid $ppid -Seconds $sec -Out $out | Out-Null
  } -ArgumentList $svc, $srv.Id, ($Duration + 4), "docs\sample_$Name.json"
  Start-Sleep -Seconds 2
  $env:PYTHONIOENCODING = "utf-8"
  python scripts\loadtest.py --url "http://127.0.0.1:$Port" --duration $Duration --procs $Procs --conc $Conc --name $Name | Select-Object -Last 1
  Wait-Job $sampler | Out-Null
  Get-Content "docs\sample_$Name.json" -Raw | ConvertFrom-Json | Select-Object cpu_avg_pct, cpu_max_pct, mem_max_mb | ConvertTo-Json -Compress
} finally {
  Get-CimInstance Win32_Process -Filter "ParentProcessId=$($srv.Id)" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Stop-Process -Id $srv.Id -Force -ErrorAction SilentlyContinue
}
