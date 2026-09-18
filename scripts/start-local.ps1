$ErrorActionPreference = 'Stop'

Write-Host 'Starting ORCA infrastructure...' -ForegroundColor Cyan
docker compose up -d

Write-Host 'Starting backend...' -ForegroundColor Cyan
Set-Location "$PSScriptRoot\..\backend"
if (-not (Test-Path '.venv')) {
  python -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pytest
& .\.venv\Scripts\python.exe run.py
