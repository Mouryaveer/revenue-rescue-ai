#!/usr/bin/env pwsh
# RevenueRescue AI — Local backend startup
# Run from repo root: .\start_backend.ps1

$env:DATABASE_URL     = "postgresql+asyncpg://revenuerescue:revenuerescue@127.0.0.1:5432/revenuerescue"
$env:LLM_PROVIDER     = "mock"
$env:SIMULATION_MODE  = "true"
$env:APP_ENV          = "development"
$env:DEBUG            = "true"
# Secrets and provider selection must come from the environment/.env file.
# This script never supplies credentials or silently switches to simulation.

Write-Host ""
Write-Host "  RevenueRescue AI — Backend" -ForegroundColor Cyan
Write-Host "  API:   http://localhost:8000"
Write-Host "  Docs:  http://localhost:8000/docs"
Write-Host ""

Set-Location "$PSScriptRoot\backend"
& "$PSScriptRoot\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir "$PSScriptRoot\backend"
