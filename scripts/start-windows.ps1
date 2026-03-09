$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

docker compose up --build -d
Write-Host "Server running on http://127.0.0.1:8000"
