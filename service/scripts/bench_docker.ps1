# Build and start the container with compose limits (2 vCPU / 2 GB), then load-test it while
# sampling `docker stats` (CPU %, RAM). Results: docs/loadtest_<name>.json.
# Usage (from service/): powershell -ExecutionPolicy Bypass -File scripts\bench_docker.ps1
param([int]$Duration = 30)
$svc = Split-Path -Parent $PSScriptRoot
Set-Location $svc
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw "docker compose failed" }
for ($i = 0; $i -lt 60; $i++) {
  Start-Sleep -Seconds 1
  try { if ((Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 2).StatusCode -eq 200) { break } } catch {}
}
docker inspect tram-forecast --format "NanoCpus={{.HostConfig.NanoCpus}} Memory={{.HostConfig.Memory}}"
$env:PYTHONIOENCODING = "utf-8"
foreach ($cfg in @(@{p=2;c=8;n="docker_16c"}, @{p=4;c=16;n="docker_64c"}, @{p=4;c=64;n="docker_256c"})) {
  python scripts\loadtest.py --url http://127.0.0.1:8000 --duration $Duration --procs $cfg.p --conc $cfg.c --container tram-forecast --name $cfg.n | Select-Object -Last 1
}
docker stats --no-stream tram-forecast
