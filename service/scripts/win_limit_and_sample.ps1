# Windows fallback when Docker is unavailable: pin a uvicorn process tree to 2 logical CPUs
# (like `cpus: 2`) and sample CPU% (100% = one core, max 200%) and RAM (working set, MB).
# Usage: powershell -File scripts/win_limit_and_sample.ps1 -ParentPid 1234 -Seconds 35 -Out docs/win_sample.json
param([int]$ParentPid, [int]$Seconds = 35, [string]$Out = "win_sample.json", [int]$Mask = 3)

function Get-Tree { param([int]$Root)
  $ids = @($Root) + @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$Root" | ForEach-Object { $_.ProcessId })
  Get-Process -Id $ids -ErrorAction SilentlyContinue
}
foreach ($p in Get-Tree $ParentPid) { $p.ProcessorAffinity = [IntPtr]$Mask }

$cpu = @(); $mem = @()
$prevCpu = (Get-Tree $ParentPid | ForEach-Object { $_.TotalProcessorTime.TotalMilliseconds } | Measure-Object -Sum).Sum
$t = [Diagnostics.Stopwatch]::StartNew(); $last = 0
for ($i = 0; $i -lt $Seconds; $i++) {
  Start-Sleep -Milliseconds 1000
  $tree = Get-Tree $ParentPid
  $now = ($tree | ForEach-Object { $_.TotalProcessorTime.TotalMilliseconds } | Measure-Object -Sum).Sum
  $el = $t.Elapsed.TotalMilliseconds
  $cpu += [Math]::Round(100 * ($now - $prevCpu) / ($el - $last), 1)
  $prevCpu = $now; $last = $el
  $mem += [Math]::Round((($tree | Measure-Object -Property WorkingSet64 -Sum).Sum) / 1MB, 1)
}
$res = [ordered]@{
  affinity_mask = $Mask
  cpu_avg_pct = [Math]::Round(($cpu | Measure-Object -Average).Average, 1)
  cpu_max_pct = ($cpu | Measure-Object -Maximum).Maximum
  mem_max_mb = ($mem | Measure-Object -Maximum).Maximum
  cpu_samples = $cpu
}
$res | ConvertTo-Json | Out-File -Encoding utf8 $Out
$res | ConvertTo-Json -Compress
